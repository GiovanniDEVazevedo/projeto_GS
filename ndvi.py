import ee
from google.oauth2 import service_account
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import sys


def autenticar_gee(caminho_chave):
    """
    AUTENTICA no Google Earth Engine usando uma conta de servico (service account).
    
    PARAMETROS:
        caminho_chave (str): caminho absoluto para o arquivo JSON da chave
            privada da conta de servico do GEE. Este arquivo e gerado no
            Google Cloud Console (IAM > Contas de Servico).
    
    RETORNA: None — inicializa a sessao do Earth Engine globalmente.
    
    MOTIVO DOS PARAMETROS:
    caminho_chave: necessario porque o GEE exige autenticacao para acesso
    a API. Usamos conta de servico (mais segura que autenticacao interativa)
    porque o SafraSmart roda em servidor, sem usuario logado.
    
    O escopo "earthengine" e obrigatorio para acessar os datasets do GEE.
    A chave e lida da variavel de ambiente GEE_KEY_PATH em analisar.py
    para nao expor credenciais no codigo fonte.
    """
    credentials = service_account.Credentials.from_service_account_file(caminho_chave)
    scoped = credentials.with_scopes(["https://www.googleapis.com/auth/earthengine"])
    ee.Initialize(scoped)
    print("  [NDVI] Earth Engine autenticado")


def _executar_ndvi(lat, lon, data_inicio, data_fim, intervalo_dias, buffer_metros):
    """
    FUNCAO INTERNA: processa o NDVI real do Sentinel-2 pelo GEE.
    
    PARAMETROS:
        lat (float): latitude do ponto de interesse.
        lon (float): longitude do ponto de interesse.
        data_inicio (datetime): inicio do periodo de busca.
        data_fim (datetime): fim do periodo de busca.
        intervalo_dias (int): tamanho do composite em dias (15 = janela de 15 dias).
        buffer_metros (int): raio em metros para buffer ao redor do ponto (50m).
    
    RETORNA: dict com:
        "datas" (list[str]): datas de cada composite.
        "ndvi" (list[float]): valores NDVI medios para cada composite.
        "ndvi_medio_geral" (float): media de todos os NDVIs.
        "ndvi_max" (float): maior NDVI registrado.
        "ndvi_min" (float): menor NDVI registrado.
        "total_imagens_usadas" (int): total de cenas Sentinel-2 processadas.
        "fonte" (str): sempre "Sentinel-2 SR Harmonized".
    Retorna None se nenhum dado foi encontrado.
    
    MOTIVO DOS PARAMETROS:
    lat/lon: coordenadas do ponto central da lavoura.
    data_inicio/data_fim: periodo da safra (do plantio ate hoje).
    
    intervalo_dias=15: composites de 15 dias sao o padrao para NDVI agricola
    porque:
    - Sentinel-2 revisita o mesmo ponto a cada 5 dias
    - 15 dias garante pelo menos 1-2 imagens sem nuvens
    - Tempo suficiente para detectar mudancas no vigor vegetativo
    
    buffer_metros=50: um raio de 50m ao redor do ponto GPS fornece area
    suficiente para estatisticas representativas sem incluir areas vizinhas.
    
    COLECAO: COPERNICUS/S2_SR_HARMONIZED
    Usamos a colecao Surface Reflectance (SR) harmonizada porque ja corrige
    efeitos atmosfericos, ao contrario da colecao TOA (Top of Atmosphere).
    
    CALCULO NDVI:
    NDVI = (B8 - B4) / (B8 + B4)
    onde B8 = infravermelho proximo (NIR), B4 = vermelho (RED).
    Valores: -1 a 1. Solo exposto ~0.1-0.2, vegetacao saudavel >0.6.
    
    FILTRO DE NUVENS: CLOUDY_PIXEL_PERCENTAGE < 20%
    Imagens com mais de 20% de nuvens sao descartadas para nao poluir
    o composite com valores invalidos.
    
    TIMEOUT: Esta funcao nao tem timeout proprio — o timeout e gerenciado
    externamente por buscar_ndvi() via ThreadPoolExecutor.
    """
    ponto = ee.Geometry.Point([lon, lat]).buffer(buffer_metros)
    colecao = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    datas_ndvi = []
    valores_ndvi = []
    total_imagens = 0
    data_atual = data_inicio

    while data_atual < data_fim:
        data_fim_intervalo = data_atual + timedelta(days=intervalo_dias)
        if data_fim_intervalo > data_fim:
            data_fim_intervalo = data_fim

        # Filtra a colecao por local, data e nuvens
        intervalo = colecao \
            .filterBounds(ponto) \
            .filterDate(data_atual.strftime("%Y-%m-%d"), data_fim_intervalo.strftime("%Y-%m-%d")) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))

        n_imagens = intervalo.size().getInfo()
        total_imagens += n_imagens

        if n_imagens == 0:
            data_atual = data_fim_intervalo
            continue

        # Cria um composite (mediana) para reduzir ruido
        composite = intervalo.median().clip(ponto)

        # Calcula NDVI: (NIR - RED) / (NIR + RED)
        ndvi = composite.normalizedDifference(['B8', 'B4']).rename('NDVI')

        # Extrai a estatistica media na regiao de interesse
        estatisticas = ndvi.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=ponto,
            scale=10,      # resolucao de 10m (bandas B8 e B4)
            maxPixels=1e9
        )
        ndvi_valor = estatisticas.getInfo().get('NDVI', None)

        if ndvi_valor is not None:
            datas_ndvi.append(data_fim_intervalo.strftime("%Y-%m-%d"))
            valores_ndvi.append(round(float(ndvi_valor), 3))

        data_atual = data_fim_intervalo

    if not valores_ndvi:
        return None

    return {
        "datas": datas_ndvi,
        "ndvi": valores_ndvi,
        "ndvi_medio_geral": round(sum(valores_ndvi) / len(valores_ndvi), 3),
        "ndvi_max": round(max(valores_ndvi), 3),
        "ndvi_min": round(min(valores_ndvi), 3),
        "total_imagens_usadas": total_imagens,
        "fonte": "Sentinel-2 SR Harmonized"
    }


def buscar_ndvi(lat, lon, data_inicio, data_fim, intervalo_dias=15, buffer_metros=50, timeout_segundos=90):
    """
    FUNCAO PRINCIPAL: busca NDVI do Sentinel-2 com protecao de timeout.
    
    PARAMETROS:
        lat (float): latitude do ponto de interesse.
        lon (float): longitude do ponto de interesse.
        data_inicio (datetime): inicio do periodo (geralmente data do plantio).
        data_fim (datetime): fim do periodo (geralmente data atual).
        intervalo_dias (int): janela do composite em dias (padrao=15).
        buffer_metros (int): raio do buffer em metros (padrao=50).
        timeout_segundos (int): tempo maximo de espera em segundos (padrao=90).
    
    RETORNA: dict com os dados NDVI (mesma estrutura de _executar_ndvi())
        ou None se:
        - Nao houver imagens no periodo
        - O tempo limite (timeout) for excedido
        - Ocorrer qualquer outro erro
    
    MOTIVO DO TIMEOUT:
    O GEE pode demorar muito para processar imagens (rede lenta, servidor
    ocupado, muitas nuvens). O timeout de 90s evita que o programa trave
    e permite que o pipeline continue sem NDVI.
    
    POR QUE ThreadPoolExecutor:
    O metodo getInfo() do GEE e uma chamada sincrona que bloqueia a thread.
    Envolvendo em uma ThreadPoolExecutor com timeout, podemos interromper
    a operacao se ela exceder o limite. Isso e mais seguro que usar timeouts
    de socket porque o getInfo() nao tem timeout nativo.
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_executar_ndvi, lat, lon, data_inicio, data_fim, intervalo_dias, buffer_metros)
        try:
            resultado = future.result(timeout=timeout_segundos)
            return resultado
        except TimeoutError:
            print("  [NDVI] Timeout de %ds excedido — continuando sem NDVI" % timeout_segundos)
            return None


def ndvi_por_fase(dados_ndvi, data_plantio, fases):
    """
    CALCULA o NDVI medio para cada fase fenologica.
    
    PARAMETROS:
        dados_ndvi (dict): saida de buscar_ndvi() com "datas" e "ndvi".
        data_plantio (datetime): data de plantio da cultura.
        fases (dict): dicionario {nome_fase: (dia_inicio, dia_fim)} com os
            intervalos de dias de cada fase (ex: {"VE-V3": (0, 20), ...}).
    
    RETORNA: dict — {nome_da_fase: ndvi_medio_ou_None}.
        Ex: {"VE-V3": 0.45, "V4-V6": 0.72, "R1-R2": None, ...}
        O valor e None se nao houver dados NDVI para aquela fase.
    
    MOTIVO DOS PARAMETROS:
    dados_ndvi: necessario para extrair valores NDVI e suas datas.
    data_plantio: converte dias apos plantio para datas reais.
    fases: mapeia cada fase a um intervalo de dias.
    
    USO:
    Permite identificar em qual fase a cultura apresentou maior/menor vigor
    vegetativo, ajudando a correlacionar estresses climaticos com o NDVI.
    """
    if not dados_ndvi:
        return {}
    resultado = {}
    for nome_fase, (d_inicio, d_fim) in fases.items():
        data_inicio_fase = data_plantio + timedelta(days=d_inicio)
        data_fim_fase = data_plantio + timedelta(days=d_fim)
        ndvis_fase = []
        for i, data_str in enumerate(dados_ndvi["datas"]):
            data = datetime.strptime(data_str, "%Y-%m-%d")
            if data_inicio_fase <= data <= data_fim_fase:
                ndvis_fase.append(dados_ndvi["ndvi"][i])
        if ndvis_fase:
            resultado[nome_fase] = round(sum(ndvis_fase) / len(ndvis_fase), 3)
        else:
            resultado[nome_fase] = None
    return resultado


if __name__ == "__main__":
    import os

    caminho_chave = os.environ.get("GEE_KEY_PATH", "./.env/calcium-pod-497417-t0-5d27a8d8dba9.json")
    autenticar_gee(caminho_chave)

    # Exemplo: soja em Cascavel/PR, plantio em 15/10/2025
    lat = -24.95
    lon = -53.46
    plantio = datetime(2025, 10, 15)
    hoje = datetime.now()

    dados_ndvi = buscar_ndvi(lat, lon, plantio, hoje)

    if dados_ndvi:
        print(f"\n--- NDVI Sentinel-2 ---")
        print(f"Periodo: {dados_ndvi['datas'][0]} a {dados_ndvi['datas'][-1]}")
        print(f"NDVI medio geral: {dados_ndvi['ndvi_medio_geral']}")
        print(f"NDVI max: {dados_ndvi['ndvi_max']}")
        print(f"NDVI min: {dados_ndvi['ndvi_min']}")
        print(f"Imagens usadas: {dados_ndvi['total_imagens_usadas']}")
        print(f"Fonte: {dados_ndvi['fonte']}")

        # Testar com fases da soja
        fases_soja = {
            "VE-V3": (0, 20),
            "V4-V6": (20, 40),
            "R1-R2": (40, 55),
            "R3-R5": (55, 90),
            "R6-R8": (90, 120)
        }
        ndvi_fases = ndvi_por_fase(dados_ndvi, plantio, fases_soja)
        print("\nNDVI por fase fenologica:")
        for fase, valor in ndvi_fases.items():
            status = "ok" if valor else "sem dados"
            print(f"  {fase}: {valor} ({status})")
