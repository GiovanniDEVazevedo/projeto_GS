"""Validação dos limites de talhões desenhados em coordenadas WGS84."""

from math import cos, radians

from shapely.affinity import scale
from shapely.geometry import Polygon


def poligono_talhao(geojson):
    if not isinstance(geojson, dict) or geojson.get("type") != "Polygon":
        raise ValueError("Desenhe um polígono para o talhão.")
    aneis = geojson.get("coordinates")
    if not isinstance(aneis, list) or len(aneis) != 1:
        raise ValueError("O talhão deve ter um contorno único.")
    anel = aneis[0]
    if not isinstance(anel, list) or not 4 <= len(anel) <= 501:
        raise ValueError("Use de 3 a 500 vértices no talhão.")
    pontos = []
    for par in anel:
        if not isinstance(par, list) or len(par) != 2 or any(type(valor) not in (int, float) for valor in par):
            raise ValueError("Coordenadas do talhão inválidas.")
        lon, lat = par
        if not -180 <= lon <= 180 or not -85 <= lat <= 85:
            raise ValueError("Coordenadas do talhão fora da faixa do mapa.")
        pontos.append([round(lon, 7), round(lat, 7)])
    if pontos[0] != pontos[-1] or len(set(map(tuple, pontos[:-1]))) != len(pontos) - 1:
        raise ValueError("Feche o contorno e remova vértices repetidos.")
    poligono = Polygon(pontos)
    oeste, sul, leste, norte = poligono.bounds
    if not poligono.is_valid or leste - oeste > .3 or norte - sul > .3:
        raise ValueError("O contorno se cruza ou tem extensão excessiva.")
    centro = poligono.centroid
    # Aproximação local suficiente para informar a área de talhões pequenos.
    area = scale(poligono, xfact=111_320 * cos(radians(centro.y)), yfact=111_320).area / 10_000
    if not .001 <= area <= 5_000:
        raise ValueError("A área do talhão deve estar entre 0,001 e 5.000 ha.")
    referencia = centro if poligono.covers(centro) else poligono.representative_point()
    return {
        "geometria": {"type": "Polygon", "coordinates": [pontos]},
        "lat": referencia.y, "lon": referencia.x, "area_ha": round(area, 3),
    }
