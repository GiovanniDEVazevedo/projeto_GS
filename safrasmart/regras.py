# =============================================================================
# TABELAS FENOLOGICAS — Soja e Milho
# =============================================================================
# Cada dict internamente contem os parametros agronomicos ideais para cada fase:
#   "dias": tuple(inicio, fim) — dias apos o plantio em que a fase ocorre.
#   "temp_ideal": tuple(min, max) — faixa de temperatura ideal em Celsius.
#   "precip_ideal_mm": tuple(min, max) — precipitacao mensal ideal em mm.
#   "sensivel_geada": bool — True se a fase e vulneravel a geada.
#   "sensibilidade": str — "alto", "medio" ou "baixo" (pesos 3/2/1).
#   "descricao": str — explicacao do que ocorre na fase.
#
# Parâmetros experimentais herdados do protótipo, sem referência documental
# suficiente para calibração. Validar por região/cultivar antes de uso agronômico.
# =============================================================================

FENOLOGIA_SOJA = {
    "VE-V3": {
        "nome_amigavel": "Germinacao e Emergencia",
        "dias": (0, 20),
        "temp_ideal": (20, 30),
        "precip_ideal_mm": (30, 60),
        "sensivel_geada": True,
        "sensibilidade": "alto",
        "descricao": "Plântula emerge e primeiras folhas se abrem"
    },
    "V4-V6": {
        "nome_amigavel": "Crescimento Vegetativo",
        "dias": (20, 40),
        "temp_ideal": (22, 32),
        "precip_ideal_mm": (40, 70),
        "sensivel_geada": True,
        "sensibilidade": "alto",
        "descricao": "Desenvolvimento de folhas e haste principal"
    },
    "R1-R2": {
        "nome_amigavel": "Floracao",
        "dias": (40, 55),
        "temp_ideal": (22, 30),
        "precip_ideal_mm": (50, 80),
        "sensivel_geada": True,
        "sensibilidade": "alto",
        "descricao": "Abertura das flores e inicio da formacao das vagens"
    },
    "R3-R5": {
        "nome_amigavel": "Enchimento de Graos",
        "dias": (55, 90),
        "temp_ideal": (20, 28),
        "precip_ideal_mm": (60, 100),
        "sensivel_geada": False,
        "sensibilidade": "medio",
        "descricao": "Graos acumulam materia seca e nutrientes"
    },
    "R6-R8": {
        "nome_amigavel": "Maturacao",
        "dias": (90, 120),
        "temp_ideal": (18, 28),
        "precip_ideal_mm": (40, 70),
        "sensivel_geada": False,
        "sensibilidade": "baixo",
        "descricao": "Graos secam e atingem ponto de colheita"
    }
}

FENOLOGIA_MILHO = {
    "VE-V3": {
        "nome_amigavel": "Germinacao e Emergencia",
        "dias": (0, 20),
        "temp_ideal": (20, 30),
        "precip_ideal_mm": (30, 60),
        "sensivel_geada": True,
        "sensibilidade": "alto",
        "descricao": "Semente germina e plântula emerge"
    },
    "V6-VT": {
        "nome_amigavel": "Crescimento e Pendoamento",
        "dias": (20, 60),
        "temp_ideal": (22, 32),
        "precip_ideal_mm": (50, 80),
        "sensivel_geada": False,
        "sensibilidade": "alto",
        "descricao": "Crescimento acelerado e emissao do pendao"
    },
    "R1": {
        "nome_amigavel": "Floracao (Espigamento)",
        "dias": (60, 75),
        "temp_ideal": (22, 30),
        "precip_ideal_mm": (60, 90),
        "sensivel_geada": False,
        "sensibilidade": "alto",
        "descricao": "Polinizacao e formacao dos graos"
    },
    "R2-R4": {
        "nome_amigavel": "Enchimento de Graos",
        "dias": (75, 105),
        "temp_ideal": (20, 28),
        "precip_ideal_mm": (50, 80),
        "sensivel_geada": False,
        "sensibilidade": "medio",
        "descricao": "Graos acumulam amido e nutrientes"
    },
    "R5-R6": {
        "nome_amigavel": "Maturacao",
        "dias": (105, 140),
        "temp_ideal": (18, 26),
        "precip_ideal_mm": (30, 60),
        "sensivel_geada": False,
        "sensibilidade": "baixo",
        "descricao": "Graos secam e atingem ponto de colheita"
    }
}

PESO_SENSIBILIDADE = {
    "alto": 3,
    "medio": 2,
    "baixo": 1
}
"""
Dicionario que converte o nivel de sensibilidade em peso numerico.
Usado em scores.py para ponderar penalidades de acordo com a fase:
- Fases "alto" (ex: germinacao): peso 3 — qualquer estresse e critico.
- Fases "medio" (ex: enchimento): peso 2 — estresse causa danos moderados.
- Fases "baixo" (ex: maturacao): peso 1 — cultura mais tolerante.
"""


def obter_tabela(cultura):
    """
    RETORNA a tabela fenologica completa para a cultura especificada.
    
    PARAMETROS:
        cultura (str): "soja" ou "milho".
    
    RETORNA: dict — FENOLOGIA_SOJA ou FENOLOGIA_MILHO completo.
        Retorna None se a cultura for desconhecida.
    
    MOTIVO DOS PARAMETROS:
    cultura: necessario para selecionar a tabela correta, ja que soja e milho
    tem ciclos, fases e tolerancias diferentes.
    """
    if cultura == "soja":
        return FENOLOGIA_SOJA
    elif cultura == "milho":
        return FENOLOGIA_MILHO
    return None


def fase_atual(cultura, dias_apos_plantio):
    """
    IDENTIFICA em qual fase fenologica a cultura se encontra.
    
    PARAMETROS:
        cultura (str): "soja" ou "milho".
        dias_apos_plantio (int): numero de dias desde o plantio.
            Pode ser negativo (antes do plantio) ou maior que o ciclo total
            (pos-safra).
    
    RETORNA: tuple(str, dict) — (nome_da_fase, dados_da_fase).
        O primeiro elemento e o codigo da fase (ex: "VE-V3").
        O segundo e o dicionario com todos os parametros da fase.
        
    CASOS ESPECIAIS:
        - Se dias_apos_plantio < 0 (antes do plantio): retorna "Pre-Plantio"
          com dados genericos para planejamento.
        - Se passou do ciclo total: retorna "Pos-Safra" com tolerancia ampla
          (15-35°C, 0-200mm) para analise historica.
        - Se cultura desconhecida: retorna string de erro.
    
    MOTIVO DOS PARAMETROS:
    cultura: determina qual tabela fenologica usar (soja 120 dias, milho 140).
    dias_apos_plantio: calculado como (data_atual - data_plantio).days.
        Essencial para saber se a cultura esta na fase critica de floracao,
        na germinacao (sensivel a geada) ou na maturacao (tolerante).
    """
    tabela = obter_tabela(cultura)
    if not tabela:
        raise ValueError("Cultura desconhecida")
    if dias_apos_plantio < 0:
        return "Pre-Plantio", {
            "nome_amigavel": "Pre-Plantio - Periodo de Planejamento",
            "dias": (dias_apos_plantio, 0),
            "temp_ideal": (20, 30),
            "precip_ideal_mm": (30, 60),
            "sensivel_geada": False,
            "sensibilidade": "baixo",
            "descricao": "Preparo do solo e planejamento da safra"
        }
    for nome_fase, dados in tabela.items():
        inicio, fim = dados["dias"]
        if inicio <= dias_apos_plantio < fim:
            return nome_fase, dados
    return "Pos-Safra", {
        "nome_amigavel": "Após o ciclo estimado",
        "dias": (dias_apos_plantio, dias_apos_plantio),
        "temp_ideal": (15, 35),
        "precip_ideal_mm": (0, 200),
        "sensivel_geada": False,
        "sensibilidade": "baixo",
        "descricao": "Ciclo de calendário estimado encerrado; colheita não confirmada."
    }


def faixa_com_tolerancia(min_ideal, max_ideal, pct=20):
    """
    EXPANDE a faixa ideal em uma porcentagem para cada lado.
    
    PARAMETROS:
        min_ideal (float): limite inferior da faixa ideal (ex: 20°C).
        max_ideal (float): limite superior da faixa ideal (ex: 30°C).
        pct (int): porcentagem de tolerancia (padrao=20%).
    
    RETORNA: tuple(float, float) — (min_tolerado, max_tolerado).
        Ex: faixa_com_tolerancia(20, 30, 20) retorna (18.0, 32.0).
        A margem e calculada como (max-min) * pct / 100.
    
    MOTIVO DOS PARAMETROS:
    pct=20: margem experimental do protótipo, sem calibração, usada para
    definir faixas aceitaveis. Por exemplo, se a faixa ideal de temperatura
    e 20-30°C, valores entre 18-32°C sao considerados aceitaveis sem causar
    danos significativos.
    
    USO:
    Usada em scores.py:score_clima para comparar a temperatura e precipitacao
    observadas com as faixas ideais das fases fenologicas, com margem de
    tolerancia.
    """
    margem = (max_ideal - min_ideal) * pct / 100
    return (min_ideal - margem, max_ideal + margem)


if __name__ == "__main__":
    print("=== Teste Regras Fenologicas ===")

    for cultura in ("soja", "milho"):
        print(f"\n--- {cultura.upper()} ---")
        tabela = obter_tabela(cultura)
        for codigo, dados in tabela.items():
            dias = dados["dias"]
            print(f"  {codigo} ({dados['nome_amigavel']}): {dias[0]}-{dias[1]} dias")
            print(f"    Temp ideal: {dados['temp_ideal'][0]}-{dados['temp_ideal'][1]}C")
            print(f"    Precip ideal: {dados['precip_ideal_mm'][0]}-{dados['precip_ideal_mm'][1]}mm")
            print(f"    Sensibilidade: {dados['sensibilidade']} | Geada: {dados['sensivel_geada']}")

    print("\n--- Teste fase_atual() ---")
    cenarios = [("soja", -50), ("soja", 10), ("soja", 45), ("soja", 75),
                ("milho", 110), ("milho", 250)]
    for cultura, dias in cenarios:
        fase, dados = fase_atual(cultura, dias)
        nome = dados["nome_amigavel"] if dados else "N/A"
        print(f"  Cultura={cultura}, dias={dias}: {fase} — {nome}")

    print("\n--- Teste faixa_com_tolerancia() ---")
    print(f"  Temp ideal (20, 30) com 20%: {faixa_com_tolerancia(20, 30)}")
    print(f"  Precip ideal (50, 80) com 20%: {faixa_com_tolerancia(50, 80)}")
