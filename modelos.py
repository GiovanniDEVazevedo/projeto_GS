from datetime import datetime

def tipo_cultura():
    """
    PERGUNTA AO USUARIO qual cultura sera plantada (soja ou milho).
    
    PARAMETROS: nenhum — a funcao interage via terminal (input).
    
    RETORNA: str — "milho" se o usuario digitar 1, "soja" se digitar 2.
    
    MOTIVO DOS PARAMETROS:
    Nao recebe parametros porque os dados sao coletados interativamente do agricultor
    no terminal. Isso mantem a entrada de dados simples e acessivel para uso em campo.
    """
    print("selecione o tipode cultura\n 1.milho\n 2.soja\n")
    opcao = int(input(">"))
    if opcao == 1:
        cultura = "milho"
    elif opcao == 2:
        cultura = "soja"
    else:
        print("valor invalido!")
        tipo_cultura()
    return cultura

def data_plantio():
    """
    PERGUNTA AO USUARIO a data em que o plantio foi (ou sera) realizado.
    
    PARAMETROS: nenhum — entrada via terminal.
    
    RETORNA: datetime — objeto de data do Python (ex: 2025-10-20 00:00:00).
    
    MOTIVO DOS PARAMETROS:
    A data de plantio e essencial para calcular em qual fase fenologica
    a cultura se encontra no momento da analise (regras.py:fase_atual).
    O formato dd/MM/aaaa foi escolhido por ser o padrao brasileiro.
    
    NOTA: Se o formato digitado estiver errado, a funcao lanca ValueError
    propositalmente para que o usuario perceba o erro.
    """
    data = input("digite a data do plantio(dd/MM/aaaa)\n >")
    objeto_data = datetime.strptime(data , "%d/%m/%Y")
    return objeto_data

def tipo_solo():
    """
    PERGUNTA AO USUARIO o tipo de solo predominante na propriedade.
    
    PARAMETROS: nenhum — entrada via terminal com menu numerico.
    
    RETORNA: str — "arenoso", "argiloso" ou "misto".
    
    MOTIVO DOS PARAMETROS:
    O tipo de solo influencia diretamente o potencial produtivo
    (produtividade.py:FATOR_SOLO) e o score de solo (scores.py:score_solo).
    Argiloso retem mais agua e nutrientes (fator 1.10), arenoso e mais pobre
    (fator 0.85), misto e intermediario (1.00).
    """
    print("qual o tipo de solo\n 1. Arenoso\n 2. Argiloso\n 3.misto\n")
    opcao = int(input("> "))
    match opcao:
        case 1:
            solo = "arenoso"
        case 2:
            solo = "argiloso"
        case 3: 
            solo = "misto"
        case _ :
            print("valor invalido!")
            tipo_solo()
    return solo

def tipo_irrigacao():
    """
    PERGUNTA AO USUARIO qual sistema de irrigacao e utilizado.
    
    PARAMETROS: nenhum — entrada via terminal com menu numerico.
    
    RETORNA: str — "sequeiro" (sem irrigacao), "aspersao" ou "gotejo".
    
    MOTIVO DOS PARAMETROS:
    A irrigacao afeta o potencial produtivo (produtividade.py:FATOR_IRRIGACAO)
    e o score de solo (scores.py:score_solo). Gotejo e mais eficiente (1.15),
    aspersao e intermediario (1.08), sequeiro nao tem bonus (1.00).
    """
    print("selecione o tipo de irrigacao\n 1.sequeiro\n 2.aspersao\n 3.gotejo")
    opcao = int(input("> "))
    match opcao:
        case 1:
            irrigacao = "sequeiro"
        case 2: 
            irrigacao = "aspersao"
        case 3:
            irrigacao = "gotejo"
        case _:
            print("valor invalido!")
            tipo_irrigacao()
    return irrigacao

def prod_anterior():
    """
    PERGUNTA AO USUARIO quantas sacas por hectare (sc/ha) foram colhidas na safra passada.
    
    PARAMETROS: nenhum — entrada via terminal.
    
    RETORNA: int — numero inteiro de sacas de 60kg (ex: 80 significa 80 sc/ha).
    
    MOTIVO DOS PARAMETROS:
    A produtividade anterior e usada em scores.py:score_historico para comparar
    o desempenho passado com o potencial regional da CONAB. Isso permite
    avaliar se o agricultor esta acima ou abaixo da media historica.
    """
    prod = int(input("digite o numero de sacas da ultima coleita\n>"))
    return prod

def obs_user():
    """
    PERGUNTA AO USUARIO suas observacoes livres sobre a lavoura.
    
    PARAMETROS: nenhum — entrada via terminal como texto livre.
    
    RETORNA: str — o texto digitado pelo agricultor (ex: "teve uma geada forte").
    
    MOTIVO DOS PARAMETROS:
    O texto e processado por observacao.py:analisar_obs que usa NLP simples
    (normalizacao de acentos + busca de palavras-chave) para extrair alertas
    sobre pragas, doencas, clima e solo. Isso enriquece a recomendacao final
    com a percepcao de quem esta no campo.
    """
    obs = input("digite suas observacoes sobre o plantio\n>")
    return obs
