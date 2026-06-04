import sys
from datetime import datetime,date
from modelos import(
    tipo_cultura,data_plantio,tipo_irrigacao,tipo_solo,prod_anterior,obs_user
)
from clima import buscar_dados_meteo
from indices import(
    resumo_climatico,dias_consecutivos_secos,dias_estresse_termico,risco_geada
)
from observacao import analisar_obs
from regras import fase_atual
from produtividade import potencial_ajustado
from scores import score_clima,score_geral,score_historico,score_risco,score_solo
from recomendador import recomendar
try:
    from ndvi import autenticar_gee,buscar_ndvi
    GEE_DISPONIVEL = True
except ImportError:
    GEE_DISPONIVEL = False
def analisar(lat, lon, cultura, data_plantio_dt, solo, irrigacao, prod_ant=None, observacoes="", usar_ndvi=True):
    resultado = {
        "metadata": {
            "data_analise": date.today().isoformat(),
            "lat": lat, "lon": lon,
            "cultura": cultura,
            "data_plantio": data_plantio_dt.strftime("%Y-%m-%d")
        },
        "clima": None, "indices": None,
        "fase": None, "ndvi": None,
        "observacao": None, "scores": None,
        "recomendacao": None,
        "erros": []
    }
    #Clima
    try:
        dados_clima = buscar_dados_meteo(lat, lon)
        if not dados_clima or not dados_clima.get("datas"):
            resultado["erros"].append("API climatico nao retornou dados")
        else: 
            resultado["clima"]={
                "total_dias": len(dados_clima["datas"]),
                "temp_media": round(sum((dados_clima["temp_max"][i] + dados_clima["temp_min"][i]) / 2 for i in range(len(dados_clima["datas"])))/ len(dados_clima["datas"]), 1),
                "precip_total": round(sum(dados_clima["precip"]),1),
                "fonte": dados_clima.get("fonte", "desconhecida")
            }
            indices = resumo_climatico(dados_clima)
            indices["dias_estresse_termico"] = dias_estresse_termico(dados_clima)
            indices["risco_geada_pct"] = risco_geada(dados_clima)
            indices["dias_consecutivos_secos"] = dias_consecutivos_secos(dados_clima)
            resultado["indices"]= indices
    except Exception as e: 
        resultado["erros"].append(f"Erro no modolo clima: {e}")
    # fenologia
    try:
        dias_plantio = (datetime.now() - data_plantio_dt).days
        fase_nome, fase_dados = fase_atual(cultura, dias_plantio)
        resultado["fase"] = {
            "nome": fase_nome,
            "nome_amigavel": fase_dados["nome_amigavel"],
            "dias_apos_plantio": dias_plantio,
            "sensivel_geada": fase_dados.get("sensivel_geada", False),
            "temp_ideal": fase_dados.get("temp_ideal"),
            "precip_ideal": fase_dados.get("precip_ideal_mm")
        }
    except Exception as e:
        resultado["erros"].append(f"Erro ao determinar fase: {e}")
        fase_dados = {}
    # NDVI
    ndvi_max = None
    if usar_ndvi and GEE_DISPONIVEL:
        print("  [NDVI] Autenticando GEE...", end="", flush=True)
        try:
            import os
            caminho_chave = os.environ.get("GEE_KEY_PATH")
            if not caminho_chave:
                raise ValueError("Variavel GEE_KEY_PATH nao definida")
            autenticar_gee(caminho_chave)
            print(" OK")
            print("  [NDVI] Buscando imagens Sentinel-2 (ate 90s)...", end="", flush=True)
            dados_ndvi = buscar_ndvi(
                lat, lon, data_plantio_dt, datetime.now(), intervalo_dias=15, timeout_segundos=90
            )
            if dados_ndvi and "ndvi" in dados_ndvi and dados_ndvi["ndvi"]:
                print(" OK — %d composite(s)" % len(dados_ndvi["ndvi"]))
                ndvi_max = max(dados_ndvi["ndvi"])
                resultado["ndvi"] = {
                    "total_imagens": len(dados_ndvi["ndvi"]),
                    "ndvi_max": round(ndvi_max, 3),
                    "ndvi_media": round(sum(dados_ndvi["ndvi"]) / len(dados_ndvi["ndvi"]), 3),
                    "ndvi_min": round(min(dados_ndvi["ndvi"]), 3),
                    "datas": dados_ndvi.get("datas", [])
                }
            else:
                print(" sem dados no periodo")
        except Exception as e:
            print(" erro")
            resultado["erros"].append(f"NDVI indisponivel: {e}")
    elif usar_ndvi and not GEE_DISPONIVEL:
        resultado["erros"].append("Modulo NDVI nao instalado (earthengine-api)")
    try:
        resultado["observacao"] = analisar_obs(observacoes) if observacoes.strip() else None
    except Exception as e:
        resultado["erros"].append(f"Erro na analise de observacao")
    try:
        sc_clima = score_clima(
            dados_clima if resultado["clima"] else None,
            resultado["indices"] or {},
            fase_dados or {},
        )
        sc_solo = score_solo(solo, irrigacao)
        sc_historico = score_historico(
            prod_ant, lat,lon, cultura, solo , irrigacao,ndvi_max
        )
        sc_risco = score_risco(
            resultado.get("observacao"), resultado.get("indices") or {}
        )
        todos_scores = {
            "clima": sc_clima,
            "solo": sc_solo,
            "historico": sc_historico,
            "risco": sc_risco
        }
        resultado["scores"] = score_geral(todos_scores)
        resultado["scores"]["parciais"] = {
            nome: {"valor": sc["valor"], "confianca": sc["confianca"]}
            for nome, sc in todos_scores.items() if sc
        }
    except Exception as e: 
        resultado["erros"].append(f"Erro no calculo de scores: {e}")
    try:
        alertas_obs = []
        if resultado.get("observacao") and resultado["observacao"].get("alertas"):
            CAT_POSITIVAS = ("clima_positivo", "solo_positivo", "sentimento_positivo")
            alertas_obs = [
                a for a in resultado["observacao"]["alertas"]
                if a.get("categoria") not in CAT_POSITIVAS
            ]
        scores_wrapped = {"geral": resultado["scores"]}
        resultado["recomendacao"] = recomendar(
            scores_wrapped,
            alertas_obs,
            resultado.get("indices") or {}
        )
    except Exception as e:
        resultado["erros"].append(f"Erro ao gerar recomendacao: {e}")
    resultado["status"] = "sucesso" if not resultado["erros"] else "parcial"
    return resultado
def exibir_relatorio(resultado):
    print("=" * 55)
    print("              SAFRASMART - RELATORIO COMPLETO")
    print("=" * 55)
    meta = resultado["metadata"]
    print(f"\nAnalise: {meta['data_analise']}")
    print(f"Local: {meta['lat']:.2f}, {meta['lon']:.2f}")
    print(f"Cultura: {meta['cultura'].title()}")
    print(f"Plantio: {meta['data_plantio']}")
    if resultado.get("fase"):
        f = resultado["fase"]
        print(f"\n+--- FASE FENOLOGICA ---+")
        print(f"  Fase: {f['nome_amigavel']} ({f['dias_apos_plantio']} dias)")
        if f["temp_ideal"]:
            print(f"  Temp ideal: {f['temp_ideal'][0]}C a {f['temp_ideal'][1]}C")
        if f["precip_ideal"]:
            print(f"  Precip ideal: {f['precip_ideal'][0]}mm a {f['precip_ideal'][1]}mm/mes")
    if resultado.get("clima"):
        c = resultado["clima"]
        print(f"\n+--- CLIMA ---+")
        print(f"  Temperatura media: {c['temp_media']}C")
        print(f"  Precipitacao total: {c['precip_total']}mm")
        print(f"  Periodo: {c['total_dias']} dias")
        print(f"  Fonte: {c['fonte']}")
    if resultado.get("indices"):
        i = resultado["indices"]
        print(f"  Dias secos consecutivos: {i.get('dias_consecutivos_secos', 'N/A')}")
        print(f"  Estresse termico: {i.get('dias_estresse_termico', 'N/A')} dias")
        print(f"  Risco de geada: {i.get('risco_geada_pct', 'N/A')}%")
    if resultado.get("ndvi"):
        n = resultado["ndvi"]
        print(f"\n+--- NDVI (Sentinel-2) ---+")
        print(f"  NDVI max: {n['ndvi_max']:.3f}")
        print(f"  NDVI medio: {n['ndvi_media']:.3f}")
        print(f"  Imagens: {n['total_imagens']} composite(s)")
    if resultado.get("observacao"):
        o = resultado["observacao"]
        print(f"\n+--- OBSERVACAO DO AGRICULTOR ---+")
        print(f"  Sentimento: {o.get('sentimento', 'N/A')}")
        print(f"  Alertas detectados: {o.get('total_alertas', 0)}")
        if o.get("alertas"):
            for a in o["alertas"]:
                print(f"    - {a.get('palavra', a.get('mensagem', ''))} "
                      f"[{a.get('severidade', 'N/A')}]")
    if resultado.get("scores"):
        s = resultado["scores"]
        print(f"\n+--- SCORES ---+")
        print(f"  Geral: {s['valor']:.1f}/10 - {s['classificacao']}")
        print(f"  Confianca: {s['confianca']}")
        if s.get("parciais"):
            for nome, ps in s["parciais"].items():
                barra = "#" * int(ps["valor"]) + "." * (10 - int(ps["valor"]))
                print(f"    {nome:10s}: {ps['valor']:.1f}/10 [{barra}] ({ps['confianca']})")
    if resultado.get("recomendacao"):
        r = resultado["recomendacao"]
        rp = r["recomendacao_principal"]
        print(f"\n+--- RECOMENDACAO ---+")
        print(f"  {rp['nivel'].upper()}")
        print(f"  {rp['texto']}")
        print(f"  Confianca: {rp['confianca']}")
        print(f"\n  {r.get('probabilidade', '')}")

        if r.get("alertas_ativos"):
            print(f"\n  Alertas ativos ({len(r['alertas_ativos'])}):")
            for a in r["alertas_ativos"]:
                print(f"    [!{a['severidade'].upper()}] {a['mensagem']}")

        if r.get("acoes_recomendadas"):
            print(f"\n  Acoes recomendadas:")
            for i, acao in enumerate(r["acoes_recomendadas"], 1):
                print(f"    {i}. {acao}")
    if resultado.get("erros"):
        print(f"\n+--- AVISOS ---+")
        for erro in resultado["erros"]:
            print(f"  ! {erro}")

    print("\n" + "=" * 55)
    print("              Fim do relatorio SafraSmart")
    print("=" * 55)
def main():
    print("=== SafraSmart - Analise Completa ===\n")

    cultura = tipo_cultura()
    dt_plantio = data_plantio()
    solo = tipo_solo()
    irrig = tipo_irrigacao()
    prod_ant = prod_anterior()
    obs = obs_user()

    lat = float(input("Latitude: ").replace(",", "."))
    lon = float(input("Longitude: ").replace(",", "."))
    resultado = analisar(
        lat=lat, lon=lon,
        cultura=cultura,
        data_plantio_dt=dt_plantio,
        solo=solo,
        irrigacao=irrig,
        prod_ant=prod_ant,
        observacoes=obs,
        usar_ndvi=True
    )
    exibir_relatorio(resultado)
if __name__ == "__main__":
    # Teste com dados reais de Sorriso/MT (maior produtor de soja do Brasil)
    print("=== Teste SafraSmart - Fazenda em Sorriso/MT ===\n")
    from datetime import datetime
    resultado = analisar(
        lat=-12.55, lon=-55.72,
        cultura="soja",
        data_plantio_dt=datetime(2025, 10, 20),
        solo="argiloso",
        irrigacao="sequeiro",
        prod_ant=80,
        observacoes="plantio realizado na epoca certa, chuva boa, mas teve alguns dias muito quentes",
        usar_ndvi=True
    )
    exibir_relatorio(resultado)