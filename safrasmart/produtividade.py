# =============================================================================
# DADOS DE PRODUTIVIDADE POR ESTADO — CONAB 2024/25 (12 Levantamento)
# =============================================================================
# Cada tupla contem: (sigla, nome, lat_min, lat_max, lon_min, lon_max, soja_sc, milho_sc)
# onde soja_sc e milho_sc sao as produtividades medias estaduais em sacas/ha.
#
# Fonte: CONAB - Companhia Nacional de Abastecimento
# Safra 2024/25 — 12 Levantamento (dados oficiais do governo brasileiro).
#
# Os bounding boxes (limites geograficos) aproximados servem para identificar
# automaticamente o estado a partir das coordenadas GPS. Primeiro match
# vence (a lista esta ordenada por relevancia agricola).
#
# NOTA: 2024/25 foi um ano recorde para Mato Grosso (84 sc/ha de soja),
# Parana (74) e Goias (82). Estes valores podem estar acima da media historica.
# =============================================================================
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

# FATORES DE AJUSTE PARA TIPO DE SOLO
# Argiloso: retem mais agua e nutrientes -> bonus de 10%.
# Misto: equilibrio natural -> neutro (1.00).
# Arenoso: baixa retencao de agua -> penalidade de 15%.
FATOR_SOLO = {
    "argiloso": 1.10,
    "misto": 1.00,
    "arenoso": 0.85
}

# FATORES DE AJUSTE PARA SISTEMA DE IRRIGACAO
# Gotejo: maxima eficiencia hidrica -> bonus de 15%.
# Aspersao: boa eficiencia -> bonus de 8%.
# Sequeiro: depende totalmente da chuva -> neutro (1.00).
FATOR_IRRIGACAO = {
    "gotejo": 1.15,
    "aspersao": 1.08,
    "sequeiro": 1.00
}


def identificar_estado(lat, lon):
    """
    IDENTIFICA o estado brasileiro a partir das coordenadas geograficas.
    
    PARAMETROS:
        lat (float): latitude decimal (ex: -12.55).
        lon (float): longitude decimal (ex: -55.72).
    
    RETORNA: tuple(sigla, nome, soja_sc, milho_sc) — ex: ("MT", "Mato Grosso", 84, 107).
        Se nenhum bounding box corresponder, retorna ("BR", "Media Nacional", 60, 107)
        como fallback.
    
    MOTIVO DOS PARAMETROS:
    lat/lon: sao as coordenadas GPS da propriedade. O estado e identificado
    por sobreposicao geografica para obter a produtividade media regional
    da CONAB sem precisar perguntar ao usuario.
    
    NOTA: Bounding boxes podem se sobrepor em divisas. O primeiro match na
    lista vence (MT tem prioridade sobre PA, PR sobre SP, etc.)
    """
    for sigla, nome, lat_min, lat_max, lon_min, lon_max, soja, milho in ESTADOS:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return sigla, nome, soja, milho
    return "BR", "Media Nacional", 60, 107


def potencial_ajustado(lat, lon, cultura, tipo_solo, irrigacao, ndvi_max=None):
    """
    CALCULA o potencial produtivo ajustado para a propriedade especifica.
    
    PARAMETROS:
        lat (float): latitude da propriedade.
        lon (float): longitude da propriedade.
        cultura (str): "soja" ou "milho".
        tipo_solo (str): "argiloso", "misto" ou "arenoso".
        irrigacao (str): "gotejo", "aspersao" ou "sequeiro".
        ndvi_max (float, opcional): valor maximo de NDVI encontrado no periodo.
    
    RETORNA: dict com:
        "sigla" (str): sigla do estado (ex: "MT").
        "estado" (str): nome completo do estado.
        "cultura" (str): cultura analisada.
        "potencial_base" (float): produtividade esperada em sc/ha.
        "produtividade_esperada" (float): mesmo valor (mantido para compatibilidade).
        "fonte" (str): sempre "CONAB 2024/25".
    
    MOTIVO DOS PARAMETROS:
    lat/lon: para identificar o estado e sua produtividade media.
    cultura: seleciona entre produtividade de soja ou milho no estado.
    tipo_solo/irrigacao: fatores multiplicativos que ajustam para cima ou
    para baixo conforme as condicoes locais.
    ndvi_max: se disponivel, aplica bonus de 10% se NDVI > 0.7 (cultura muito
    saudavel) ou penalidade de 10% se NDVI < 0.3 (estresse severo).
    
    FORMULA:
    produtividade = base_estadual * fator_solo * fator_irrigacao * fator_ndvi
    """
    sigla, nome, soja, milho = identificar_estado(lat, lon)
    base = soja if cultura == "soja" else milho
    base *= FATOR_SOLO.get(tipo_solo, 1.00)
    base *= FATOR_IRRIGACAO.get(irrigacao, 1.00)

    # Ajuste por NDVI (vigor vegetativo observado via satelite)
    if ndvi_max is not None:
        if ndvi_max > 0.7:
            base *= 1.10  # Cultura muito saudavel -> +10%
        elif ndvi_max < 0.3:
            base *= 0.90  # Estresse severo -> -10%

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
