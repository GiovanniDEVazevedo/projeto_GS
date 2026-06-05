def media_movel_temperatura(dados_climaticos, janela=7):
    """
    CALCULA a media movel da temperatura media diaria.
    
    A media movel suaviza variacoes diarias e revela a tendencia termica real,
    essencial para identificar ondas de calor ou frio prolongado.
    
    PARAMETROS:
        dados_climaticos (dict): saida padronizada de clima.py:buscar_dados_meteo()
            com as chaves "datas", "temp_max", "temp_min", "precip".
        janela (int): tamanho da janela da media movel em dias (padrao=7).
            Uma janela de 7 dias representa uma semana, que e o ciclo minimo
            para detectar mudancas climaticas significativas na agricultura.
    
    RETORNA: list[float] — medias moveis para cada dia do periodo.
        O primeiro elemento usa os dados disponiveis desde o inicio
        (pode ter menos pontos que a janela).
    
    MOTIVO DOS PARAMETROS:
    - dados_climaticos: necessario para extrair temp_max e temp_min de cada dia.
    - janela=7: 7 dias e o padrao agronomico para avaliar tendencias de
      temperatura semanalmente, periodo suficiente para acionar alertas de
      estresse termico.
    
    CALCULO:
    Temperatura media diaria = (temp_max + temp_min) / 2
    Media movel = media das temperaturas medias dos ultimos N dias.
    """
    medias = []
    n = len(dados_climaticos["datas"])
    temps = []
    for i in range(n):
        temps.append((dados_climaticos["temp_max"][i] + dados_climaticos["temp_min"][i]) / 2)
    for i in range(n):
        inicio = max(0, i - janela + 1)
        fatia = temps[inicio:i + 1]
        medias.append(round(sum(fatia) / len(fatia), 1))
    return medias


def precip_acumulada(dados_climaticos, dia_inicio, dia_fim):
    """
    CALCULA a precipitacao total acumulada em um intervalo de dias.
    
    PARAMETROS:
        dados_climaticos (dict): dados climaticos padronizados.
        dia_inicio (int): indice do dia inicial (0-based, 0 = primeira data).
        dia_fim (int): indice do dia final (inclusive).
    
    RETORNA: float — soma total de precipitacao em mm no intervalo.
        Retorna 0.0 se os indices estiverem fora dos limites.
    
    MOTIVO DOS PARAMETROS:
    dia_inicio/dia_fim: indices que permitem calcular precipitacao para
    qualquer periodo, como fases fenologicas especificas (ex: quanto choveu
    durante a floracao). Usar indices em vez de datas evita parse de string.
    
    USO:
    Usada em scores.py indiretamente via resumo_climatico para comparar
    a precipitacao observada com a faixa ideal da fase fenologica.
    """
    n = len(dados_climaticos["datas"])
    if dia_inicio < 0 or dia_fim >= n:
        return 0.0
    total = 0.0
    for i in range(dia_inicio, dia_fim + 1):
        total += dados_climaticos["precip"][i]
    return round(total, 1)


def dias_consecutivos_secos(dados_climaticos, limiar_mm=0.5):
    """
    CONTA quantos dias consecutivos (do presente para tras) tiveram
    precipitacao abaixo do limiar.
    
    PARAMETROS:
        dados_climaticos (dict): dados climaticos padronizados.
        limiar_mm (float): valor em mm abaixo do qual considera-se "seco"
            (padrao=0.5mm — chuva insignificante que nao molha o solo).
    
    RETORNA: int — numero de dias secos consecutivos.
        Ex: 15 significa que faz 15 dias que nao chove significativamente.
    
    MOTIVO DOS PARAMETROS:
    limiar_mm=0.5: valores abaixo de 0.5mm sao considerados orvalho ou
    chuva tracejada, insuficientes para repor agua no solo.
    
    POR QUE DE TRAS PARA FRENTE:
    A varredura comeca do ultimo dia (hoje) e vai para tras, parando no
    primeiro dia com chuva. Isso mede a SECA ATUAL, nao a quantidade total
    de dias secos no periodo. Essencial para alertas de seca em tempo real.
    """
    contador = 0
    n = len(dados_climaticos["datas"])
    for i in range(n - 1, -1, -1):
        if dados_climaticos["precip"][i] < limiar_mm:
            contador += 1
        else:
            break
    return contador


def dias_estresse_termico(dados_climaticos, limite=35.0):
    """
    CONTA quantos dias tiveram temperatura maxima acima do limite de estresse.
    
    PARAMETROS:
        dados_climaticos (dict): dados climaticos padronizados.
        limite (float): temperatura em Celsius acima da qual ha estresse
            (padrao=35.0°C — temperatura que causa fechamento estomatico
            e esterilidade floral em soja e milho).
    
    RETORNA: int — numero de dias com estresse termico no periodo.
    
    MOTIVO DOS PARAMETROS:
    limite=35.0°C: baseado na literatura agronomica, temperaturas acima de
    35°C durante a floracao causam abortamento floral em soja e milho,
    reduzindo significativamente a produtividade.
    """
    contagem = 0
    for t in dados_climaticos["temp_max"]:
        if t > limite:
            contagem += 1
    return contagem


def risco_geada(dados_climaticos, temp_min_risco=2.0):
    """
    CALCULA a porcentagem de dias com temperatura minima abaixo do limiar de geada.
    
    PARAMETROS:
        dados_climaticos (dict): dados climaticos padronizados.
        temp_min_risco (float): temperatura minima em Celsius considerada
            risco de geada (padrao=2.0°C — geada fraca; geada forte e <0°C).
    
    RETORNA: float — porcentagem de dias com risco (ex: 5.5 significa 5.5%).
        Retorna 0.0 se nao houver dados.
    
    MOTIVO DOS PARAMETROS:
    temp_min_risco=2.0°C: a 2°C ja ha risco de geada branca (formacao de
    gelo na superficie das folhas), que queima tecidos vegetais.
    Em fases sensiveis (VE-V3, floracao), isso pode destruir a lavoura.
    """
    n = len(dados_climaticos["datas"])
    if n == 0:
        return 0.0
    dias_com_risco = 0
    for t in dados_climaticos["temp_min"]:
        if t <= temp_min_risco:
            dias_com_risco += 1
    return round((dias_com_risco / n) * 100, 1)


def amplitude_termica(dados_climaticos):
    """
    CALCULA a amplitude termica diaria (diferenca entre max e min) para cada dia.
    
    PARAMETROS:
        dados_climaticos (dict): dados climaticos padronizados.
    
    RETORNA: list[float] — amplitudes termicas diarias em Celsius.
        Ex: [12.5, 10.3, 14.1, ...] significa que no primeiro dia
        a temperatura variou 12.5°C entre a minima e a maxima.
    
    MOTIVO:
    A amplitude termica influencia a formacao de orvalho, a incidencia de
    doencas fungicas e o desenvolvimento radicular. Amplitudes muito altas
    (>15°C) indicam instabilidade atmosferica e podem prejudicar culturas.
    """
    amplitudes = []
    for i in range(len(dados_climaticos["datas"])):
        amp = dados_climaticos["temp_max"][i] - dados_climaticos["temp_min"][i]
        amplitudes.append(round(amp, 1))
    return amplitudes


def resumo_climatico(dados_climaticos):
    """
    CONSOLIDA varios indicadores climaticos em um unico dicionario resumido.
    
    PARAMETROS:
        dados_climaticos (dict): saida padronizada de clima.py:buscar_dados_meteo().
    
    RETORNA: dict com 6 chaves:
        "temp_media_7dias" (float): media movel dos ultimos 7 dias (tendencia atual).
        "temp_media_geral" (float): media de todo o periodo (visao historica).
        "precip_total" (float): precipitacao acumulada total em mm.
        "dias_consecutivos_secos" (int): dias atuais sem chuva significativa.
        "risco_geada_pct" (float): porcentagem de dias com risco de geada.
        "amplitude_media" (float): media da amplitude termica diaria.
    Retorna dict vazio {} se nao houver dados.
    
    MOTIVO:
    Consolida as 6 funcoes acima em um unico dict para facilitar o consumo
    pelos modulos seguintes (scores.py, recomendador.py, analisar.py).
    Cada score ou recomendacao usa um subconjunto diferente destes indices.
    """
    if not dados_climaticos or not dados_climaticos["datas"]:
        return {}
    n = len(dados_climaticos["datas"])
    medias_temp = media_movel_temperatura(dados_climaticos, janela=7)
    temp_media_geral = round(sum(
        (dados_climaticos["temp_max"][i] + dados_climaticos["temp_min"][i]) / 2
        for i in range(n)
    ) / n, 1)
    ampls = amplitude_termica(dados_climaticos)
    return {
        "temp_media_7dias": round(medias_temp[-1], 1) if medias_temp else 0,
        "temp_media_geral": temp_media_geral,
        "precip_total": round(sum(dados_climaticos["precip"]), 1),
        "dias_consecutivos_secos": dias_consecutivos_secos(dados_climaticos),
        "risco_geada_pct": risco_geada(dados_climaticos),
        "amplitude_media": round(sum(ampls) / len(ampls), 1) if ampls else 0
    }
