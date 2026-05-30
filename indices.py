def media_movel_temperatura(dados_climaticos, janela=7):
    medias=[]

    for i in range(len(dados_climaticos)):
        inicio = max(0, i - janela + 1)
        fatia = dados_climaticos[inicio + 1]
        tempo_total = sum(d.tempo_media for d in fatia)
        medias.append(tempo_total / len(fatia))
    return medias
def precip_acumulada(dados_climaticos, dia_inicio, dia_fim):
    if dia_inicio < 0 or dia_fim >= len(dados_climaticos):
        return 0.0
    total = 0.0
    for i in range(dia_inicio , dia_fim + 1):
        total += dados_climaticos[i].precipitacao_mm
    return total
def dias_sem_chuva(dados_climaticos, limiar_mm):
    contador = 0 
    for dado in reversed(dados_climaticos):
        if dado.precipitacao_mm < limiar_mm:
            contador += 1
        else:
            break
    return contador
def dias_estresse_termico(dados_climaticos, limite = 35.0):
    contagem = 0 
    for dado in dados_climaticos:
        if dado.temp_max > limite:
            contagem +=1
    return contagem
def risco_geada(dados_climaticos, temp_min_risco=2.0):
    dias_com_risco = 0
    for dado in dados_climaticos:
        if dado.temp_min <= temp_min_risco:
            dias_com_risco += 1 
    return round((dias_com_risco / len(dados_climaticos)) * 100, 1)
def amplitude_termica(dados_climaticos):
    amplitudes = []
    for dado in dados_climaticos:
        amp = dado.temp_max - dado.temp_min
        amplitudes.append(round(amp, 1))
    return amplitudes
def resumo_climatioco(dados_climaticos):
    if not dados_climaticos:
        return {}
    medias_temp = media_movel_temperatura(dados_climaticos, janela=7)
    return{
        "temp_media_7dias": round(medias_temp[-1], 1) if medias_temp else 0,
        "temp_media_geral": round(sum(d.temp_media for d in dados_climaticos) / len(dados_climaticos), 1),
        "precip_total": round(sum(d.precipitacao_mm for d in dados_climaticos), 1),
        "dias_sem_chuva": dias_sem_chuva(dados_climaticos),
        "risco_geada_pct": risco_geada(dados_climaticos),
        "amplitude_media": round(sum(amplitude_termica(dados_climaticos))/len(dados_climaticos),1)
        }
