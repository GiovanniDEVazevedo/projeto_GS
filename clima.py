import requests
from datetime import datetime, timedelta


def coordenadas():
    """
    PERGUNTA AO USUARIO as coordenadas geograficas (latitude e longitude) da propriedade.
    
    PARAMETROS: nenhum — entrada via terminal com validacao.
    
    RETORNA: tuple(float, float) — (latitude, longitude) dentro dos limites do Brasil.
    
    MOTIVO DOS PARAMETROS:
    Nao recebe parametros porque coleta dados interativamente.
    As coordenadas sao essenciais para:
    - buscar dados climaticos especificos do local (clima.py:buscar_dados_meteo)
    - identificar o estado para potencial produtivo (produtividade.py:identificar_estado)
    - buscar imagens de satelite NDVI (ndvi.py:buscar_ndvi)
    
    A validacao garante que as coordenadas estejam dentro do territorio brasileiro
    (lat: -33 a 5, lon: -73 a -34) para evitar erros nas APIs externas.
    """
    while True:
        try:
            lat = float(input("digite uma latitude (de -33 a 5)"))
            if lat < -33 or lat > 5:
                print("Latitude invalida. O Brasil esta entre -33 e 5.")
                continue
            lon = float(input("digite uma longitude (de -73 a -34)"))
            if lon < -73 or lon > -34:
                print("Longitude invalida. O Brasil esta entre -73 e -34.")
                continue
            return lat, lon
        except ValueError:
            print("Digite um numero valido (ex: -23.55).")


def buscar_dados_meteo(lat, lon, dias=365):
    """
    FUNCAO PRINCIPAL: obtem dados climaticos historicos para uma localizacao.
    
    Usa estrategia de 3 niveis (cascata): tenta a melhor API primeiro, depois
    fallbacks caso a anterior falhe.
    
    PARAMETROS:
        lat (float): latitude no formato decimal (ex: -12.55 para Sorriso/MT).
        lon (float): longitude no formato decimal (ex: -55.72 para Sorriso/MT).
        dias (int): quantidade de dias no passado para buscar (padrao 365 = 1 ano).
                    365 dias cobre um ciclo agricola completo.
    
    RETORNA: dict — dados climaticos padronizados com as chaves:
        "datas" (list[str]): datas no formato YYYY-MM-DD.
        "temp_max" (list[float]): temperatura maxima diaria em Celsius.
        "temp_min" (list[float]): temperatura minima diaria em Celsius.
        "precip" (list[float]): precipitacao diaria em mm.
        "fonte" (str): nome da API que forneceu os dados ("Open-Meteo Archive",
                       "NASA POWER" ou "Open-Meteo Forecast").
    Ou None se todas as 3 APIs falharem.
    
    MOTIVO DOS PARAMETROS:
    lat/lon: necessarios para qualquer API meteorologica — cada ponto geografico
    tem condicoes climaticas unicas.
    dias=365: um ano completo de dados historicos permite analisar sasonalidade,
    calcular medias confiaveis e detectar eventos extremos (geada, seca, estresse).
    
    ESTRATEGIA DE CASCATA (3 niveis):
    1. Open-Meteo Archive (melhor): dados historicos completos, 365 dias.
    2. NASA POWER (fallback medio): mesma cobertura, API mais lenta (30s timeout).
    3. Open-Meteo Forecast (fallback curto): so 92 dias, usado apenas em emergencia.
    """
    hoje = datetime.now()
    fim = hoje - timedelta(days=1)
    inicio = fim - timedelta(days=dias - 1)
    return (_tentar_archive_api(lat, lon, inicio, fim)
            or _tentar_nasa_api(lat, lon, inicio, fim)
            or _tentar_forecast_api(lat, lon))


def _tentar_archive_api(lat, lon, inicio, fim):
    """
    PRIMEIRO NIVEL da cascata: API Open-Meteo Archive.
    
    PARAMETROS:
        lat (float): latitude decimal.
        lon (float): longitude decimal.
        inicio (datetime): data de inicio do periodo (hoje - 365 dias).
        fim (datetime): data de fim do periodo (ontem).
    
    RETORNA: dict padronizado via _extrair_dados() ou None em caso de erro.
    
    MOTIVO:
    Open-Meteo Archive e a API mais completa para dados historicos no Brasil,
    gratuita, sem limite de requisicoes, com resolucao de ~11km. Suporta
    periodos de ate 365 dias completos com dados diarios de temperatura e
    precipitacao.
    
    POR QUE ESSES PARAMETROS:
    inicio/fim: definem a janela temporal exata para garantir dados consistentes
    e evitar lacunas. O formato ISO (YYYY-MM-DD) e exigido pela API.
    timeout=15s: tempo limite para nao travar o programa se a API estiver lenta.
    """
    try:
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": inicio.strftime("%Y-%m-%d"),
            "end_date": fim.strftime("%Y-%m-%d"),
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "America/Sao_Paulo"
        }
        resposta = requests.get(url, params=params, timeout=15)
        resposta.raise_for_status()
        dados = resposta.json()
        return _extrair_dados(dados, "Open-Meteo Archive")
    except requests.exceptions.RequestException:
        print("Erro na API Open-Meteo Archive — tentando fallback...")
        return None


def _tentar_forecast_api(lat, lon):
    """
    TERCEIRO NIVEL (fallback final): API Open-Meteo Forecast.
    
    PARAMETROS:
        lat (float): latitude decimal.
        lon (float): longitude decimal.
    
    RETORNA: dict padronizado com no maximo 92 dias de dados, ou None em erro.
    
    MOTIVO:
    Usada apenas quando Archive e NASA falham. E uma API de previsao do tempo,
    mas permite o parametro past_days=92 para obter dados recentes. So cobre
    os ultimos 92 dias, o que e suficiente para analises basicas (fase atual,
    estresse recente) mas nao para medias historicas anuais.
    
    POR QUE past_days=92:
    E o limite maximo permitido pela API da Open-Meteo para dados passados.
    """
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "America/Sao_Paulo",
            "past_days": 92
        }
        resposta = requests.get(url, params=params, timeout=15)
        resposta.raise_for_status()
        dados = resposta.json()
        return _extrair_dados(dados, "Open-Meteo Forecast")
    except requests.exceptions.RequestException:
        print("Erro na API Open-Meteo Forecast — sem dados climaticos.")
        return None


def _tentar_nasa_api(lat, lon, inicio, fim):
    """
    SEGUNDO NIVEL da cascata: API NASA POWER (fallback medio).
    
    PARAMETROS:
        lat (float): latitude decimal.
        lon (float): longitude decimal.
        inicio (datetime): data de inicio do periodo.
        fim (datetime): data de fim do periodo.
    
    RETORNA: dict padronizado (mesma estrutura) ou None em erro.
    
    MOTIVO:
    NASA POWER e uma API de reanalise climatica global com dados desde 1981.
    Cobre o mesmo periodo de 365 dias, mas e mais lenta (timeout 30s) e o
    formato JSON e diferente do Open-Meteo, exigindo parse manual.
    Fator de correcao: PRECTOTCORR (precipitacao) vem em mm/dia, igual ao
    Open-Meteo, entao nao precisa de conversao.
    
    POR QUE timeout=30s:
    A API da NASA e significativamente mais lenta que Open-Meteo.
    """
    try:
        url = "https://power.larc.nasa.gov/api/temporal/daily/point"
        params = {
            "parameters": "T2M_MAX,T2M_MIN,PRECTOTCORR",
            "community": "AG",
            "latitude": lat,
            "longitude": lon,
            "startDate": inicio.strftime("%Y%m%d"),
            "endDate": fim.strftime("%Y%m%d"),
            "format": "JSON"
        }
        resposta = requests.get(url, params=params, timeout=30)
        resposta.raise_for_status()
        dados = resposta.json()
        # O JSON da NASA tem estrutura aninhada diferente do Open-Meteo:
        # properties > parameter > T2M_MAX e um dict {data: valor}
        datas_ordenadas = sorted(dados["properties"]["parameter"]["T2M_MAX"].keys())
        maximas = []
        minimas = []
        precipitacao = []
        for data in datas_ordenadas:
            maximas.append(dados["properties"]["parameter"]["T2M_MAX"].get(data, 0))
            minimas.append(dados["properties"]["parameter"]["T2M_MIN"].get(data, 0))
            precipitacao.append(dados["properties"]["parameter"]["PRECTOTCORR"].get(data, 0))
        return {
            "datas": datas_ordenadas,
            "temp_max": maximas,
            "temp_min": minimas,
            "precip": precipitacao,
            "fonte": "NASA POWER"
        }
    except requests.exceptions.RequestException:
        print("Erro na API NASA POWER — tentando ultimo fallback...")
        return None


def _extrair_dados(dados, fonte="Open-Meteo"):
    """
    FUNCAO AUXILIAR: padroniza o JSON retornado pelas APIs Open-Meteo.
    
    PARAMETROS:
        dados (dict): JSON decodificado da resposta da API.
        fonte (str): nome da API de origem para rastreamento.
    
    RETORNA: dict com 4 listas sincronizadas + fonte:
        "datas": list[str] — datas no formato YYYY-MM-DD.
        "temp_max": list[float] — temperaturas maximas diarias.
        "temp_min": list[float] — temperaturas minimas diarias.
        "precip": list[float] — precipitacao diaria em mm.
        "fonte": str — identificacao da origem dos dados.
    
    MOTIVO:
    As APIs do Open-Meteo retornam None para dias sem dado (ex: futuro).
    Esta funcao converte None para 0 para evitar erros nos calculos
    estatisticos de indices.py.
    """
    maximas = [v if v is not None else 0 for v in dados["daily"]["temperature_2m_max"]]
    minimas = [v if v is not None else 0 for v in dados["daily"]["temperature_2m_min"]]
    precipitacao = [v if v is not None else 0 for v in dados["daily"]["precipitation_sum"]]
    return {
        "datas": dados["daily"]["time"],
        "temp_max": maximas,
        "temp_min": minimas,
        "precip": precipitacao,
        "fonte": fonte
    }


def resumo(dados):
    """
    EXIBE UM RESUMO ESTATISTICO BASICO no terminal para uso direto pelo usuario.
    
    PARAMETROS:
        dados (dict): saida padronizada de buscar_dados_meteo().
    
    RETORNA: None — apenas imprime na tela.
    
    MOTIVO DOS PARAMETROS:
    Recebe o dict completo de dados climaticos para extrair e exibir:
    - Medias de temperatura (maxima, minima)
    - Valores absolutos extremos
    - Precipitacao total e media
    - Dias sem chuva (indicador de seca)
    - Dias com estresse termico (>35°C)
    - Dias com risco de geada (<4°C)
    """
    if not dados or not dados["datas"]:
        print("Nenhum dado disponivel.")
        return
    n = len(dados["datas"])
    temp_max = dados["temp_max"]
    temp_min = dados["temp_min"]
    precip = dados["precip"]

    temp_max_media = sum(temp_max) / n
    temp_min_media = sum(temp_min) / n
    temp_max_abs = max(temp_max)
    temp_min_abs = min(temp_min)
    precip_total = sum(precip)
    precip_media = precip_total / n

    dias_sem_chuva = sum(1 for p in precip if p == 0)
    dias_com_chuva = n - dias_sem_chuva
    dias_estresse = sum(1 for t in temp_max if t > 35)
    dias_geada = sum(1 for t in temp_min if t < 4)

    print(f"\n--- Resumo Climatico ({n} dias) ---")
    print(f"Periodo: {dados['datas'][0]} a {dados['datas'][-1]}")
    print()
    print("Temperaturas:")
    print(f"  Maxima media:  {temp_max_media:.1f}C    Maxima absoluta: {temp_max_abs:.1f}C")
    print(f"  Minima media:  {temp_min_media:.1f}C    Minima absoluta: {temp_min_abs:.1f}C")
    print(f"  Dias com estresse (>35C): {dias_estresse} dias")
    print(f"  Dias com risco geada (<4C): {dias_geada} dias")
    print()
    print("Precipitacao:")
    print(f"  Total acumulado: {precip_total:.1f} mm")
    print(f"  Media diaria:     {precip_media:.1f} mm")
    print(f"  Dias com chuva:   {dias_com_chuva} dias")
    print(f"  Dias sem chuva:   {dias_sem_chuva} dias")

if __name__ == "__main__":
    print("=== SafraSmart - Dados Climaticos ===")
    lat, lon = coordenadas()
    dados = buscar_dados_meteo(lat, lon)
    resumo(dados)
