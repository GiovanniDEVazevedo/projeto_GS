def media_movel_temperatura(dados_climaticos, janela=7):
    medias = []
    n = len(dados_climaticos["datas"])
    temps = []
    for i in range(n):
        temps.append((dados_climaticos["temp_max"][i] + dados_climaticos["temp_min"][i]) / 2)

    for i in range(n):
        inicio = max(0, i - janela + 1)
        fatia = temps[inicio:i+1]
        medias.append(round(sum(fatia) / len(fatia), 1))
    return medias

def precip_acumulada(dados_climaticos, dia_inicio, dia_fim):
    n = len(dados_climaticos["datas"])
    if dia_inicio < 0 or dia_fim >= n:
        return 0.0
    total = 0.0
    for i in range(dia_inicio, dia_fim + 1):
        total += dados_climaticos["precip"][i]
    return round(total, 1)

def dias_consecutivos_secos(dados_climaticos, limiar_mm=0.5):
    contador = 0
    n = len(dados_climaticos["datas"])
    for i in range(n - 1, -1, -1):
        if dados_climaticos["precip"][i] < limiar_mm:
            contador += 1
        else:
            break
    return contador

def dias_estresse_termico(dados_climaticos, limite=35.0):
    contagem = 0
    for t in dados_climaticos["temp_max"]:
        if t > limite:
            contagem += 1
    return contagem

def risco_geada(dados_climaticos, temp_min_risco=2.0):
    n = len(dados_climaticos["datas"])
    if n == 0:
        return 0.0
    dias_com_risco = 0
    for t in dados_climaticos["temp_min"]:
        if t <= temp_min_risco:
            dias_com_risco += 1
    return round((dias_com_risco / n) * 100, 1)

def amplitude_termica(dados_climaticos):
    amplitudes = []
    for i in range(len(dados_climaticos["datas"])):
        amp = dados_climaticos["temp_max"][i] - dados_climaticos["temp_min"][i]
        amplitudes.append(round(amp, 1))
    return amplitudes

def resumo_climatico(dados_climaticos):
    if not dados_climaticos or not dados_climaticos["datas"]:
        return {}
    n = len(dados_climaticos["datas"])
    medias_temp = media_movel_temperatura(dados_climaticos, janela=7)
    temp_media_geral = round(sum((dados_climaticos["temp_max"][i] + dados_climaticos["temp_min"][i]) / 2 for i in range(n)) / n, 1)
    ampls = amplitude_termica(dados_climaticos)
    return {
        "temp_media_7dias": round(medias_temp[-1], 1) if medias_temp else 0,
        "temp_media_geral": temp_media_geral,
        "precip_total": round(sum(dados_climaticos["precip"]), 1),
        "dias_consecutivos_secos": dias_consecutivos_secos(dados_climaticos),
        "risco_geada_pct": risco_geada(dados_climaticos),
        "amplitude_media": round(sum(ampls) / len(ampls), 1) if ampls else 0
    }
