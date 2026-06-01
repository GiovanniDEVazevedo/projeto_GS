from regras import fase_atual,faixa_com_tolerancia, PESO_SENSIBILIDADE
from produtividade import potencial_ajustado

PESOS = {
    "clima": 0.4,
    "solo": 0.2,
    "historico": 0.2,
    "risco": 0.2
}
def score_clima(dados_climaticos, resumo_indices,fase):
    if not dados_climaticos or not resumo_indices:
        return {"valor": 5.0 ,"confianca": "baixa", "detalhes":{}}
    n = len(dados_climaticos["datas"])
    temp_media_geral = round(sum((dados_climaticos["temp_max"][i] + dados_climaticos["temp_min"][i])/ 2 for i in range(n))/n,1) 
    precip_total = sum(dados_climaticos["precip"])
    temp_ideal = fase.get("temp_ideal", (20,30))
    precip_ideal = fase.get("temp_ideal_mm", (30,60))
    temp_tol = faixa_com_tolerancia(temp_ideal[0], temp_ideal[1])
    precip_tol = faixa_com_tolerancia(precip_ideal[0], precip_ideal[1])
    if temp_tol[0] <= temp_media_geral <= temp_tol[1]:
        score_temp = 10.0
    else:
        desvio = min(abs(temp_media_geral - temp_tol[0]), abs(temp_media_geral - temp_tol[1]))
        score_temp = max(0,10 - desvio * 2)
    if precip_tol[0] <= precip_total <= precip_tol[1]:
        score_precip = 10.0
    else:
        razao = precip_total / ((precip_ideal[0] + precip_ideal[1])/2)
        if razao > 1:
            score_precip = max(0, 10 - (razao - 1) * 5)
        else:
            score_precip = max(0, 10 - (1 - razao) * 5)
    penalidade = 0 
    estresse = resumo_indices.get("dias_estresse_termico", 0)
    if estresse and estresse > 5:
        penalidade += min(estresse * 0.1, 2.0)
    geada_pct = resumo_indices.get("risco_geada_pct", 0)
    if fase.get("sensivel_geada", False)and geada_pct > 0:
        penalidade += min(geada_pct  / 10,2.0)
    valor = round(score_temp * 0.5 + score_precip *0.3 - penalidade * 0.2, 1)
    valor= max(0, min(10, valor))
    confianca = "alta" if n>= 300 else "media" if n <= 90 else "baixa" 
    return {
        "valor": valor,
        "confianca": confianca,
        "detalhes": {
            "score_temp": round(score_temp, 1),
            "score_precip": round(score_precip, 1),
            "penalidade": round(penalidade, 1),
            "temp_media": temp_media_geral,
            "precip_total": round(precip_total, 1)
        }
    }
def score_solo(tipo_solo, irrigacao):
    NOTA_SOLO = {"argiloso": 8, "misto": 6, "arenoso": 4}
    BONUS_IRRIGACAO = {"gotejo": 2, "aspersao": 1, "sequeiro": 0}
    nota = NOTA_SOLO.get(tipo_solo, 5)
    bonus = BONUS_IRRIGACAO.get(irrigacao, 0)
    valor = min(10, nota + bonus)
    return {"valor": valor, "confianca": "alta", "detalhes": {"nota_solo": nota, "bonus_irrigacao": bonus}}
def score_historico(prod_anterior, lat, lon, cultura, tipo_solo, irrigacao, ndvi_max=None):
    potencial = potencial_ajustado(lat, lon, cultura, tipo_solo, irrigacao, ndvi_max)
    potencial_valor = potencial["potencial_base"]
    if prod_anterior is None:
        return {"valor": 5.0, "confianca": "baixa", "detalhes": {"prod_anterior": None}}
    if potencial_valor <= 0:
        return {"valor": 5.0, "confianca": "baixa", "detalhes": {}}
    valor = round((prod_anterior / potencial_valor) * 10, 1)
    valor = max(0, min(10, valor))
    confianca = "media"
    if valor >= 9.0 or valor <= 1.0:
        confianca = "alta"
    return {
        "valor": valor,
        "confianca": confianca,
        "detalhes": {
            "prod_anterior": prod_anterior,
            "potencial_regional": potencial_valor
        }
    }
def score_risco(analise_obs, resumo_indices):
    penalidade = 0.0
    if analise_obs and analise_obs.get("alertas"):
        for alerta in analise_obs["alertas"]:
            sev = alerta.get("severidade", "baixa")
            if sev == "alta":       
                penalidade += 1.5
            elif sev == "media":    
                penalidade += 1.0
            else:
                penalidade += 0.5
    if resumo_indices:
        dias_secos = resumo_indices.get("dias_consecutivos_secos", 0)
        if dias_secos and dias_secos > 10:
            penalidade += min((dias_secos - 10) * 0.2, 2.0)
    geada_pct = resumo_indices.get("risco_geada_pct", 0)
    if geada_pct and geada_pct > 5:
        penalidade += min(geada_pct / 10, 1.5)
    valor = round(max(0, 10 - penalidade), 1)
    confianca = "alta" if analise_obs else "baixa"
    return {
        "valor": valor,
        "confianca": confianca,
        "detalhes": {"penalidade_total": round(penalidade, 1), "total_alertas": len(analise_obs.get("alertas", [])) if analise_obs else 0}
    }
def score_geral(scores):
    if not scores:
        return {"valor": 0, "classificacao": "Sem dados", "confianca": "baixa"}
    ponderado = 0.0
    confiancas = []
    for nome, peso in PESOS.items():
        sc = scores.get(nome)
        if sc:
            ponderado += sc["valor"] * peso
            confiancas.append(sc["confianca"])
            valor = round(ponderado, 1)
    classificacao = classificar(valor)
    return {
        "valor": valor,
        "classificacao": classificacao,
        "confianca": _confianca_geral(confiancas),
        "scores": {k: v["valor"] for k, v in scores.items() if v}
    }
def classificar(valor):
    if valor >= 7.0:    return "Recomendado"
    if valor >= 5.0:    return "Atencao"
    return "Nao recomendado"
def _confianca_geral(confiancas):
    if not confiancas:
        return "baixa"
    if all(c == "alta" for c in confiancas):
        return "alta"
    if any(c == "baixa" for c in confiancas):
        return "baixa"
    return "media"
if __name__ == "__main__":
    from datetime import datetime
    from clima import buscar_dados_meteo
    from indices import resumo_climatico, dias_estresse_termico, risco_geada, dias_consecutivos_secos
    from regras import fase_atual
    from observacao import analisar_obs
    from modelos import tipo_cultura, data_plantio, tipo_solo, tipo_irrigacao, prod_anterior, obs_user
    from ndvi import autenticar_gee, buscar_ndvi

    # 1. Dados do agricultor (simulados)
    cultura = "soja"
    data_plantio_dt = datetime(2025, 10, 15)
    solo = "argiloso"
    irrig = "gotejo"
    prod_ant = 55
    obs = "teve uma geada forte e a terra ta rachada"

    lat = -24.95
    lon = -53.46

    print("=== SafraSmart - Score Completo ===\n")

    # 2. Clima
    print("[1/5] Buscando dados climaticos...")
    dados_clima = buscar_dados_meteo(lat, lon)
    resumo_indices = resumo_climatico(dados_clima)
    resumo_indices["dias_estresse_termico"] = dias_estresse_termico(dados_clima)
    resumo_indices["risco_geada_pct"] = risco_geada(dados_clima)
    resumo_indices["dias_consecutivos_secos"] = dias_consecutivos_secos(dados_clima)

    # 3. Fase fenológica
    dias_plantio = (datetime.now() - data_plantio_dt).days
    fase_nome, fase_dados = fase_atual(cultura, dias_plantio)
    print(f"[2/5] Fase: {fase_dados['nome_amigavel']}")

    # 4. Observação
    analise_obs = analisar_obs(obs)
    print(f"[3/5] Observacao: {analise_obs['sentimento']} ({analise_obs['total_alertas']} alertas)")

    # 5. NDVI (opcional)
    ndvi_max = None
    try:
        dados_ndvi = buscar_ndvi(lat, lon, data_plantio_dt, datetime.now(), intervalo_dias=30)
        if dados_ndvi:
            ndvi_max = dados_ndvi["ndvi_max"]
            print(f"[4/5] NDVI maximo: {ndvi_max}")
    except Exception:
        print("[4/5] NDVI indisponivel (continuando sem)")

    # 6. Scores
    sc_clima = score_clima(dados_clima, resumo_indices, fase_dados)
    sc_solo = score_solo(solo, irrig)
    sc_historico = score_historico(prod_ant, lat, lon, cultura, solo, irrig, ndvi_max)
    sc_risco = score_risco(analise_obs, resumo_indices)

    scores = {"clima": sc_clima, "solo": sc_solo, "historico": sc_historico, "risco": sc_risco}
    geral = score_geral(scores)

    # 7. Resultado
    print(f"\n[5/5] RESULTADO:\n")
    for nome, sc in scores.items():
        print(f"  {nome.upper():10s}: {sc['valor']:.1f}/10  ({sc['confianca']})")
    print(f"\n  GERAL:      {geral['valor']:.1f}/10")
    print(f"  CLASSIFICACAO: {geral['classificacao']}")
    print(f"  CONFIRANCA:    {geral['confianca']}")
    print(f"\n  Scores parciais: {geral['scores']}")