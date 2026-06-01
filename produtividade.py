ESTADOS = [
    ("MT", "Mato Grosso",        -18.0,  -7.0,  -62.0, -50.0,   84, 107),
    ("PR", "Parana",              -26.5, -22.5,  -54.5, -48.0,   74, 110),
    ("GO", "Goias",               -19.5, -12.5,  -53.0, -45.5,   82, 107),
    ("MS", "Mato Grosso do Sul",  -24.0, -17.0,  -58.0, -50.5,   70, 107),
    ("MG", "Minas Gerais",        -23.0, -14.0,  -51.0, -39.5,   71,  71),
    ("RS", "Rio Grande do Sul",   -33.5, -27.0,  -57.5, -49.5,   56,  53),
    ("SP", "Sao Paulo",           -25.5, -19.5,  -53.0, -44.0,   73,  73),
    ("BA", "Bahia",               -18.5,  -8.5,  -47.0, -37.0,   59,  58),
    ("SC", "Santa Catarina",      -29.5, -25.5,  -53.0, -48.5,   94,  94),
    ("TO", "Tocantins",           -13.5,  -5.0,  -50.5, -45.5,   67,  67),
    ("MA", "Maranhao",            -11.0,  -2.5,  -47.5, -41.0,   66,  66),
    ("PI", "Piaui",               -11.0,  -2.5,  -46.0, -40.5,   53,  53),
    ("RO", "Rondonia",            -14.0,  -7.5,  -67.0, -59.5,   73,  73),
    ("PA", "Para",                -16.0,  -1.0,  -56.0, -46.0,   56,  56),
    ("DF", "Distrito Federal",    -16.0, -15.5,  -48.0, -47.5,   82, 107),
]
FATOR_SOLO = {
    "argiloso": 1.10,
    "misto": 1.00,
    "arenoso": 0.85
}
FATOR_IRRIGACAO = {
    "gotejo": 1.15,
    "aspersao": 1.08,
    "sequeiro": 1.00
}
def identificar_estado(lat, lon):
    for sigla, nome,lat_min, lat_max, lon_min, lon_max, soja,milho in ESTADOS:
        if lat_min <= lat <=lat_max and lon_min <= lon <= lon_max:
            return sigla, nome, soja,milho
    return "BR", "Media Nacional", 60 , 107
def potencial_ajustado(lat, lon, cultura,tipo_solo,irrigacao, ndvi_max=None):
    sigla , nome, soja , milho = identificar_estado(lat , lon)
    base = soja if cultura == "soja" else milho
    base *= FATOR_SOLO.get(tipo_solo , 1.00)
    base *= FATOR_IRRIGACAO.get(irrigacao , 1.00)
    if ndvi_max is not None:
        if ndvi_max > 0.7:
            base *= 1.10
        elif ndvi_max < 0.3:
            base *= 0.90
    return {
        "sigla": sigla,
        "estado": nome,
        "cultura": cultura,
        "potencial_base": round(base, 1),
        "produtividade_esperada": round(base, 1),
        "fonte": "CONAB 2024/25"
    }
if __name__ == "__main__":
    exemplos = [
        (-24.95, -53.46, "soja", "argiloso", "gotejo", 0.75),
        (-23.55, -46.63, "milho", "arenoso", "aspersao", 0.45),
        (-15.78, -47.93, "soja", "misto", "sequeiro", None),
        (-30.03, -51.23, "soja", "argiloso", "aspersao", 0.82),
    ]
    for lat, lon, cult, solo, irrig, ndvi in exemplos:
        res = potencial_ajustado(lat, lon, cult, solo, irrig, ndvi)
        print(f"{res['estado']:20s} | {cult:6s} | {res['potencial_base']:5.1f} sc/ha | {res['fonte']}")
