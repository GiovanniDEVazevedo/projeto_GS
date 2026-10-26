"""Triagem explicável de evidências, sem prescrição ou probabilidade inventada."""
ALERTAS_PADRAO = {
    "geada": ("Temperaturas baixas ou geada relatada; verificar condições no campo.", "Consultar previsão local e assistência técnica para avaliar proteção."),
    "seca": ("Período seco observado ou relatado; a umidade do solo precisa ser verificada.", "Verificar umidade do solo e disponibilidade de água antes de decidir sobre irrigação."),
    "estresse_termico": ("Há registros ou relatos de calor elevado no período analisado.", "Acompanhar temperatura e sinais de estresse no campo."),
    "praga": ("Presença ou suspeita de praga relatada pelo produtor, sem confirmação automática.", "Inspecionar a área e buscar identificação com assistência técnica."),
    "doenca": ("Sintomas ou suspeita de doença relatados, sem diagnóstico automático.", "Registrar fotos e consultar assistência técnica para diagnóstico."),
    "solo_rachado": ("Ressecamento ou fissuras relatados no solo.", "Verificar umidade e cobertura do solo com assistência técnica."),
    "solo_compactado": ("Possível compactação relatada.", "Verificar o perfil do solo antes de alterar o manejo."),
    "excesso_hidrico": ("Solo encharcado ou excesso de água relatado; pode haver restrição de aeração.", "Inspecionar drenagem e evitar decisões de irrigação sem avaliar o solo."),
    "solo_infertil": ("Possível baixa fertilidade relatada; não confirmada por análise de solo.", "Consultar análise de solo e orientação agronômica."),
}
MAPA = {"lagarta": "praga", "percevejo": "praga", "pulgao": "praga", "mosca branca": "praga", "cochonilha": "praga",
        "ferrugem": "doenca", "fungo": "doenca", "oidio": "doenca", "antracnose": "doenca", "mancha": "doenca", "mofo": "doenca",
        "geada": "geada", "seca": "seca", "estiagem": "seca", "calor forte": "estresse_termico",
        "rachado": "solo_rachado", "compactado": "solo_compactado", "encharcado": "excesso_hidrico", "infertil": "solo_infertil"}


def recomendar(scores, alertas_obs, resumo_indices):
    geral = (scores or {}).get("geral") or {}
    status = geral.get("status", "SEM_DADOS")
    alertas = []
    for relato in alertas_obs or []:
        if relato.get("presenca") == "negada" or relato.get("temporalidade", "atual") != "atual":
            continue
        chave = MAPA.get(relato.get("evento", relato.get("palavra")))
        if not chave:
            if relato.get("categoria") not in {"pragas", "doencas", "clima_negativo", "solo_negativo"}:
                continue
            alertas.append({"tipo": relato.get("palavra", "relato"), "mensagem": "Ocorrência relatada: " + relato.get("palavra", "não identificada"),
                "severidade": relato.get("severidade", "media"), "origem": "relato_produtor",
                "acao_recomendada": "Verificar a ocorrência no campo com assistência técnica."})
            continue
        mensagem, acao = ALERTAS_PADRAO[chave]
        alertas.append({"tipo": chave, "mensagem": mensagem, "acao_recomendada": acao,
                        "severidade": relato.get("severidade", "media"), "origem": "relato_produtor",
                        "presenca": relato.get("presenca", "relatada"), "confirmacao": "nao_verificada"})
    for chave, ativo in [
        ("estresse_termico", (resumo_indices.get("dias_estresse_termico") or 0) > 5),
        ("geada", (resumo_indices.get("risco_geada_pct") or 0) > 0),
        ("seca", (resumo_indices.get("dias_consecutivos_secos") or 0) > 10),
    ]:
        if ativo:
            mensagem, acao = ALERTAS_PADRAO[chave]
            alertas.append({"tipo": chave, "mensagem": mensagem, "severidade": "alta", "origem": "modelo_meteorologico",
                            "acao_recomendada": acao, "periodo_inicio": resumo_indices.get("periodo_inicio"), "periodo_fim": resumo_indices.get("periodo_fim")})
    unicos = {(a["tipo"], a["origem"]): a for a in alertas}
    alertas = list(unicos.values())
    if status == "SEM_DADOS":
        nivel, texto = "Dados insuficientes", "Não há evidência climática suficiente para sintetizar as condições. Os relatos continuam disponíveis para verificação."
    elif alertas:
        status = "ATENCAO" if status == "FAVORAVEL" else status
        nivel, texto = "Atenção às evidências", "Existem ocorrências que precisam ser verificadas no campo. Consulte as justificativas e os períodos analisados."
    else:
        nivel, texto = "Condições observadas", "Consulte os indicadores e sua cobertura. Ausência de alertas não comprova ausência de problemas."
    acoes = list(dict.fromkeys(a["acao_recomendada"] for a in alertas))
    acoes.append("Para planejar plantio, consultar o ZARC da região e assistência agronômica; este relatório não define a janela de plantio.")
    return {"status": status, "recomendacao_principal": {"nivel": nivel, "texto": texto, "confianca": "baixa"},
            "alertas_ativos": alertas, "acoes_recomendadas": acoes, "score_geral": geral,
            "limitacao": "Triagem experimental de apoio à decisão; regras ainda sem calibração agronômica. Não estima probabilidade de sucesso nem produtividade."}
