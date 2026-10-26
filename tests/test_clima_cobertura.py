from datetime import date, datetime, timedelta
from unittest.mock import Mock

import pytest

from safrasmart import clima
from safrasmart.analisar import analisar
from safrasmart.scores import score_clima, score_geral
from safrasmart.worker import processar_um
from safrasmart.validacao import validar


def serie(inicio, n, fonte='Arquivo', chuva=2):
    return {'datas': [(inicio + timedelta(days=i)).isoformat() for i in range(n)],
            'temp_max': [30.] * n, 'temp_min': [20.] * n, 'precip': [chuva] * n, 'fonte': fonte}


def fontes(monkeypatch, archive, forecast, nasa=None):
    monkeypatch.setattr(clima, 'hoje_local', lambda: date(2026, 10, 26))
    mocks = [Mock(return_value=x) for x in (archive, forecast, nasa)]
    for nome, mock in zip(('_tentar_archive_api', '_tentar_forecast_api', '_tentar_nasa_api'), mocks):
        monkeypatch.setattr(clima, nome, mock)
    return mocks


def test_archive_parcial_nao_bloqueia_fallback_recente(monkeypatch):
    arquivo = serie(date(2026, 10, 1), 25)
    for campo in ('temp_max', 'temp_min', 'precip'):
        arquivo[campo][-5:] = [None] * 5
    forecast = serie(date(2026, 10, 20), 8, fonte='Modelo recente', chuva=4)
    mocks = fontes(monkeypatch, arquivo, forecast)
    r = clima.buscar_dados_meteo(-12.55, -55.72, dias=25, fim=date(2026, 10, 25), inicio_necessario=date(2026, 10, 1))
    assert r['datas'][-1] == '2026-10-25'
    assert r['precip'][:20] == [2.] * 20
    assert r['precip'][-5:] == [4.] * 5
    assert r['fonte_por_dia'][-5:] == ['Modelo recente'] * 5
    assert r['fontes_utilizadas'] == ['Arquivo', 'Modelo recente']
    mocks[1].assert_called_once()
    mocks[2].assert_not_called()
    # Nenhum dado de hoje/amanhã do Forecast foi usado como passado.
    assert len(r['datas']) == 25
    assert score_clima(r, {}, {'temp_ideal': (20, 30), 'precip_ideal_mm': (30, 90)})['valor'] is not None


def test_fonte_completa_na_janela_nao_exige_consultas_desnecessarias(monkeypatch):
    # O início anual tem lacunas, mas a janela efetivamente analisada está completa.
    arquivo = serie(date(2026, 10, 10), 16)
    mocks = fontes(monkeypatch, arquivo, None)
    r = clima.buscar_dados_meteo(0, 0, dias=365, fim=date(2026, 10, 25), inicio_necessario=date(2026, 10, 10))
    assert r['precip'][-16:] == [2.] * 16
    assert r['precip'][0] is None
    mocks[1].assert_not_called()
    mocks[2].assert_not_called()


def test_fallback_nasa_para_periodo_antigo_sem_forecast(monkeypatch):
    arquivo = serie(date(2025, 1, 1), 10)
    arquivo['precip'][-1] = None
    nasa = serie(date(2025, 1, 1), 10, fonte='NASA', chuva=5)
    mocks = fontes(monkeypatch, arquivo, None, nasa)
    r = clima.buscar_dados_meteo(0, 0, dias=10, fim=date(2025, 1, 10))
    mocks[1].assert_not_called()
    mocks[2].assert_called_once()
    assert r['precip'][-1] == 5
    assert r['fonte_por_dia'][-1] == 'NASA'
    assert r['precip'][0] == 2  # não substituir dados completos já existentes


def test_calendario_invalido_tenta_outra_fonte(monkeypatch):
    fontes(monkeypatch, {'datas': ['data-invalida'], 'fonte': 'Arquivo'}, serie(date(2026, 10, 1), 25))
    r = clima.buscar_dados_meteo(0, 0, dias=25, fim=date(2026, 10, 25))
    assert r['precip'] == [2.] * 25
    assert r['tentativas_fontes'][0]['status'] == 'indisponivel'


def test_fontes_falham_sem_inventar_dados(monkeypatch):
    fontes(monkeypatch, None, None)
    assert clima.buscar_dados_meteo(0, 0) is None


def test_lacunas_persistentes_permanecem_none(monkeypatch):
    arquivo = serie(date(2026, 10, 1), 25)
    arquivo['precip'][-1] = None
    fontes(monkeypatch, arquivo, None)
    r = clima.buscar_dados_meteo(0, 0, dias=25, fim=date(2026, 10, 25))
    assert r['precip'][-1] is None
    score = score_clima(r, {}, {'temp_ideal': (20, 30)})
    assert score['valor'] is None
    assert score['detalhes']['codigo'] == 'COBERTURA_INSUFICIENTE'
    assert '24 de 25 dias' in score['detalhes']['motivo']
    assert score_geral({'clima': score})['detalhes']['motivo'] == score['detalhes']['motivo']


@pytest.mark.parametrize('plantio,codigo', [('2026-10-26', 'PLANTIO_HOJE'), ('2026-10-30', 'PLANTIO_FUTURO'), ('2026-10-24', 'JANELA_CURTA')])
def test_plantio_recente_ou_futuro_explica_limite_sem_gerar_sintese(monkeypatch, plantio, codigo):
    monkeypatch.setattr('safrasmart.analisar.buscar_dados_meteo', lambda *a, **kw: serie(date(2026, 9, 1), 56))
    r = analisar(-23, -46, 'soja', datetime.fromisoformat(plantio), 'misto', 'sequeiro', usar_ndvi=False, hoje=date(2026, 10, 26))
    assert r['scores']['valor'] is None
    assert r['scores']['detalhes']['codigo'] == codigo
    motivo = r['scores']['parciais']['clima']['detalhes']['motivo']
    assert r['recomendacao']['recomendacao_principal']['texto'] == motivo
    assert motivo in r['erros']


def test_indisponibilidade_climatica_nao_e_confundida_com_chave_gee(monkeypatch):
    monkeypatch.setattr('safrasmart.analisar.buscar_dados_meteo', lambda *a, **kw: None)
    r = analisar(-23, -46, 'soja', datetime(2026, 10, 1), 'misto', 'sequeiro', usar_ndvi=False, hoje=date(2026, 10, 26))
    assert r['scores']['detalhes']['codigo'] == 'CLIMA_INDISPONIVEL'
    assert 'APIs de clima' in r['recomendacao']['recomendacao_principal']['texto']


def test_clima_suficiente_sem_ndvi_continua_sintese(monkeypatch):
    monkeypatch.setattr('safrasmart.analisar.buscar_dados_meteo', lambda *a, **kw: serie(date(2026, 10, 1), 25))
    r = analisar(-23, -46, 'soja', datetime(2026, 10, 1), 'misto', 'sequeiro', usar_ndvi=False, hoje=date(2026, 10, 26))
    # Fase V4-V6 a partir do dia 20 -> cinco dias nessa fase: ainda é janela curta.
    assert r['scores']['detalhes']['codigo'] == 'JANELA_CURTA'
    r = analisar(-23, -46, 'soja', datetime(2026, 10, 10), 'misto', 'sequeiro', usar_ndvi=False, hoje=date(2026, 10, 26))
    assert r['scores']['valor'] is not None
    assert r['recomendacao']['status'] != 'SEM_DADOS'
    assert r['ndvi'] is None


def test_versao_motor_concluido_corresponde_ao_resultado(app, payload):
    repo = app.extensions['repo']
    repo.registrar('owner', validar(payload))
    processar_um(repo, executar=lambda _: {'metadata': {'versao_motor': '2.0.1'}})
    assert repo.obter('owner', payload['id'])['versao_motor'] == '2.0.1'
