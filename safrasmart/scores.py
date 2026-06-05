from .regras import fase_atual, faixa_com_tolerancia, PESO_SENSIBILIDADE
from .produtividade import potencial_ajustado

# =============================================================================
# PESOS DE CADA DIMENSAO NO SCORE GERAL
# =============================================================================
# Clima tem o dobro do peso das demais dimensoes porque:
# - O clima e o fator mais critico e imprevisivel na agricultura.
# - Solo, historico e risco sao importantes mas tem impacto mais previsivel.
# - A ponderacao reflete a prioridade: 40% clima, 20% cada um dos outros.
# =============================================================================
PESOS = {
    "clima": 0.4,
    "solo": 0.2,
    "historico": 0.2,
    "risco": 0.2
}


def score_clima(dados_climaticos, resumo_indices, fase):
    """
    CALCULA o score de clima (0-10) comparando dados observados com faixas ideais.
    
    PARAMETROS:
        dados_climaticos (dict): dados brutos da API climatica (clima.py).
        resumo_indices (dict): indices calculados (indices.py:resumo_climatico).
        fase (dict): dados da fase fenologica atual (regras.py:fase_atual).
    
    RETORNA: dict com:
        "valor" (float): score de 0 a 10.
        "confianca" (str): "alta" (>=300 dias), "media" (<300), "baixa" (<90).
        "detalhes" (dict): score_temp, score_precip, penalidade, temp_media, precip_total.
    
    MOTIVO DOS PARAMETROS:
    dados_climaticos: para extrair temperaturas e precipitacao reais.
    resumo_indices: para obter estresse termico e risco de geada.
    fase: para comparar com as faixas ideais da fase fenologica atual.
    
    LOGICA DE PONTUACAO:
    1. Temperatura: 10 se dentro da faixa (com 20% tolerancia).
       Senao, perde 2 pontos por grau Celsius de desvio.
    2. Precipitacao: 10 se dentro da faixa. Senao, perde 5 pontos por
       100% de desvio em relacao ao ponto medio.
    3. Penalidades: estresse termico >5 dias (-0.1/dia, max -2);
       geada em fase sensivel (-geada%/10, max -2).
    4. Formula final: score_temp*0.5 + score_precip*0.3 - penalidade*0.2
    """
    if not dados_climaticos or not resumo_indices:
        return {"valor": 5.0, "confianca": "baixa", "detalhes": {}}

    n = len(dados_climaticos["datas"])
    temp_media_geral = round(sum(
        (dados_climaticos["temp_max"][i] + dados_climaticos["temp_min"][i]) / 2
        for i in range(n)
    ) / n, 1)
    precip_total = sum(dados_climaticos["precip"])
    temp_ideal = fase.get("temp_ideal", (20, 30))
    precip_ideal = fase.get("precip_ideal_mm", (30, 60))
    temp_tol = faixa_com_tolerancia(temp_ideal[0], temp_ideal[1])
    precip_tol = faixa_com_tolerancia(precip_ideal[0], precip_ideal[1])

    # Score de temperatura
    if temp_tol[0] <= temp_media_geral <= temp_tol[1]:
        score_temp = 10.0
    else:
        desvio = min(abs(temp_media_geral - temp_tol[0]),
                     abs(temp_media_geral - temp_tol[1]))
        score_temp = max(0, 10 - desvio * 2)

    # Score de precipitacao
    if precip_tol[0] <= precip_total <= precip_tol[1]:
        score_precip = 10.0
    else:
        ponto_medio = (precip_ideal[0] + precip_ideal[1]) / 2
        razao = precip_total / ponto_medio if ponto_medio > 0 else 1
        if razao > 1:
            score_precip = max(0, 10 - (razao - 1) * 5)
        else:
            score_precip = max(0, 10 - (1 - razao) * 5)

    # Penalidades
    penalidade = 0
    estresse = resumo_indices.get("dias_estresse_termico", 0)
    if estresse and estresse > 5:
        penalidade += min(estresse * 0.1, 2.0)

    geada_pct = resumo_indices.get("risco_geada_pct", 0)
    if fase.get("sensivel_geada", False) and geada_pct > 0:
        penalidade += min(geada_pct / 10, 2.0)

    valor = round(score_temp * 0.5 + score_precip * 0.3 - penalidade * 0.2, 1)
    valor = max(0, min(10, valor))

    # Confianca baseada na quantidade de dados disponiveis
    confianca = "alta" if n >= 300 else "media" if n >= 90 else "baixa"

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
    """
    CALCULA o score de solo e irrigacao (0-10).
    
    PARAMETROS:
        tipo_solo (str): "argiloso", "misto" ou "arenoso".
        irrigacao (str): "gotejo", "aspersao" ou "sequeiro".
    
    RETORNA: dict com "valor" (0-10), "confianca" (sempre "alta"), "detalhes".
    
    LOGICA:
    - Nota base: argiloso=8, misto=6, arenoso=4.
    - Bonus irrigacao: gotejo=+2, aspersao=+1, sequeiro=+0.
    - Valor maximo: 10.
    
    MOTIVO:
    Argiloso recebe nota 8 porque e o solo ideal para agricultura (retencao
    de agua e nutrientes). Arenoso recebe 4 porque exige mais manejo.
    Gotejo e o sistema mais eficiente (+2), aspersao e intermediario (+1).
    """
    NOTA_SOLO = {"argiloso": 8, "misto": 6, "arenoso": 4}
    BONUS_IRRIGACAO = {"gotejo": 2, "aspersao": 1, "sequeiro": 0}
    nota = NOTA_SOLO.get(tipo_solo, 5)
    bonus = BONUS_IRRIGACAO.get(irrigacao, 0)
    valor = min(10, nota + bonus)
    return {
        "valor": valor,
        "confianca": "alta",
        "detalhes": {"nota_solo": nota, "bonus_irrigacao": bonus}
    }


def score_historico(prod_anterior, lat, lon, cultura, tipo_solo, irrigacao, ndvi_max=None):
    """
    CALCULA o score historico comparando produtividade anterior com potencial regional.
    
    PARAMETROS:
        prod_anterior (float): sacas/ha colhidas na safra passada.
        lat, lon (float): coordenadas da propriedade.
        cultura (str): "soja" ou "milho".
        tipo_solo (str): tipo de solo.
        irrigacao (str): tipo de irrigacao.
        ndvi_max (float, opcional): NDVI maximo para ajuste fino.
    
    RETORNA: dict com "valor" (0-10), "confianca", "detalhes".
    
    LOGICA:
    score = (prod_anterior / potencial_regional) * 10
    Se produziu exatamente o potencial da regiao, score = 10.
    Se produziu 50% do potencial, score = 5.
    
    Confianca: "media" por padrao; "alta" se score >= 9 ou <= 1
    (consistencia comprovada para mais ou para menos).
    
    MOTIVO:
    Compara o desempenho real do agricultor com a media estadual da CONAB,
    considerando solo, irrigacao e NDVI. Um score alto indica que o agricultor
    esta acima da media regional (boa gestao).
    """
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


def score_risco(analise_obs, resumo_indices, temp_media=None, temp_ideal=None):
    """
    CALCULA o score de risco (0-10) com base em observacoes e indices climaticos.
    
    PARAMETROS:
        analise_obs (dict): saida de observacao.py:analisar_obs().
        resumo_indices (dict): indices climaticos (indices.py:resumo_climatico).
        temp_media (float, opcional): temperatura media do periodo.
        temp_ideal (tuple, opcional): faixa ideal de temperatura (min, max).
    
    RETORNA: dict com "valor" (0-10), "confianca", "detalhes".
    
    LOGICA:
    - Comeca em 10 e subtrai penalidades.
    - Se nao ha observacao do agricultor: penalidade fixa de -3 (incerteza).
    - Alertas da observacao: alta=-1.5, media=-1.0, baixa=-0.5.
    - Dias secos >5: -0.2/dia extra (max -2).
    - Risco de geada >2%: -geada%/10 (max -1.5).
    - Temperatura fora da faixa ideal: -1 por grau de desvio (max -2).
    - Confianca: "alta" se agricultor deu observacoes, "media" se so indices, "baixa" se nada.
    
    MOTIVO:
    Antes o score ficava 10/10 quando nao havia observacoes (comum no formulario web),
    enganando o usuario. Agora aplica penalidade por falta de informacao e usa
    limiares climaticos mais sensiveis para capturar riscos moderados.
    """
    penalidade = 0.0

    # Penalidade por falta de observacao do agricultor
    if not analise_obs:
        penalidade += 3.0  # incerteza de nao saber o que ocorre em campo

    # Alertas das observacoes do agricultor
    if analise_obs and analise_obs.get("alertas"):
        for alerta in analise_obs["alertas"]:
            sev = alerta.get("severidade", "baixa")
            if sev == "alta":
                penalidade += 1.5
            elif sev == "media":
                penalidade += 1.0
            else:
                penalidade += 0.5

    # Dias secos consecutivos (limiar reduzido de >10 para >5)
    if resumo_indices:
        dias_secos = resumo_indices.get("dias_consecutivos_secos", 0)
        if dias_secos and dias_secos > 5:
            penalidade += min((dias_secos - 5) * 0.2, 2.0)

    # Risco de geada (limiar reduzido de >5% para >2%)
    geada_pct = resumo_indices.get("risco_geada_pct", 0)
    if geada_pct and geada_pct > 2:
        penalidade += min(geada_pct / 10, 1.5)

    # Penalidade por temperatura fora da faixa ideal
    if temp_media is not None and temp_ideal:
        t_min, t_max = temp_ideal
        if temp_media < t_min:
            penalidade += min((t_min - temp_media) * 1.0, 2.0)
        elif temp_media > t_max:
            penalidade += min((temp_media - t_max) * 1.0, 2.0)

    valor = round(max(0, 10 - penalidade), 1)

    if analise_obs:
        confianca = "alta"
    elif resumo_indices:
        confianca = "media"
    else:
        confianca = "baixa"

    return {
        "valor": valor,
        "confianca": confianca,
        "detalhes": {
            "penalidade_total": round(penalidade, 1),
            "total_alertas": len(analise_obs.get("alertas", [])) if analise_obs else 0
        }
    }


def score_geral(scores):
    """
    CALCULA o score geral ponderado (0-10) a partir dos 4 scores parciais.
    
    PARAMETROS:
        scores (dict): dicionario com os 4 scores parciais:
            {"clima": dict, "solo": dict, "historico": dict, "risco": dict}.
    
    RETORNA: dict com:
        "valor" (float): score ponderado final (0-10).
        "classificacao" (str): "Recomendado", "Atencao" ou "Nao recomendado".
        "confianca" (str): "alta", "media" ou "baixa".
        "scores" (dict): valores numericos de cada dimensao.
    
    FORMULA:
    geral = clima*0.4 + solo*0.2 + historico*0.2 + risco*0.2
    
    Confianca geral:
    - "alta" se todos os 4 forem "alta".
    - "baixa" se algum for "baixa".
    - "media" caso contrario.
    """
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
    """
    CONVERTE um valor numerico (0-10) em uma classificacao textual.
    
    PARAMETROS:
        valor (float): score geral entre 0 e 10.
    
    RETORNA: str — "Recomendado" (>=7), "Atencao" (5-6.9), "Nao recomendado" (<5).
    
    MOTIVO:
    Os limites seguem a logica de notas escolares adaptada para agricultura:
    - >=7: condicoes favoraveis (como nota azul).
    - 5-6.9: condicoes regulares, requer atencao (como nota amarela).
    - <5: condicoes desfavoraveis (como nota vermelha).
    """
    if valor >= 7.0:
        return "Recomendado"
    if valor >= 5.0:
        return "Atencao"
    return "Nao recomendado"


def _confianca_geral(confiancas):
    """
    CALCULA a confianca geral a partir das confiancas individuais.
    
    PARAMETROS:
        confiancas (list[str]): lista de "alta", "media" ou "baixa".
    
    RETORNA: str — "alta", "media" ou "baixa".
    
    LOGICA:
    - Todas "alta" -> "alta".
    - Alguma "baixa" -> "baixa".
    - Senao -> "media".
    
    MOTIVO:
    A confianca geral so e "alta" se TODAS as dimensoes tiverem dados
    confiaveis. Basta uma dimensao com problema para reduzir a confianca.
    """
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

    # 3. Fase fenologica
    dias_plantio = (datetime.now() - data_plantio_dt).days
    fase_nome, fase_dados = fase_atual(cultura, dias_plantio)
    print(f"[2/5] Fase: {fase_dados['nome_amigavel']}")

    # 4. Observacao
    analise_obs = analisar_obs(obs)
    print(f"[3/5] Observacao: {analise_obs['sentimento']} ({analise_obs['total_alertas']} alertas)")

    # 5. NDVI
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
