"""Planejamento por calendário fenológico; não identifica maturidade em campo."""
from datetime import date, timedelta

from .regras import obter_tabela


CRITERIOS = {
    "soja": [
        "Confirme a maturação plena (R8) e a coloração das vagens em campo.",
        "Meça a umidade dos grãos e confira a regulagem da colheitadeira e a necessidade de secagem.",
        "Confira a previsão de chuva e as condições de acesso ao talhão antes da operação.",
    ],
    "milho": [
        "Confirme a maturidade fisiológica (R6), observando a camada preta nos grãos.",
        "Meça a umidade e verifique a estrutura de secagem: maturidade fisiológica não significa grão seco.",
        "Confira a previsão de chuva e as condições do talhão antes da operação.",
    ],
}


def planejar_colheita(cultura, plantio, hoje, *, data_colheita=None, realizada=None):
    tabela = obter_tabela(cultura)
    if not tabela:
        raise ValueError("Cultura desconhecida")
    codigo, maturacao = list(tabela.items())[-1]
    inicio_dias, fim_dias = maturacao["dias"]
    inicio = plantio + timedelta(days=inicio_dias)
    # As fases usam [início, fim); a interface exibe as duas datas inclusivas.
    fim = plantio + timedelta(days=fim_dias - 1)
    colheita = date.fromisoformat(data_colheita) if data_colheita else None
    referencia = colheita or hoje
    dias = (referencia - plantio).days
    if colheita:
        status, titulo = "REGISTRADA", "Colheita registrada"
        descricao = "Data informada pelo produtor. O painel descreve o histórico até a colheita."
    elif realizada is None:
        status, titulo = "NAO_INFORMADA", "Colheita não confirmada"
        descricao = "Este registro não informa se a colheita ocorreu. Crie uma nova análise para confirmar."
    elif hoje < plantio:
        status, titulo = "PLANEJAMENTO", "Safra em planejamento"
        descricao = "A faixa será uma referência de maturação após o plantio informado."
    elif hoje < inicio:
        status, titulo = "AGUARDAR", "Acompanhe o desenvolvimento"
        descricao = f"Faltam aproximadamente {(inicio - hoje).days} dias para o início da fase de maturação estimada."
    elif hoje <= fim:
        status, titulo = "AVALIAR", "Avalie a maturação em campo"
        descricao = "O calendário indica a fase de maturação. Confirme o estádio e a umidade antes de colher."
    else:
        status, titulo = "REVISAR", "Revise a lavoura em campo"
        descricao = "A faixa do calendário já passou e a colheita não foi realizada. Confira cultivar, plantio e maturidade; não é uma confirmação de atraso."
    fases = [{"codigo": nome, "nome": fase["nome_amigavel"], "inicio_dias": fase["dias"][0],
              "fim_dias_exclusivo": fase["dias"][1],
              "estado": "concluida" if dias >= fase["dias"][1] else "atual" if dias >= fase["dias"][0] else "futura"}
             for nome, fase in tabela.items()]
    return {
        "status": status, "titulo": titulo, "descricao": descricao,
        "realizada": True if colheita else realizada, "data_colheita": data_colheita,
        "data_referencia": referencia.isoformat(), "estimada": colheita is None,
        "janela": {"inicio": inicio.isoformat(), "fim": fim.isoformat(),
                   "inicio_dias": inicio_dias, "fim_dias": fim_dias - 1, "fase": codigo,
                   "rotulo": "Faixa estimada para avaliar a colheita"},
        "progresso_ciclo_pct": round(max(0, min(100, dias / fim_dias * 100))),
        "dias_apos_plantio": dias, "ciclo_referencia_dias": fim_dias, "fases": fases,
        "criterios": CRITERIOS[cultura],
        "limitacao": "Referência de maturação do calendário genérico, não uma data ótima de colheita. Varia com cultivar, região e manejo. O sistema não mede a umidade dos grãos nem usa previsão do tempo para escolher dias de operação.",
        "fonte_calendario": "fenologia-calendario-v2-experimental",
        "referencia_agronomica": (
            "https://www.infoteca.cnptia.embrapa.br/handle/doc/979883" if cultura == "soja" else
            "https://www.infoteca.cnptia.embrapa.br/handle/doc/241208"),
    }
