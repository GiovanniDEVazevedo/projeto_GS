"""Normalização de séries regionais diárias, com lacunas preservadas."""

import csv
import io
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from math import isfinite

import requests

from ..observacao import normalizar

ARQUIVO = "https://archive-api.open-meteo.com/v1/archive"
MODELO_ARQUIVO = "era5"
RECORTE_ARQUIVO = "open-meteo-" + MODELO_ARQUIVO
CHIRPS_GEE = "UCSB-CHC/CHIRPS/V3/DAILY_RNL"
CHIRPS = "https://www.chc.ucsb.edu/data/chirps3"
INMET = "https://portal.inmet.gov.br/dadoshistoricos"
CAMPOS = {"temp_max": "temperature_2m_max", "temp_min": "temperature_2m_min",
          "chuva_mm": "precipitation_sum", "et0_mm": "et0_fao_evapotranspiration"}


def valor_diario(valor, minimo=0, maximo=2_000):
    if valor is None or valor == "":
        return None
    if isinstance(valor, bool):
        raise ValueError("Valor diário inválido.")
    numero = float(str(valor).replace(",", "."))
    if numero == -9999:
        return None
    if not isfinite(numero) or not minimo <= numero <= maximo:
        raise ValueError("Valor diário fora da faixa esperada.")
    return numero


def dados_open_meteo(resposta):
    unidades = resposta["daily_units"]
    diaria = resposta["daily"]
    dias = diaria["time"]
    if len(set(dias)) != len(dias) or not dias:
        raise ValueError("O arquivo climático contém datas ausentes ou duplicadas.")
    for campo, api in CAMPOS.items():
        unidade = "°C" if campo.startswith("temp") else "mm"
        if unidades.get(api) != unidade or len(diaria[api]) != len(dias):
            raise ValueError(f"Série ou unidade inesperada para {api}.")
    resultado = {}
    for i, dia in enumerate(dias):
        data = date.fromisoformat(dia).isoformat()
        valores = {k: valor_diario(diaria[v][i], -90 if k.startswith("temp") else 0,
                                  65 if k.startswith("temp") else 2_000) for k, v in CAMPOS.items()}
        if None not in (valores["temp_min"], valores["temp_max"]) and valores["temp_min"] > valores["temp_max"]:
            raise ValueError("Temperatura mínima acima da máxima.")
        resultado[data] = valores
    return resultado


def baixar_open_meteo(lat, lon, inicio, fim):
    resposta = requests.get(ARQUIVO, params={
        "latitude": lat, "longitude": lon, "start_date": inicio.isoformat(), "end_date": fim.isoformat(),
        "daily": ",".join(CAMPOS.values()), "models": MODELO_ARQUIVO, "timezone": "UTC",
    }, timeout=(10, 55))
    resposta.raise_for_status()
    dados = resposta.json()
    if dados.get("timezone") not in {"UTC", "GMT"}:
        raise ValueError("O arquivo Open-Meteo precisa fornecer dias em UTC.")
    serie = dados_open_meteo(dados)
    if set(serie) != {(inicio + timedelta(days=i)).isoformat() for i in range((fim - inicio).days + 1)}:
        raise ValueError("O arquivo Open-Meteo não cobre as datas solicitadas.")
    if any(not any(d[campo] is not None for d in serie.values()) for campo in CAMPOS):
        raise ValueError("O modelo retornou uma variável totalmente ausente.")
    return serie, {"lat": dados["latitude"], "lon": dados["longitude"], "altitude_m": dados.get("elevation")}


def ler_chirps_csv(arquivo):
    leitor = csv.DictReader(arquivo)
    if not {"data", "precipitacao_mm"}.issubset(leitor.fieldnames or []):
        raise ValueError("O recorte CHIRPS deve ter as colunas data,precipitacao_mm.")
    dias = {}
    for linha in leitor:
        dia = date.fromisoformat(linha["data"]).isoformat()
        if dia in dias:
            raise ValueError("O recorte CHIRPS contém datas duplicadas.")
        dias[dia] = {"chuva_mm": valor_diario(linha["precipitacao_mm"])}
    if not dias:
        raise ValueError("Recorte CHIRPS vazio.")
    return dias


def baixar_chirps_gee(lat, lon, inicio, fim):
    import ee
    from ..ndvi import autenticar_gee

    autenticar_gee()
    ponto = ee.Geometry.Point([lon, lat])
    fonte = ee.ImageCollection(CHIRPS_GEE).select("precipitation")
    cursor = inicio
    dias = {}
    while cursor <= fim:
        final = min(fim + timedelta(days=1), date(cursor.year + 1, 1, 1))
        linhas = fonte.filterDate(cursor.isoformat(), final.isoformat()).getRegion(ponto, 5566).getInfo()
        if linhas and len(linhas) > 1:
            indices = {nome: i for i, nome in enumerate(linhas[0])}
            for linha in linhas[1:]:
                dia = datetime.fromtimestamp(linha[indices["time"]] / 1000, tz=timezone.utc).date().isoformat()
                if dia in dias:
                    raise ValueError("A extração CHIRPS retornou mais de uma amostra por dia.")
                dias[dia] = {"chuva_mm": valor_diario(linha[indices["precipitation"]])}
        cursor = final
    if not dias:
        raise ValueError("Sem amostras CHIRPS no período.")
    return dias


def ler_inmet(conteudo):
    try:
        texto = conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = conteudo.decode("latin-1")
    linhas = iter(csv.reader(io.StringIO(texto), delimiter=";"))
    meta = {}
    for linha in linhas:
        if not linha:
            continue
        titulo = normalizar(linha[0]).strip(" :")
        if titulo.startswith("data"):
            cabecalho = [normalizar(c).replace("(", "").replace(")", "").strip() for c in linha]
            break
        if len(linha) >= 2:
            meta[titulo] = linha[1].strip()
    else:
        raise ValueError("Arquivo de estação INMET sem cabeçalho horário.")
    prefixos = {"data": "data", "hora": "hora utc", "chuva_mm": "precipitacao total, horario",
                "temp_max": "temperatura maxima na hora ant", "temp_min": "temperatura minima na hora ant"}
    colunas = {}
    for nome, prefixo in prefixos.items():
        colunas[nome] = next((i for i, c in enumerate(cabecalho) if c.startswith(prefixo)), None)
        if colunas[nome] is None:
            raise ValueError(f"Coluna INMET ausente: {nome}.")
    horas = defaultdict(dict)
    for linha in linhas:
        if not linha or not linha[0].strip():
            continue
        if len(linha) <= max(colunas.values()):
            raise ValueError("Linha INMET incompleta.")
        data = date.fromisoformat(linha[colunas["data"]].replace("/", "-"))
        horario = linha[colunas["hora"]].replace("UTC", "").replace(":", "").strip()
        if len(horario) != 4 or not horario.isdecimal() or horario[2:] != "00" or not 0 <= int(horario[:2]) <= 23:
            raise ValueError("Horário INMET fora do padrão de hora UTC.")
        # As medições horárias resumem a hora que termina no horário registrado.
        instante = datetime(data.year, data.month, data.day, int(horario[:2])) - timedelta(hours=1)
        dia = horas[instante.date().isoformat()]
        if instante.hour in dia:
            raise ValueError("Arquivo INMET contém horas duplicadas.")
        dia[instante.hour] = {k: valor_diario(linha[colunas[k]].strip(), -90 if k.startswith("temp") else 0,
                                           65 if k.startswith("temp") else 2_000)
                             for k in ("chuva_mm", "temp_min", "temp_max")}
    diaria = {}
    for data, amostras in horas.items():
        diaria[data] = {}
        for campo, agregar in (("chuva_mm", sum), ("temp_min", min), ("temp_max", max)):
            valores = [a[campo] for a in amostras.values()]
            diaria[data][campo] = agregar(valores) if len(valores) == 24 and None not in valores else None
    estacao = meta.get("codigo (wmo)") or meta.get("codigo wmo")
    if not diaria or not estacao or not meta.get("latitude") or not meta.get("longitude"):
        raise ValueError("Informe o CSV horário oficial de uma estação INMET com código e coordenadas.")
    return diaria, {"estacao": estacao, "lat": valor_diario(meta["latitude"], -90, 90),
                    "lon": valor_diario(meta["longitude"], -180, 180),
                    "altitude_m": valor_diario(meta.get("altitude"), -500, 9_000)}
