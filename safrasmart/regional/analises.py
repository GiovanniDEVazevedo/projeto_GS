"""Indicadores por janela e comparações descritivas da mesma série climática."""

from datetime import date, timedelta
from math import sqrt
from statistics import mean, median, pstdev


def janela(serie, fim, tamanho):
    inicio = fim - timedelta(days=tamanho - 1)
    dados = [serie.get((inicio + timedelta(days=i)).isoformat(), {}) for i in range(tamanho)]
    chuvas = [d["chuva_mm"] for d in dados if d.get("chuva_mm") is not None]
    temperaturas = [(d["temp_min"] + d["temp_max"]) / 2 for d in dados
                    if d.get("temp_min") is not None and d.get("temp_max") is not None]
    maximas = [d["temp_max"] for d in dados if d.get("temp_max") is not None]
    return {
        "inicio": inicio.isoformat(), "fim": fim.isoformat(), "dias": tamanho,
        "chuva_mm": round(sum(chuvas), 2) if len(chuvas) == tamanho else None,
        "chuva_parcial_mm": round(sum(chuvas), 2) if 0 < len(chuvas) < tamanho else None,
        "dias_chuva": len(chuvas), "dias_secos": sum(v < 1 for v in chuvas) if len(chuvas) == tamanho else None,
        "temp_media_c": round(mean(temperaturas), 2) if len(temperaturas) == tamanho else None,
        "dias_temperatura": len(temperaturas),
        "dias_maxima_35c": sum(v >= 35 for v in maximas) if len(maximas) == tamanho else None,
    }


def ordenar_por_distancia(atual, anteriores, campos):
    escalas = {c: pstdev([r[c] for r in anteriores]) or 1 for c in campos}
    casos = [{**r, "distancia": round(sqrt(sum(((r[c] - atual[c]) / escalas[c]) ** 2 for c in campos)), 4)}
             for r in anteriores]
    return sorted(casos, key=lambda r: (r["distancia"], r["fim"]))


def anos_analogos(serie, fim, tamanho=30):
    atual = janela(serie, fim, tamanho)
    campos = ["chuva_mm"]
    if atual["temp_media_c"] is not None:
        campos.append("temp_media_c")
    if atual["chuva_mm"] is None:
        return {"status": "janela_incompleta", "amostras": 0, "casos": []}
    anteriores = []
    for ano in sorted({int(dia[:4]) for dia in serie if int(dia[:4]) < fim.year}):
        if fim.month == 2 and fim.day == 29:
            try:
                anterior = date(ano, 2, 29)
            except ValueError:
                continue
        else:
            anterior = date(ano, fim.month, fim.day)
        candidato = janela(serie, anterior, tamanho)
        if all(candidato[c] is not None for c in campos):
            anteriores.append(candidato)
    if len(anteriores) < 3:
        return {"status": "amostra_pequena", "amostras": len(anteriores), "casos": []}
    anomalias = {c: round(atual[c] - median([r[c] for r in anteriores]), 2) for c in campos}
    casos = ordenar_por_distancia(atual, anteriores, campos)
    baseline = min(anteriores, key=lambda r: (abs(r["chuva_mm"] - atual["chuva_mm"]), r["fim"]))
    return {
        "status": "disponivel", "amostras": len(anteriores), "campos": campos, "casos": casos[:3],
        "janela_atual": atual, "anomalias_mediana": anomalias, "referencia_apenas_chuva": baseline["fim"],
        "limitacao": "Compara janelas do mesmo calendário na mesma série. São analogias climáticas regionais.",
    }


def balanco_hidrico(serie, inicio, fim, parametros):
    if not parametros:
        return {"status": "parametros_ausentes"}
    capacidade = parametros["cad_mm"]
    estoque = parametros["armazenamento_inicial_mm"]
    dias = []
    cursor = inicio
    while cursor <= fim:
        data = cursor.isoformat()
        dia = serie.get(data, {})
        chuva, et0 = dia.get("chuva_mm"), dia.get("et0_mm")
        irrigacao = parametros.get("irrigacao_diaria_mm", {}).get(data)
        if parametros["sequeiro"]:
            irrigacao = 0
        if None in (chuva, et0, irrigacao):
            return {"status": "dados_diarios_incompletos", "dia_faltante": data}
        etc = et0 * parametros["kc"]
        saldo = estoque + chuva + irrigacao - etc
        estoque = max(0, min(capacidade, saldo))
        dias.append({"data": data, "chuva_mm": chuva, "irrigacao_mm": irrigacao, "et0_mm": et0,
                     "etc_mm": round(etc, 2), "armazenamento_mm": round(estoque, 2),
                     "excedente_mm": round(max(0, saldo - capacidade), 2),
                     "demanda_nao_atendida_mm": round(max(0, -saldo), 2)})
        cursor += timedelta(days=1)
    return {
        "status": "estimativa", "inicio": inicio.isoformat(), "fim": fim.isoformat(), "dias": dias,
        "cad_mm": capacidade, "kc": parametros["kc"],
        "armazenamento_final_mm": round(estoque, 2),
        "limitacao": "Estimativa diária com parâmetros informados e precipitação/ET₀ de modelo. "
                     "O excedente e a demanda não atendida são indicadores para investigação.",
    }
