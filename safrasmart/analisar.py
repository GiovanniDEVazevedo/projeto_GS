"""Pipeline versionado com evidências, cobertura e análise por fase estimada."""
import logging
import os
from datetime import date, datetime, timedelta
from uuid import uuid4

from .modelos import tipo_cultura, data_plantio, tipo_irrigacao, tipo_solo, prod_anterior, obs_user
from .clima import buscar_dados_meteo, coordenadas, hoje_local
from .indices import resumo_climatico, recortar_periodo
from .observacao import analisar_obs
from .regras import fase_atual, obter_tabela
from .scores import score_clima, score_geral, score_historico, score_risco, score_solo
from .recomendador import recomendar
from .validacao import validar

log = logging.getLogger(__name__)
VERSAO_MOTOR = "2.0.0"


def analisar(lat, lon, cultura, data_plantio_dt, solo, irrigacao,
             prod_ant=None, observacoes="", usar_ndvi=True, cache=None, hoje=None):
    validar({"id": str(uuid4()), "lat": lat, "lon": lon, "cultura": cultura,
             "data_plantio": data_plantio_dt.strftime("%Y-%m-%d"), "solo": solo,
             "irrigacao": irrigacao, "prod_ant": prod_ant, "observacoes": observacoes})
    hoje = hoje or hoje_local()
    plantio = data_plantio_dt.date()
    dias = (hoje - plantio).days
    fase_nome, fase_dados = fase_atual(cultura, dias)
    tabela = obter_tabela(cultura)
    ciclo = max(f["dias"][1] for f in tabela.values())
    pos_ciclo = dias >= ciclo
    referencia = list(tabela.values())[-1] if pos_ciclo else fase_dados
    fim = min(hoje - timedelta(days=1), plantio + timedelta(days=ciclo - 1))
    inicio_janela = max(plantio + timedelta(days=referencia["dias"][0]), fim - timedelta(days=29)) if dias >= 0 else fim - timedelta(days=29)
    resultado = {
        "metadata": {"data_analise": hoje.isoformat(), "lat": lat, "lon": lon, "cultura": cultura,
                     "data_plantio": plantio.isoformat(), "versao_motor": VERSAO_MOTOR,
                     "contexto": "historico_do_ciclo_estimado" if pos_ciclo else "planejamento" if dias < 0 else "monitoramento",
                     "natureza": "apoio_a_decisao_experimental"},
        "clima": None, "indices": {}, "ndvi": None, "scores": None, "erros": [],
        "fase": {"nome": fase_nome, "nome_amigavel": fase_dados["nome_amigavel"], "dias_apos_plantio": dias,
                 "sensivel_geada": referencia.get("sensivel_geada", False), "temp_ideal": referencia.get("temp_ideal"),
                 "precip_ideal": referencia.get("precip_ideal_mm"), "estimada": True,
                 "limitacao": "Calendário genérico; varia com cultivar, região e manejo. Não confirma colheita."},
        "observacao": analisar_obs(observacoes),
    }
    dados_clima = None
    janela = None
    parametros = {"tipo": "clima-v2", "lat": lat, "lon": lon, "dias": 365, "fim": fim.isoformat()}
    try:
        calcular = lambda: buscar_dados_meteo(lat, lon, fim=fim)
        dados_clima = cache.obter_ou_calcular(parametros, calcular) if cache else calcular()
        if dados_clima:
            resumo = resumo_climatico(dados_clima)
            resultado["clima"] = {"total_dias": len(dados_clima["datas"]), "temp_media": resumo["temp_media_geral"],
                                  "precip_total": resumo["precip_total"], "fonte": dados_clima["fonte"],
                                  "precip_completa": resumo["precip_completa"],
                                  "periodo_inicio": resumo["periodo_inicio"], "periodo_fim": resumo["periodo_fim"],
                                  "consultado_em": dados_clima.get("consultado_em")}
            janela = recortar_periodo(dados_clima, inicio_janela, fim)
            resultado["indices"] = resumo_climatico(janela)
        else:
            resultado["erros"].append("Fontes climáticas indisponíveis; nenhuma condição foi presumida.")
    except (ValueError, KeyError, TypeError, IndexError):
        log.exception("Dados meteorológicos inválidos")
        resultado["erros"].append("Dados climáticos inválidos ou incompletos.")

    if usar_ndvi and plantio < hoje:
        if os.getenv("GEE_KEY_PATH"):
            try:
                from .ndvi import buscar_ndvi
                inicio_ndvi = datetime.combine(plantio, datetime.min.time())
                fim_ndvi = datetime.combine(min(hoje, plantio + timedelta(days=ciclo)), datetime.min.time())
                calcular_ndvi = lambda: buscar_ndvi(lat, lon, inicio_ndvi, fim_ndvi)
                chave_ndvi = {"tipo": "ndvi-scl-v2", "lat": lat, "lon": lon,
                              "inicio": plantio.isoformat(), "fim": fim_ndvi.isoformat(), "intervalo": 15, "buffer": 50}
                ndvi = cache.obter_ou_calcular(chave_ndvi, calcular_ndvi, ttl=86400) if cache else calcular_ndvi()
                if ndvi:
                    resultado["ndvi"] = {**ndvi, "total_imagens": len(ndvi["ndvi"]),
                        "ndvi_media": ndvi["ndvi_medio_geral"],
                        "area": "Amostra em raio de 50 m do ponto; não representa o polígono da propriedade."}
                else:
                    resultado["erros"].append("NDVI sem observações válidas no período ou abaixo da cobertura mínima.")
            except (ImportError, TimeoutError, RuntimeError, ValueError, OSError):
                log.warning("NDVI indisponível")
                resultado["erros"].append("NDVI indisponível; a análise continua sem dados de vegetação.")
        else:
            resultado["erros"].append("NDVI não configurado (GEE_KEY_PATH).")

    indices = resultado["indices"]
    sc_clima = score_clima(janela, indices, referencia) if dias >= 0 else score_clima(None, {}, {})
    parciais = {"clima": sc_clima, "solo": score_solo(solo, irrigacao),
                "historico": score_historico(prod_ant, lat, lon, cultura, solo, irrigacao),
                "risco": score_risco(resultado["observacao"], indices,
                    temp_media=indices.get("temp_media_geral"), temp_ideal=referencia.get("temp_ideal"))}
    resultado["scores"] = {**score_geral(parciais), "parciais": parciais}
    resultado["recomendacao"] = recomendar({"geral": resultado["scores"]}, resultado["observacao"]["alertas"], indices)
    resultado["confiabilidade"] = {
        "qualidade_dados": "suficiente_para_triagem" if sc_clima["valor"] is not None else "insuficiente",
        "cobertura_temperatura": indices.get("cobertura_temperatura", 0),
        "cobertura_precipitacao": indices.get("cobertura_precipitacao", 0),
        "incerteza_agronomica": "alta", "modelo_validado": False,
        "regras": "fenologia-calendario-v2-experimental", "observacoes": "relato_nao_verificado",
    }
    resultado["status"] = "parcial" if resultado["erros"] or sc_clima["valor"] is None else "sucesso"
    return resultado


def exibir_relatorio(resultado):
    """
    EXIBE o relatorio completo formatado no terminal.
    
    PARAMETROS:
        resultado (dict): saida completa da funcao analisar().
    
    RETORNA: None — apenas imprime no terminal.
    
    MOTIVO:
    Formata o dicionario de resultado em seccoes visuais com ASCII,
    facilitando a leitura pelo agricultor no terminal. Cada seccao
    so aparece se o dado correspondente estiver disponivel.
    """
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
        print("  Origem: relato do produtor, não verificado")
        print(f"  Alertas detectados: {o.get('total_alertas', 0)}")
        if o.get("alertas"):
            for a in o["alertas"]:
                print(f"    - {a.get('palavra', a.get('mensagem', ''))} "
                      f"[{a.get('severidade', 'N/A')}]")

    if resultado.get("scores"):
        s = resultado["scores"]
        print(f"\n+--- SCORES ---+")
        print(f"  Índice experimental: {s['valor']} - {s['classificacao']}")
        print(f"  Confianca: {s['confianca']}")
        if s.get("parciais"):
            for nome, ps in s["parciais"].items():
                barra = "disponível" if ps["valor"] is not None else "sem dados"
                print(f"    {nome:10s}: {ps['valor']} [{barra}] ({ps['confianca']})")

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
    """
    FUNCAO PRINCIPAL para uso interativo via terminal.
    
    PARAMETROS: nenhum — coleta todos os dados via modelos.py + input().
    
    RETORNA: None — executa a analise completa e exibe o relatorio.
    
    MOTIVO:
    Versao CLI completa para uso direto no terminal sem necessidade
    de servidor web. Coleta cultura, data, solo, irrigacao, produtividade
    anterior, observacoes e coordenadas do usuario.
    """
    print("=== SafraSmart - Analise Completa ===\n")

    cultura = tipo_cultura()
    dt_plantio = data_plantio()
    solo = tipo_solo()
    irrig = tipo_irrigacao()
    prod_ant = prod_anterior()
    obs = obs_user()

    lat ,lon = coordenadas()

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
