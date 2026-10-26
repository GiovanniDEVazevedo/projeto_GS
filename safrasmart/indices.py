"""Indicadores descritivos. Ausência de observação permanece None."""
from datetime import date, timedelta
from .clima import valor_valido


def _valores(dados, campo):
    return [valor_valido(v, campo == "precip") for v in dados.get(campo, [])]


def _media(valores):
    validos = [v for v in valores if v is not None]
    return round(sum(validos) / len(validos), 1) if validos else None


def _temperaturas(dados):
    return [(a + b) / 2 if a is not None and b is not None else None
            for a, b in zip(_valores(dados, "temp_max"), _valores(dados, "temp_min"))]


def recortar_periodo(dados, inicio, fim):
    if not dados or inicio > fim:
        return {"datas": [], "temp_max": [], "temp_min": [], "precip": []}
    por_data = {d: i for i, d in enumerate(dados["datas"])}
    datas = [inicio + timedelta(days=i) for i in range((fim - inicio).days + 1)]
    saida = {"datas": [d.isoformat() for d in datas], "fonte": dados.get("fonte")}
    for campo in ("temp_max", "temp_min", "precip"):
        valores = dados.get(campo, [])
        saida[campo] = [valores[por_data[d]] if d in por_data and por_data[d] < len(valores) else None for d in saida["datas"]]
    return saida


def media_movel_temperatura(dados_climaticos, janela=7):
    if janela < 1:
        raise ValueError("janela deve ser positiva")
    temps = _temperaturas(dados_climaticos)
    return [_media(temps[max(0, i - janela + 1):i + 1]) for i in range(len(temps))]


def precip_acumulada(dados_climaticos, dia_inicio, dia_fim):
    valores = _valores(dados_climaticos, "precip")
    if dia_inicio < 0 or dia_fim >= len(valores) or dia_fim < dia_inicio:
        return None
    fatia = valores[dia_inicio:dia_fim + 1]
    return round(sum(fatia), 1) if fatia and all(v is not None for v in fatia) else None


def dias_consecutivos_secos(dados_climaticos, limiar_mm=0.5):
    valores = _valores(dados_climaticos, "precip")
    datas = dados_climaticos.get("datas", [])
    if not valores or valores[-1] is None:
        return None
    contador = 0
    for i in range(len(valores) - 1, -1, -1):
        if valores[i] is None or valores[i] >= limiar_mm:
            break
        if i < len(valores) - 1 and (date.fromisoformat(datas[i + 1]) - date.fromisoformat(datas[i])).days != 1:
            break
        contador += 1
    return contador


def dias_estresse_termico(dados_climaticos, limite=35.0):
    validos = [v for v in _valores(dados_climaticos, "temp_max") if v is not None]
    return sum(v > limite for v in validos) if validos else None


def risco_geada(dados_climaticos, temp_min_risco=2.0):
    validos = [v for v in _valores(dados_climaticos, "temp_min") if v is not None]
    return round(sum(v <= temp_min_risco for v in validos) * 100 / len(validos), 1) if validos else None


def amplitude_termica(dados_climaticos):
    return [round(a - b, 1) if a is not None and b is not None else None
            for a, b in zip(_valores(dados_climaticos, "temp_max"), _valores(dados_climaticos, "temp_min"))]


def resumo_climatico(dados_climaticos):
    if not dados_climaticos or not dados_climaticos.get("datas"):
        return {}
    n = len(dados_climaticos["datas"])
    temperaturas = _temperaturas(dados_climaticos)
    chuva = _valores(dados_climaticos, "precip")
    precip_validos = [v for v in chuva if v is not None]
    cob_temp = sum(v is not None for v in temperaturas) / n
    cob_precip = len(precip_validos) / n
    return {
        "temp_media_7dias": _media(temperaturas[-7:]),
        "temp_media_geral": _media(temperaturas),
        "precip_total": round(sum(precip_validos), 1) if precip_validos else None,
        "precip_completa": len(precip_validos) == n,
        "dias_consecutivos_secos": dias_consecutivos_secos(dados_climaticos),
        "dias_estresse_termico": dias_estresse_termico(dados_climaticos),
        "risco_geada_pct": risco_geada(dados_climaticos),
        "amplitude_media": _media(amplitude_termica(dados_climaticos)),
        "cobertura_temperatura": round(cob_temp, 3), "cobertura_precipitacao": round(cob_precip, 3),
        "dias_validos_temperatura": sum(v is not None for v in temperaturas),
        "dias_validos_precipitacao": len(precip_validos), "dias_esperados": n,
        "periodo_inicio": dados_climaticos["datas"][0], "periodo_fim": dados_climaticos["datas"][-1],
    }
