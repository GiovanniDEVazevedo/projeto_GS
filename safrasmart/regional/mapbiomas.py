"""Estimativas de granulometria da Coleção 3 do MapBiomas Solo."""

from .clima import valor_diario

URL = "https://brasil.mapbiomas.org/iniciativas-e-produtos/solo/granulometria/"
ASSETS = "projects/mapbiomas-public/assets/brazil/soil/collection3/"
FRACOES = {"argila": "clay", "silte": "silt", "areia": "sand"}


def amostrar_solo(lat, lon, profundidade):
    import ee
    from ..ndvi import autenticar_gee

    if profundidade not in range(0, 100, 10):
        raise ValueError("Escolha uma camada de 10 cm entre 0 e 100 cm.")
    autenticar_gee()
    imagens = []
    for rotulo, fracao in FRACOES.items():
        colecao = f"{ASSETS}mapbiomas_brazil_collection3_soil_{fracao}_fraction_v1"
        imagem = f"{fracao}_fraction_{profundidade:03d}_{profundidade + 10:03d}_v1"
        imagens.append(ee.Image(f"{colecao}/{imagem}").select([0]).rename(rotulo))
    leitura = ee.Image.cat(*imagens).reduceRegion(
        reducer=ee.Reducer.first(), geometry=ee.Geometry.Point([lon, lat]), scale=30, maxPixels=64
    ).getInfo()
    fracoes = {chave: valor_diario(leitura.get(chave), 0, 100) for chave in FRACOES}
    if all(valor is None for valor in fracoes.values()):
        raise ValueError("MapBiomas Solo sem cobertura no ponto escolhido.")
    return {"profundidade_cm": [profundidade, profundidade + 10], "fracoes_pct": fracoes,
            "resolucao_m": 30, "ano_referencia": 1990}
