"""Fontes meteorológicas com lacunas explícitas e calendário diário alinhado."""
import logging
import math
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

log = logging.getLogger(__name__)


def hoje_local():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).date()


def valor_valido(valor, chuva=False):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        return None
    if valor == -999 or (chuva and valor < 0) or (not chuva and not -90 <= valor <= 65):
        return None
    return float(valor)


def _extrair_dados(dados, fonte="Open-Meteo"):
    diario = dados["daily"]
    datas = diario["time"]
    saida = {"datas": datas, "fonte": fonte}
    for chave, original in [("temp_max", "temperature_2m_max"), ("temp_min", "temperature_2m_min"), ("precip", "precipitation_sum")]:
        valores = diario.get(original, [])
        saida[chave] = [valor_valido(valores[i], chave == "precip") if i < len(valores) else None for i in range(len(datas))]
    return saida


def alinhar_calendario(dados, inicio, fim):
    if not dados:
        return None
    por_data = {}
    for i, texto in enumerate(dados["datas"]):
        dia = date.fromisoformat(texto) if "-" in texto else datetime.strptime(texto, "%Y%m%d").date()
        por_data[dia] = {campo: valor_valido(dados[campo][i], campo == "precip")
                        if i < len(dados.get(campo, [])) else None for campo in ("temp_max", "temp_min", "precip")}
    datas = [inicio + timedelta(days=i) for i in range((fim - inicio).days + 1)]
    saida = {"datas": [d.isoformat() for d in datas], "fonte": dados["fonte"],
             "consultado_em": datetime.now(ZoneInfo("UTC")).isoformat()}
    for campo in ("temp_max", "temp_min", "precip"):
        saida[campo] = [por_data.get(d, {}).get(campo) for d in datas]
    # Máxima menor que mínima é uma observação inválida, não uma amplitude negativa.
    for i, (maxima, minima) in enumerate(zip(saida["temp_max"], saida["temp_min"])):
        if maxima is not None and minima is not None and maxima < minima:
            saida["temp_max"][i] = saida["temp_min"][i] = None
    return saida if any(v is not None for v in saida["temp_max"] + saida["precip"]) else None


def cobertura_completa(dados, inicio, fim):
    if not dados or inicio > fim:
        return False
    indices = [i for i, d in enumerate(dados["datas"]) if inicio.isoformat() <= d <= fim.isoformat()]
    return bool(indices) and len(indices) == (fim - inicio).days + 1 and all(
        i < len(dados.get(c, [])) and valor_valido(dados[c][i], c == "precip") is not None
        for i in indices for c in ("temp_max", "temp_min", "precip"))


def buscar_dados_meteo(lat, lon, dias=365, fim=None, inicio_necessario=None):
    if not 1 <= dias <= 366:
        raise ValueError("dias deve estar entre 1 e 366")
    fim = fim or hoje_local() - timedelta(days=1)
    if isinstance(fim, datetime):
        fim = fim.date()
    fim = min(fim, hoje_local() - timedelta(days=1))
    inicio = fim - timedelta(days=dias - 1)
    # Avaliar a janela usada pela análise, não apenas a existência de algum
    # registro no ano. Uma reanálise pode ter dias recentes ainda indisponíveis.
    necessario = max(inicio, min(inicio_necessario or fim - timedelta(days=29), fim))
    fontes = [("Open-Meteo Archive", lambda: _tentar_archive_api(lat, lon, inicio, fim))]
    if fim >= hoje_local() - timedelta(days=92):
        fontes.append(("Open-Meteo Forecast", lambda: _tentar_forecast_api(lat, lon)))
    fontes.append(("NASA POWER", lambda: _tentar_nasa_api(lat, lon, inicio, fim)))
    resultado = None
    tentativas = []
    campos = ("temp_max", "temp_min", "precip")
    for nome, buscar in fontes:
        try:
            dados = alinhar_calendario(buscar(), inicio, fim)
        except (ValueError, KeyError, TypeError, IndexError, AttributeError):
            log.warning("Calendário meteorológico inválido: %s", nome)
            dados = None
        tentativas.append({"fonte": nome, "status": "recebido" if dados else "indisponivel"})
        if not dados:
            continue
        if resultado is None:
            resultado = {**dados, "fonte_por_dia": [dados["fonte"] if any(dados[c][i] is not None for c in campos) else None
                                                   for i in range(len(dados["datas"]))]}
        else:
            for i in range(len(dados["datas"])):
                antigos = sum(resultado[c][i] is not None for c in campos)
                novos = sum(dados[c][i] is not None for c in campos)
                if novos > antigos:
                    # Usar uma fonte por dia, sem misturar máxima de um modelo
                    # com mínima de outro nem somar chuvas de fontes diferentes.
                    for campo in campos:
                        resultado[campo][i] = dados[campo][i]
                    resultado["fonte_por_dia"][i] = dados["fonte"]
        if cobertura_completa(resultado, necessario, fim):
            break
    if resultado:
        resultado["fontes_utilizadas"] = list(dict.fromkeys(f for f in resultado["fonte_por_dia"] if f))
        resultado["fonte"] = " + ".join(resultado["fontes_utilizadas"])
        resultado["tentativas_fontes"] = tentativas
    return resultado


def _consultar(url, params, fonte, nasa=False):
    try:
        resposta = requests.get(url, params=params, timeout=(3, 20 if nasa else 15))
        resposta.raise_for_status()
        dados = resposta.json()
        if not nasa:
            return _extrair_dados(dados, fonte)
        parametros = dados["properties"]["parameter"]
        datas = sorted(set().union(*(parametros.get(k, {}) for k in ("T2M_MAX", "T2M_MIN", "PRECTOTCORR"))))
        saida = {"datas": datas, "fonte": fonte}
        for chave, original in [("temp_max", "T2M_MAX"), ("temp_min", "T2M_MIN"), ("precip", "PRECTOTCORR")]:
            saida[chave] = [valor_valido(parametros.get(original, {}).get(d), chave == "precip") for d in datas]
        return saida
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError) as erro:
        resposta_erro = getattr(erro, "response", None)
        codigo = getattr(resposta_erro, "status_code", None)
        log.warning("Fonte meteorológica indisponível: %s (HTTP %s; %s)", fonte, codigo or "sem resposta", type(erro).__name__)
        return None


def _tentar_archive_api(lat, lon, inicio, fim):
    return _consultar("https://archive-api.open-meteo.com/v1/archive", {
        "latitude": lat, "longitude": lon, "start_date": inicio.isoformat(), "end_date": fim.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum", "timezone": "America/Sao_Paulo"
    }, "Open-Meteo Archive")


def _tentar_nasa_api(lat, lon, inicio, fim):
    return _consultar("https://power.larc.nasa.gov/api/temporal/daily/point", {
        "latitude": lat, "longitude": lon, "start": inicio.strftime("%Y%m%d"), "end": fim.strftime("%Y%m%d"),
        "parameters": "T2M_MAX,T2M_MIN,PRECTOTCORR", "community": "AG", "format": "JSON"
    }, "NASA POWER", nasa=True)


def _tentar_forecast_api(lat, lon):
    return _consultar("https://api.open-meteo.com/v1/forecast", {
        "latitude": lat, "longitude": lon, "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "America/Sao_Paulo", "past_days": 92, "forecast_days": 1,
    }, "Open-Meteo Forecast (histórico recente de modelo)")


def coordenadas():
    from .validacao import EntradaInvalida, numero
    while True:
        try:
            return numero(input("Latitude: "), "lat", -90, 90), numero(input("Longitude: "), "lon", -180, 180)
        except EntradaInvalida as erro:
            print(erro)


def resumo(dados):
    from .indices import resumo_climatico
    print(resumo_climatico(dados) if dados else "Nenhum dado disponível.")
