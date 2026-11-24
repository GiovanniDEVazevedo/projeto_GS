"""Sentinel-2: máscara SCL por pixel, cobertura e uma única avaliação remota."""
import multiprocessing as mp
import os
from datetime import datetime, timedelta

from .credenciais_gee import carregar_dados_gee, gee_configurado


def autenticar_gee(caminho_chave=None):
    dados = carregar_dados_gee(caminho_chave)
    projeto = os.getenv("GEE_PROJECT", "").strip() or dados.get("project_id")
    if not isinstance(projeto, str) or not projeto.strip():
        raise RuntimeError("Defina GEE_PROJECT ou use um JSON com project_id.")
    import ee
    from google.oauth2 import service_account
    try:
        credentials = service_account.Credentials.from_service_account_info(dados,
            scopes=["https://www.googleapis.com/auth/earthengine"])
    except (ValueError, TypeError):
        raise RuntimeError("Credencial GEE inválida. Verifique o JSON e a chave privada da conta de serviço.") from None
    ee.Initialize(credentials, project=projeto.strip())
    ee.data.setDeadline(80000)
    ee.data.setMaxRetries(1)


def _executar_ndvi(lat, lon, data_inicio, data_fim, intervalo_dias, buffer_metros, geometria):
    import ee
    area = (ee.Geometry.Polygon(geometria["coordinates"], proj="EPSG:4326", geodesic=False)
            if geometria else ee.Geometry.Point([lon, lat]).buffer(buffer_metros))

    def mascarar(imagem):
        scl = imagem.select("SCL")
        valido = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6))
        return imagem.updateMask(valido).normalizedDifference(["B8", "B4"]).rename("NDVI").copyProperties(imagem, ["system:time_start"])

    colecao = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(area)
               .filterDate(data_inicio.isoformat(), data_fim.isoformat())
               .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80)).map(mascarar))
    quantidade = (data_fim - data_inicio).days
    inicios = ee.List.sequence(0, quantidade - 1, intervalo_dias)
    inicio_ee = ee.Date(data_inicio.isoformat())
    fim_ee = ee.Date(data_fim.isoformat())

    def compor(deslocamento):
        inicio = inicio_ee.advance(deslocamento, "day")
        fim = ee.Date(inicio.advance(intervalo_dias, "day").millis().min(fim_ee.millis()))
        imagens = colecao.filterDate(inicio, fim)
        n = imagens.size()
        vazia = ee.Image.constant(0).rename("NDVI").updateMask(ee.Image.constant(0))
        composite = ee.Image(ee.Algorithms.If(n.gt(0), imagens.median(), vazia))
        cobertura = composite.mask().unmask(0, sameFootprint=False).rename("valido")
        stats = composite.addBands(cobertura).reduceRegion(
            reducer=ee.Reducer.mean().combine(ee.Reducer.count(), sharedInputs=True),
            geometry=area, crs="EPSG:6933", scale=10, maxPixels=1000000)
        ultima = ee.Algorithms.If(n.gt(0), ee.Date(imagens.aggregate_max("system:time_start")).format("YYYY-MM-dd"), "")
        return ee.Feature(None, {"inicio": inicio.format("YYYY-MM-dd"), "fim_exclusivo": fim.format("YYYY-MM-dd"),
            "data_ultima_cena": ultima, "cenas": n, "ndvi": stats.get("NDVI_mean"),
            "cobertura": stats.get("valido_mean"), "pixels_validos": stats.get("NDVI_count")})

    features = ee.FeatureCollection(inicios.map(compor)).getInfo()["features"]
    minimo = float(os.getenv("MIN_NDVI_COVERAGE", "0.5"))
    todas = [feature["properties"] for feature in features]
    janelas = [p for p in todas if p.get("ndvi") is not None and (p.get("cobertura") or 0) >= minimo
               and (p.get("pixels_validos") or 0) >= (4 if geometria else 1)]
    if not janelas:
        return None
    valores = [round(p["ndvi"], 3) for p in janelas]
    return {"datas": [p["data_ultima_cena"] for p in janelas], "ndvi": valores,
            "cobertura_pixels_validos": [round(p["cobertura"], 3) for p in janelas],
            "janelas": janelas, "janelas_avaliadas": len(todas), "cobertura_minima": minimo,
            "ndvi_medio_geral": round(sum(valores) / len(valores), 3),
            "ndvi_max": max(valores), "ndvi_min": min(valores),
            "total_imagens_usadas": sum(p["cenas"] for p in janelas),
            "fonte": "Sentinel-2 SR Harmonized", "mascara": "SCL classes 4, 5 e 6",
            "buffer_metros": None if geometria else buffer_metros}


def _ndvi_filho(canal, args):
    try:
        autenticar_gee()
        canal.send({"resultado": _executar_ndvi(*args)})
    except Exception:
        # Nunca devolver mensagem que possa incluir o conteúdo da chave privada.
        canal.send({"erro": "Falha na consulta ao Earth Engine."})
    finally:
        canal.close()


def buscar_ndvi(lat, lon, data_inicio, data_fim, intervalo_dias=15, buffer_metros=50, timeout_segundos=90,
                *, geometria=None):
    if data_inicio >= data_fim:
        return None
    if intervalo_dias < 1 or (data_fim - data_inicio).days > 730 or not 1 <= buffer_metros <= 1000:
        raise ValueError("Período, intervalo ou área NDVI fora dos limites.")
    if not gee_configurado():
        raise RuntimeError("Configure GEE_SERVICE_ACCOUNT_JSON ou GEE_KEY_PATH no .env.")
    contexto = mp.get_context("spawn")
    receber, enviar = contexto.Pipe(duplex=False)
    args = (lat, lon, data_inicio, data_fim, intervalo_dias, buffer_metros, geometria)
    processo = contexto.Process(target=_ndvi_filho, args=(enviar, args))
    processo.start()
    enviar.close()
    try:
        if not receber.poll(timeout_segundos):
            raise TimeoutError("NDVI excedeu o tempo máximo.")
        try:
            resposta = receber.recv()
        except EOFError:
            raise RuntimeError("Processamento NDVI interrompido.") from None
        if resposta.get("erro"):
            raise RuntimeError(resposta["erro"])
        return resposta["resultado"]
    finally:
        receber.close()
        processo.join(timeout=1)
        if processo.is_alive():
            processo.terminate()
            processo.join(timeout=3)
        if processo.is_alive():
            processo.kill()
            processo.join()


def ndvi_por_fase(dados_ndvi, data_plantio, fases):
    if not dados_ndvi:
        return {}
    resultado = {}
    for nome, (inicio, fim) in fases.items():
        valores = [valor for texto, valor in zip(dados_ndvi["datas"], dados_ndvi["ndvi"])
                   if inicio <= (datetime.fromisoformat(texto) - data_plantio).days < fim]
        resultado[nome] = round(sum(valores) / len(valores), 3) if valores else None
    return resultado
