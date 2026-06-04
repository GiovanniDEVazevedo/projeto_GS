import ee
from google.oauth2 import service_account
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import sys

def autenticar_gee(caminho_chave):
    credentials = service_account.Credentials.from_service_account_file(caminho_chave)
    scoped = credentials.with_scopes(["https://www.googleapis.com/auth/earthengine"])
    ee.Initialize(scoped)
    print("  [NDVI] Earth Engine autenticado")

def _executar_ndvi(lat, lon, data_inicio, data_fim, intervalo_dias, buffer_metros):
    ponto = ee.Geometry.Point([lon, lat]).buffer(buffer_metros)
    colecao = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    datas_ndvi = []
    valores_ndvi = []
    total_imagens = 0
    data_atual = data_inicio
    while data_atual < data_fim:
        data_fim_intervalo = data_atual + timedelta(days=intervalo_dias)
        if data_fim_intervalo > data_fim:
            data_fim_intervalo = data_fim
        intervalo = colecao \
            .filterBounds(ponto) \
            .filterDate(data_atual.strftime("%Y-%m-%d"), data_fim_intervalo.strftime("%Y-%m-%d")) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
        n_imagens = intervalo.size().getInfo()
        total_imagens += n_imagens
        if n_imagens == 0:
            data_atual = data_fim_intervalo
            continue
        composite = intervalo.median().clip(ponto)
        ndvi = composite.normalizedDifference(['B8', 'B4']).rename('NDVI')
        estatisticas = ndvi.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=ponto,
            scale=10,
            maxPixels=1e9
        )
        ndvi_valor = estatisticas.getInfo().get('NDVI', None)
        if ndvi_valor is not None:
            datas_ndvi.append(data_fim_intervalo.strftime("%Y-%m-%d"))
            valores_ndvi.append(round(float(ndvi_valor), 3))
        data_atual = data_fim_intervalo
    if not valores_ndvi:
        return None
    return {
        "datas": datas_ndvi,
        "ndvi": valores_ndvi,
        "ndvi_medio_geral": round(sum(valores_ndvi) / len(valores_ndvi), 3),
        "ndvi_max": round(max(valores_ndvi), 3),
        "ndvi_min": round(min(valores_ndvi), 3),
        "total_imagens_usadas": total_imagens,
        "fonte": "Sentinel-2 SR Harmonized"
    }

def buscar_ndvi(lat, lon, data_inicio, data_fim, intervalo_dias=15, buffer_metros=50, timeout_segundos=90):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_executar_ndvi, lat, lon, data_inicio, data_fim, intervalo_dias, buffer_metros)
        try:
            resultado = future.result(timeout=timeout_segundos)
            return resultado
        except TimeoutError:
            print("  [NDVI] Timeout de %ds excedido — continuando sem NDVI" % timeout_segundos)
            return None
def ndvi_por_fase(dados_ndvi, data_plantio, fases):
    if not dados_ndvi:
        return {}
    resultado = {}
    for nome_fase, (d_inicio,d_fim) in fases.items():
        data_inicio_fase=data_plantio + timedelta(days=d_inicio)
        data_fim_fase = data_plantio + timedelta(days=d_fim)

        ndvis_fase = []
        for i, data_str in enumerate(dados_ndvi["datas"]):
            data = datetime.strptime(data_str, "%Y-%m-%d")
            if data_inicio_fase <= data <= data_fim_fase:
                ndvis_fase.append(dados_ndvi["ndvi"][i])
        if ndvis_fase:
            resultado[nome_fase] = round(sum(ndvis_fase) / len(ndvis_fase), 3)
        else:
            resultado[nome_fase] = None
    return resultado
if __name__ == "__main__":
    import os

    caminho_chave = os.environ.get("GEE_KEY_PATH", "./.env/calcium-pod-497417-t0-5d27a8d8dba9.json")
    autenticar_gee(caminho_chave)

    # Exemplo: soja em Cascavel/PR, plantio em 15/10/2025
    lat = -24.95
    lon = -53.46
    plantio = datetime(2025, 10, 15)
    hoje = datetime.now()

    dados_ndvi = buscar_ndvi(lat, lon, plantio, hoje)

    if dados_ndvi:
        print(f"\n--- NDVI Sentinel-2 ---")
        print(f"Periodo: {dados_ndvi['datas'][0]} a {dados_ndvi['datas'][-1]}")
        print(f"NDVI medio geral: {dados_ndvi['ndvi_medio_geral']}")
        print(f"NDVI max: {dados_ndvi['ndvi_max']}")
        print(f"NDVI min: {dados_ndvi['ndvi_min']}")
        print(f"Imagens usadas: {dados_ndvi['total_imagens_usadas']}")
        print(f"Fonte: {dados_ndvi['fonte']}")

        # Testar com fases da soja
        fases_soja = {
            "VE-V3": (0, 20),
            "V4-V6": (20, 40),
            "R1-R2": (40, 55),
            "R3-R5": (55, 90),
            "R6-R8": (90, 120)
        }
        ndvi_fases = ndvi_por_fase(dados_ndvi, plantio, fases_soja)
        print("\nNDVI por fase fenologica:")
        for fase, valor in ndvi_fases.items():
            status = "ok" if valor else "sem dados"
            print(f"  {fase}: {valor} ({status})")
