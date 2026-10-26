"""Índices experimentais de compatibilidade, nunca probabilidades de sucesso."""
from .indices import resumo_climatico
from .regras import faixa_com_tolerancia

PESOS = {"clima": .4, "solo": .2, "historico": .2, "risco": .2}


def indisponivel(motivo):
    return {"valor": None, "confianca": "baixa", "status": "SEM_DADOS", "detalhes": {"motivo": motivo}}


def score_clima(dados_climaticos, resumo_indices, fase):
    if not dados_climaticos or not fase:
        return indisponivel("Sem dados climáticos ou referência da fase.")
    resumo = resumo_climatico(dados_climaticos)
    n = resumo.get("dias_esperados", 0)
    # Não extrapolar chuva de dias faltantes. Comparação requer janela completa.
    if n < 7 or resumo.get("cobertura_temperatura", 0) < .8 or not resumo.get("precip_completa"):
        return indisponivel("Janela com menos de 7 dias ou cobertura insuficiente; chuva não foi extrapolada.")
    temp = resumo["temp_media_geral"]
    precip_total = resumo["precip_total"]
    precip_30dias = precip_total * 30 / n
    tmin, tmax = faixa_com_tolerancia(*fase.get("temp_ideal", (20, 30)))
    pmin, pmax = faixa_com_tolerancia(*fase.get("precip_ideal_mm", (30, 60)))
    score_temp = max(0., 10 - max(tmin - temp, temp - tmax, 0) * 2)
    ponto = max(1, sum(fase.get("precip_ideal_mm", (30, 60))) / 2)
    score_precip = max(0., 10 - max(pmin - precip_30dias, precip_30dias - pmax, 0) / ponto * 5)
    penalidade = min(max(0, (resumo.get("dias_estresse_termico") or 0) - 5) * .1, 2)
    if fase.get("sensivel_geada"):
        penalidade += min((resumo.get("risco_geada_pct") or 0) / 10, 2)
    valor = round(max(0, min(10, (score_temp * .5 + score_precip * .3) / .8 - penalidade)), 1)
    return {"valor": valor, "confianca": "media", "status": codigo(valor), "detalhes": {
        "score_temp": round(score_temp, 1), "score_precip": round(score_precip, 1),
        "penalidade": round(penalidade, 1), "temp_media": temp, "precip_total": precip_total,
        "precip_equivalente_30dias": round(precip_30dias, 1), "dias_janela": n,
        "referencia": "Faixas experimentais mensais, normalizadas para 30 dias; sem calibração agronômica."}}


def score_solo(tipo_solo, irrigacao):
    # Textura e sistema de irrigação não determinam fertilidade ou aptidão.
    return indisponivel("Textura e irrigação registradas; faltam análise de solo e manejo para pontuar.")


def score_historico(prod_anterior, lat, lon, cultura, tipo_solo, irrigacao, ndvi_max=None):
    # Retirado da decisão: retângulos de estados e médias fixas não estimam a safra.
    return indisponivel("Uma safra isolada e limites estaduais aproximados não sustentam comparação regional.")


def score_risco(analise_obs, resumo_indices, temp_media=None, temp_ideal=None):
    alertas = (analise_obs or {}).get("alertas", [])
    penalidade = 0.
    for alerta in alertas:
        if alerta.get("categoria", "").startswith("sentimento") or alerta.get("categoria", "").endswith("positivo"):
            continue
        if alerta.get("presenca") == "negada" or alerta.get("temporalidade", "atual") != "atual":
            continue
        penalidade += {"alta": 1.5, "media": 1., "baixa": .5}.get(alerta.get("severidade"), .5)
    if not resumo_indices and not alertas:
        return indisponivel("Sem evidências para avaliar riscos; ausência de relato não comprova segurança.")
    secos = resumo_indices.get("dias_consecutivos_secos") or 0
    penalidade += min(max(0, secos - 5) * .2, 2)
    penalidade += min((resumo_indices.get("risco_geada_pct") or 0) / 10, 1.5)
    if temp_media is not None and temp_ideal:
        penalidade += min(max(temp_ideal[0] - temp_media, temp_media - temp_ideal[1], 0), 2)
    valor = round(max(0, 10 - penalidade), 1)
    return {"valor": valor, "confianca": "baixa", "status": codigo(valor),
            "detalhes": {"penalidade_total": round(penalidade, 1), "total_alertas": len(alertas),
                         "motivo": "Triagem baseada em relatos não verificados e dados meteorológicos de modelo."}}


def codigo(valor):
    if valor is None:
        return "SEM_DADOS"
    return "FAVORAVEL" if valor >= 7 else "ATENCAO" if valor >= 5 else "DESFAVORAVEL"


def classificar(valor):
    return {"FAVORAVEL": "Compatibilidade favorável", "ATENCAO": "Atenção", "DESFAVORAVEL": "Compatibilidade desfavorável", "SEM_DADOS": "Dados insuficientes"}[codigo(valor)]


def score_geral(scores):
    validos = {k: v for k, v in (scores or {}).items() if v and v.get("valor") is not None}
    # Exigir clima válido evita que um texto positivo produza recomendação sozinho.
    if "clima" not in validos:
        return {**indisponivel("Dados climáticos insuficientes para síntese."), "classificacao": classificar(None), "scores": {}}
    peso = sum(PESOS[k] for k in validos)
    valor = round(sum(v["valor"] * PESOS[k] for k, v in validos.items()) / peso, 1)
    return {"valor": valor, "classificacao": classificar(valor), "status": codigo(valor), "confianca": "baixa",
            "natureza": "indice_heuristico_nao_validado", "scores": {k: v["valor"] for k, v in validos.items()}}
