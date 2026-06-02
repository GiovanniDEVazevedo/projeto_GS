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
def recomendar(scores,alertas_obs, resumo_indices):
    if not scores or "geral" not in scores:
        return {
            "recomendacoes_gerais": {"nivel": "Sem dados", "texto": "Dados insuficientes para gerar recomendacao", "confianca": "baixa"},
            "alertas_ativos" : [],
            "acoes_recomendadas" : [],
            "score_geral": None
        }
    geral = scores["geral"]
    valor = geral["valor"]
    classificacao = geral["classificacao"]
    confianca_geral = geral.get("confianca", "baixa")
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
            rec_principal = {"nivel": "Indefinido", "texto": "Nao foi possivel classificar.", "confianca": "baixa"}
    alertas_ativos = []
    if alertas_obs:
        for alerta in alertas_obs:
            chave = alerta.get("chave", "desconhecido")
            severidade = alerta.get("severidade", "baixa")
            modelo = ALERTAS_PADRAO.get(chave, ALERTAS_PADRAO.get("desconhecido", {
                "mensagem": alerta.get("mensagem", chave),
                "severidade": severidade,
                "acao": "Avaliar condicao localmente"
            }))
            alertas_ativos.append({
                    "tipo": chave,
                    "mensagem": modelo["mensagem"],
                    "severidade": severidade,
                    "acao_recomendada": modelo["acao"],
                    "origem": "observacao_agricultor"
                })
    if resumo_indices:
        dias_estresse = resumo_indices.get("dias_estresse_termico", 0)
        if dias_estresse and dias_estresse > 10:
              alertas_ativos.append({
                   "tipo": "estresse termico",
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
        dias_secos = resumo_indices.get("dias_consecutivos_secos",0)
        if dias_secos and dias_secos> 10:
            alertas_ativos.append({
                "tipo": "seca",
                "mensagem": ALERTAS_PADRAO["seca"]["mensagem"],
                "severidade": "alta",
                "acao_recomendada": ALERTAS_PADRAO["seca"]["acao"],
                "origem": "indices_climaticos"
            })
    vistos = set()
    alertas_unicos = []
    for a in alertas_ativos:
        if a["tipo"] not in vistos:
            vistos.add(a["tipo"])
            alertas_unicos.append(a)
    alertas_ativos = alertas_unicos

    acoes = list(rec_principal.get("acoes", []))
    for alerta in alertas_ativos:
         if alerta["acao_recomendada"] not in acoes:
              acoes.append(alerta["acao_recomendada"])
    probabilidade = _calcular_probabilidade(valor, confianca_geral,alertas_ativos)
    return {
         "recomendacao_principal": rec_principal,
         "alertas_ativos": alertas_ativos,
         "acoes_recomendadas": acoes,
         "probabilidade": probabilidade,
         "score_geral": {"valor": valor,"classificacao": classificacao, "confianca": confianca_geral}
    }
def _ajustar_confianca(confianca_base, confianca_geral):
    niveis = {"alta": 3, "media": 2,"baixa": 1}
    base = niveis.get(confianca_base, 2)
    geral = niveis.get(confianca_geral, 2)
    media = (base + geral) / 2
    if media >= 2.5: return "alta"
    if media >= 1.5: return "media"
    return "baixa"
def _calcular_probabilidade(valor, confianca, alertas_ativos):
    if confianca == "baixa":
        return "Baixa confiabilidade nos dados - recomendacao indicativa"
    pct = round((valor / 10)*100)
    if not alertas_ativos:
         return f"Probabilidade de sucesso estimado em {pct}% com base nos dados historicos e climaticos"
    desconto = len([a for a in alertas_ativos if a["severidade"] == "alta"]) * 10 
    pct_ajustado = max(0, pct - desconto)
    return f"Probabilidade de sucesso estimada em {pct_ajustado}% apos descontar {len([a for a in alertas_ativos if a["severidade"] == "alta"])} alerta(s) de alta severidade"
if __name__ == "__main__":
    # Simula saída do scores.py com os dados que testamos
    scores_exemplo = {
        "geral": {
            "valor": 6.7,
            "classificacao": "Atencao",
            "confianca": "media",
            "scores": {"clima": 5.0, "solo": 10.0, "historico": 5.9, "risco": 7.5}
        }
    }

    alertas_exemplo = [
        {"chave": "geada", "severidade": "alta", "mensagem": "teve uma geada forte"},
        {"chave": "solo_rachado", "severidade": "media", "mensagem": "terra ta rachada"}
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