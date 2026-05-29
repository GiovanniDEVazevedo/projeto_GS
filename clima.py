import requests
from datetime import datetime,timedelta





def coordenadas():
    while True:
        try:
            lat = float(input("digite uma latitude (de -33 a 5)"))
            if lat < -33 or lat > 5:
                print("Latitude invalida. O Brasil esta entre -33 e 5.")
                continue
            lon = float(input( "digite uma longitude (de -73 a -34)" )) 
            if lon < -73 or lon > -34:
                print("Longitude invalida. O Brasil esta entre -73 e -34.")
                continue
            return lat, lon
        except ValueError:
            print("Digite um numero valido (ex: -23.55).")

def buscar_dados_meteo(lat, lon , dias=365):
    hoje = datetime.now()
    fim = hoje - timedelta(days=1)
    inicio = fim - timedelta(days=dias -1)
    return _tentar_archive_api(lat, lon , inicio,fim) or _tentar_nasa_api(lat, lon , inicio,fim) or  _tentar_forecast_api(lat , lon) 

def _tentar_archive_api(lat, lon,inicio,fim):
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
        return _extrair_dados(dados)
    except requests.exceptions.RequestException:
        return print("Erro na api")
def _tentar_forecast_api(lat, lon):
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
        return _extrair_dados(dados)
    except requests.exceptions.RequestException:
        return print("Erro na api")
def _tentar_nasa_api(lat, lon, inicio, fim):
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
        datas_ordenadas = sorted(dados["properties"]["parameter"]["T2M_MAX"].keys())
        maximas = []
        minimas = []
        precipitacao = []
        for data in datas_ordenadas:
            maximas.append(dados["properties"]["parameter"]["T2M_MAX"].get(data, 0 ))
            minimas.append(dados["properties"]["parameter"]["T2M_MIN"].get(data, 0))
            precipitacao.append(dados["properties"]["parameter"]["PRECTOTCORR"].get(data, 0))
        return {
                "datas": datas_ordenadas,
                "temp_max": maximas,
                "temp_min": minimas,
                "precip": precipitacao
            }
    except requests.exceptions.RequestException:
        return print("Erro na api")




def _extrair_dados(dados):
    maximas = [v if v is not None else 0 for v in dados["daily"]["temperature_2m_max"]]
    minimas = [v if v is not None else 0 for v in dados["daily"]["temperature_2m_min"]]
    precipitacao = [v if v is not None else 0 for v in dados["daily"]["precipitation_sum"]]
    return {
        "datas": dados["daily"]["time"],
        "temp_max": maximas,
        "temp_min": minimas,
        "precip" : precipitacao
    }
def resumo(dados):
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
    
    dias_sem_chuva = sum(1 for p in precip if p==0)
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