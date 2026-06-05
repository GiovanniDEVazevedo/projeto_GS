# =============================================================================
# NIVEL DE RECOMENDACAO (3 niveis)
# =============================================================================
# Cada nivel tem:
#   "nivel": nome do nivel.
#   "faixa": tuple(min, max) — faixa de score que ativa este nivel.
#   "texto": descricao amigavel para o agricultor.
#   "confianca_base": confianca intrinseca deste nivel.
#   "acoes": lista de acoes recomendadas padrao.
# =============================================================================
RECOMENDACOES = [
    {
        "nivel": "Recomendado",
        "faixa": (7.0, 10.0),
        "texto": "Condicoes favoraveis para o plantio e conducao da safra.",
        "confianca_base": "alta",
        "acoes": [
            "Iniciar plantio conforme janela ideal para a regiao",
            "Manter monitoramento fitossanitario padrao",
            "Aplicar fertilizacao de base conforme analise de solo",
            "Contratar seguro agricola recomendado"
        ]
    },
    {
        "nivel": "Atencao",
        "faixa": (5.0, 6.9),
        "texto": "Condicoes regulares — recomenda-se cautela e medidas mitigadoras.",
        "confianca_base": "media",
        "acoes": [
            "Avaliar risco-beneficio antes de iniciar plantio",
            "Intensificar monitoramento climatico (previsao 15 dias)",
            "Priorizar cultivares resistentes a estresse hidrico",
            "Considerar plantio escalonado para diluir riscos",
            "Revisar cobertura do seguro agricola"
        ]
    },
    {
        "nivel": "Nao recomendado",
        "faixa": (0.0, 4.9),
        "texto": "Condicoes desfavoraveis — plantio nao recomendado neste momento.",
        "confianca_base": "baixa",
        "acoes": [
            "Adiar o plantio ate melhora das condicoes climaticas",
            "Consultar zoneamento agricola de risco climatico (ZARC)",
            "Avaliar culturas alternativas mais tolerantes",
            "Manter area em pousio ou plantar cobertura verde",
            "Revisar planejamento financeiro da safra"
        ]
    }
]

# =============================================================================
# ALERTAS PADRAO
# =============================================================================
# Mapeia tipos de alerta para mensagens e acoes recomendadas.
# A severidade determina o impacto no score de probabilidade.
# Cada alerta tem:
#   "mensagem": texto explicativo para o agricultor.
#   "severidade": "alta", "media" ou "baixa".
#   "acao": acao mitigadora recomendada.
# =============================================================================
ALERTAS_PADRAO = {
    "geada": {
        "mensagem": "Risco de geada detectado — proteja mudas com cobertura",
        "severidade": "alta",
        "acao": "Cobertura de solo com palha ou filme plastico"
    },
    "seca": {
        "mensagem": "Periodo seco prolongado — irrigacao de salvacao recomendada",
        "severidade": "alta",
        "acao": "Irrigacao suplementar imediata"
    },
    "estresse_termico": {
        "mensagem": "Dias consecutivos acima de 35°C — risco de esterilidade floral",
        "severidade": "alta",
        "acao": "Irrigacao por aspersao para refrescamento do dossel"
    },
    "praga": {
        "mensagem": "Pragas detectadas na lavoura — monitoramento urgente",
        "severidade": "alta",
        "acao": "Aplicacao de defensivo especifico com receituario agronomico"
    },
    "doenca": {
        "mensagem": "Sintomas de doenca identificados — diagnostico laboratorial necessario",
        "severidade": "alta",
        "acao": "Coletar amostras e enviar ao laboratorio fitopatologico"
    },
    "solo_rachado": {
        "mensagem": "Solo com fissuras — perda de umidade acelerada",
        "severidade": "media",
        "acao": "Gradagem leve para quebrar crosta superficial"
    },
    "solo_umido": {
        "mensagem": "Solo com umidade adequada — condicoes favoraveis",
        "severidade": "baixa",
        "acao": "Prosseguir com operacoes planejadas"
    }
}


def recomendar(scores, alertas_obs, resumo_indices):
    """
    FUNCAO PRINCIPAL: gera a recomendacao final com base em scores, alertas e indices.
    
    PARAMETROS:
        scores (dict): contem a chave "geral" com o score_geral completo.
            Ex: {"geral": {"valor": 7.5, "classificacao": "Recomendado", ...}}.
        alertas_obs (list[dict]): alertas da observacao do agricultor (JA filtrados,
            sem categorias positivas). Cada item tem "categoria", "palavra",
            "severidade".
        resumo_indices (dict): indices climaticos com "dias_estresse_termico",
            "risco_geada_pct", "dias_consecutivos_secos".
    
    RETORNA: dict com 5 chaves:
        "recomendacao_principal" (dict): nivel, texto, confianca, acoes.
        "alertas_ativos" (list[dict]): alertas climaticos + observacao (deduplicados).
        "acoes_recomendadas" (list[str]): acoes da recomendacao + alertas (sem duplicatas).
        "probabilidade" (str): texto explicativo da probabilidade de sucesso.
        "score_geral" (dict): valor, classificacao, confianca.
    
    FLUXO:
    1. Valida dados de entrada.
    2. Encontra o nivel de recomendacao pela faixa de score.
    3. Adiciona alertas climaticos automaticos (estresse, geada, seca).
    4. Converte alertas da observacao usando ALERTAS_PADRAO.
    5. Deduplica alertas (mesmo tipo aparece uma vez).
    6. Mescla acoes da recomendacao com acoes dos alertas.
    7. Calcula probabilidade com desconto por severidade.
    """
    if not scores or "geral" not in scores:
        return {
            "recomendacoes_gerais": {
                "nivel": "Sem dados",
                "texto": "Dados insuficientes para gerar recomendacao",
                "confianca": "baixa"
            },
            "alertas_ativos": [],
            "acoes_recomendadas": [],
            "score_geral": None
        }

    geral = scores["geral"]
    valor = geral["valor"]
    classificacao = geral["classificacao"]
    confianca_geral = geral.get("confianca", "baixa")

    # Encontra o nivel de recomendacao pela faixa de score
    rec_principal = None
    for rec in RECOMENDACOES:
        faixa_min, faixa_max = rec["faixa"]
        if faixa_min <= valor <= faixa_max:
            rec_principal = {
                "nivel": rec["nivel"],
                "texto": rec["texto"],
                "confianca": _ajustar_confianca(rec["confianca_base"], confianca_geral),
                "acoes": rec["acoes"]
            }
            break

    if rec_principal is None:
        rec_principal = {
            "nivel": "Indefinido",
            "texto": "Nao foi possivel classificar.",
            "confianca": "baixa"
        }

    # Monta lista de alertas ativos
    alertas_ativos = []

    # 1. Alertas da observacao do agricultor
    if alertas_obs:
        for alerta in alertas_obs:
            categoria = alerta.get("categoria", "desconhecido")
            palavra = alerta.get("palavra", "desconhecido")
            severidade = alerta.get("severidade", "baixa")

            # Mapeia categoria/palavra para um tipo de alerta padrao
            # Se nao encontrar, cria alerta generico
            # Mapeamento direto para tipos conhecidos
            tipo_alerta = palavra.lower()
            # Normaliza para as chaves de ALERTAS_PADRAO
            mapa_palavra = {
                "geada": "geada", "seca": "seca", "estiagem": "seca",
                "calor forte": "estresse_termico",
                "lagarta": "praga", "percevejo": "praga", "pulgao": "praga",
                "mosca branca": "praga", "cochonilha": "praga", "ferrugem": "praga",
                "fungo": "doenca", "oidio": "doenca", "antracnose": "doenca",
                "mancha": "doenca", "mofo": "doenca",
                "rachado": "solo_rachado", "duro": "solo_rachado",
                "compactado": "solo_rachado", "encharcado": "solo_umido",
            }
            chave = mapa_palavra.get(tipo_alerta, None)

            if chave and chave in ALERTAS_PADRAO:
                modelo = ALERTAS_PADRAO[chave]
                alertas_ativos.append({
                    "tipo": chave,
                    "mensagem": modelo["mensagem"],
                    "severidade": severidade,
                    "acao_recomendada": modelo["acao"],
                    "origem": "observacao_agricultor"
                })

    # 2. Alertas climaticos automaticos (baseados em indices)
    if resumo_indices:
        dias_estresse = resumo_indices.get("dias_estresse_termico", 0)
        if dias_estresse and dias_estresse > 10:
            alertas_ativos.append({
                "tipo": "estresse_termico",
                "mensagem": ALERTAS_PADRAO["estresse_termico"]["mensagem"],
                "severidade": "alta",
                "acao_recomendada": ALERTAS_PADRAO["estresse_termico"]["acao"],
                "origem": "indices_climaticos"
            })

        geada_pct = resumo_indices.get("risco_geada_pct", 0)
        if geada_pct and geada_pct > 5:
            alertas_ativos.append({
                "tipo": "geada",
                "mensagem": ALERTAS_PADRAO["geada"]["mensagem"],
                "severidade": "alta",
                "acao_recomendada": ALERTAS_PADRAO["geada"]["acao"],
                "origem": "indices_climaticos"
            })

        dias_secos = resumo_indices.get("dias_consecutivos_secos", 0)
        if dias_secos and dias_secos > 10:
            alertas_ativos.append({
                "tipo": "seca",
                "mensagem": ALERTAS_PADRAO["seca"]["mensagem"],
                "severidade": "alta",
                "acao_recomendada": ALERTAS_PADRAO["seca"]["acao"],
                "origem": "indices_climaticos"
            })

    # 3. Deduplica alertas (mesmo tipo aparece apenas uma vez)
    vistos = set()
    alertas_unicos = []
    for a in alertas_ativos:
        if a["tipo"] not in vistos:
            vistos.add(a["tipo"])
            alertas_unicos.append(a)
    alertas_ativos = alertas_unicos

    # 4. Mescla acoes (recomendacao + alertas, sem duplicatas)
    acoes = list(rec_principal.get("acoes", []))
    for alerta in alertas_ativos:
        if alerta["acao_recomendada"] not in acoes:
            acoes.append(alerta["acao_recomendada"])

    probabilidade = _calcular_probabilidade(valor, confianca_geral, alertas_ativos)

    return {
        "recomendacao_principal": rec_principal,
        "alertas_ativos": alertas_ativos,
        "acoes_recomendadas": acoes,
        "probabilidade": probabilidade,
        "score_geral": {
            "valor": valor,
            "classificacao": classificacao,
            "confianca": confianca_geral
        }
    }


def _ajustar_confianca(confianca_base, confianca_geral):
    """
    AJUSTA a confianca final combinando a confianca base do nivel de recomendacao
    com a confianca geral dos dados.
    
    PARAMETROS:
        confianca_base (str): confianca intrinseca do nivel ("alta", "media", "baixa").
        confianca_geral (str): confianca dos dados ("alta", "media", "baixa").
    
    RETORNA: str — "alta", "media" ou "baixa".
    
    LOGICA:
    Converte "alta"=3, "media"=2, "baixa"=1, calcula media aritmetica:
    - media >= 2.5 -> "alta"
    - media >= 1.5 -> "media"
    - senao -> "baixa"
    
    Ex: base="alta"(3) + geral="media"(2) = media 2.5 -> "alta"
    Ex: base="media"(2) + geral="baixa"(1) = media 1.5 -> "media"
    """
    niveis = {"alta": 3, "media": 2, "baixa": 1}
    base = niveis.get(confianca_base, 2)
    geral = niveis.get(confianca_geral, 2)
    media = (base + geral) / 2
    if media >= 2.5:
        return "alta"
    if media >= 1.5:
        return "media"
    return "baixa"


def _calcular_probabilidade(valor, confianca, alertas_ativos):
    """
    CALCULA a probabilidade de sucesso da safra como texto explicativo.
    
    PARAMETROS:
        valor (float): score geral (0-10).
        confianca (str): confianca geral dos dados.
        alertas_ativos (list[dict]): lista de alertas ativos.
    
    RETORNA: str — texto explicativo da probabilidade.
    
    LOGICA:
    - Se confianca "baixa": retorna mensagem de baixa confiabilidade.
    - Senao: pct = (valor/10) * 100, desconta 10% por alerta de alta severidade.
    
    Ex: score 7.5, 2 alertas altos -> 75% - 20% = 55%
    
    MOTIVO:
    A probabilidade nunca e absoluta ("garantimos 75% de sucesso"), mas sim
    uma estimativa com descontos por riscos identificados. Isso reforca a
    natureza probabilistica e nao deterministica do sistema.
    """
    if confianca == "baixa":
        return "Baixa confiabilidade nos dados - recomendacao indicativa"
    pct = round((valor / 10) * 100)
    if not alertas_ativos:
        return f"Probabilidade de sucesso estimada em {pct}% com base nos dados historicos e climaticos"
    desconto = len([a for a in alertas_ativos if a["severidade"] == "alta"]) * 10
    pct_ajustado = max(0, pct - desconto)
    return (
        f"Probabilidade de sucesso estimada em {pct_ajustado}%"
        f" apos descontar {len([a for a in alertas_ativos if a['severidade'] == 'alta'])}"
        f" alerta(s) de alta severidade"
    )


if __name__ == "__main__":
    # Simula saida do scores.py com os dados que testamos
    scores_exemplo = {
        "geral": {
            "valor": 6.7,
            "classificacao": "Atencao",
            "confianca": "media",
            "scores": {"clima": 5.0, "solo": 10.0, "historico": 5.9, "risco": 7.5}
        }
    }

    alertas_exemplo = [
        {"categoria": "clima_negativo", "palavra": "geada", "severidade": "alta"},
        {"categoria": "solo_negativo", "palavra": "rachado", "severidade": "media"}
    ]

    indices_exemplo = {
        "dias_estresse_termico": 3,
        "risco_geada_pct": 12,
        "dias_consecutivos_secos": 8
    }

    resultado = recomendar(scores_exemplo, alertas_exemplo, indices_exemplo)

    print("=== RECOMENDACAO ===\n")
    rp = resultado["recomendacao_principal"]
    print(f"Nivel: {rp['nivel']}")
    print(f"Texto: {rp['texto']}")
    print(f"Confianca: {rp['confianca']}")
    print(f"\nProbabilidade: {resultado['probabilidade']}")

    if resultado["alertas_ativos"]:
        print(f"\nAlertas ativos ({len(resultado['alertas_ativos'])}):")
        for a in resultado["alertas_ativos"]:
            print(f"  [{a['severidade'].upper()}] {a['mensagem']}")
            print(f"    Acao: {a['acao_recomendada']}")

    print(f"\nAcoes recomendadas ({len(resultado['acoes_recomendadas'])}):")
    for i, acao in enumerate(resultado["acoes_recomendadas"], 1):
        print(f"  {i}. {acao}")
