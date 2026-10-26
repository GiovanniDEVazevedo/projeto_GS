from datetime import date, datetime, timedelta

import pytest
from safrasmart import clima
from safrasmart.analisar import analisar
from safrasmart.indices import (amplitude_termica, dias_consecutivos_secos, media_movel_temperatura,
                               precip_acumulada, recortar_periodo, resumo_climatico, risco_geada)
from safrasmart.regras import fase_atual
from safrasmart.scores import score_clima, score_geral


def serie(n=30, inicio=date(2026, 9, 1), precip=1.5):
    return {'datas': [(inicio + timedelta(days=i)).isoformat() for i in range(n)],
            'temp_max': [30.] * n, 'temp_min': [20.] * n, 'precip': [precip] * n, 'fonte': 'fixture'}


def test_null_nan_e_sentinela_nao_viram_zero():
    dados = clima._extrair_dados({'daily': {'time': ['2026-10-01', '2026-10-02'],
        'temperature_2m_max': [None, float('nan')], 'temperature_2m_min': [-999, 0], 'precipitation_sum': [0, -999]}})
    assert dados['temp_max'] == [None, None]
    assert dados['temp_min'] == [None, 0]
    assert dados['precip'] == [0, None]
    resumo = resumo_climatico(dados)
    assert resumo['temp_media_geral'] is None
    assert resumo['cobertura_temperatura'] == 0
    assert resumo['precip_total'] == 0
    assert resumo['precip_completa'] is False
    assert precip_acumulada(dados, 0, 1) is None
    assert risco_geada(dados) == 100
    assert media_movel_temperatura(dados) == [None, None]
    assert amplitude_termica(dados) == [None, None]


def test_calendario_preenche_lacunas_e_exclui_futuro():
    dados = {'datas': ['20261001', '20261003', '20261004'], 'temp_max': [30, 10, 31],
             'temp_min': [20, 20, 21], 'precip': [0, -999, 100], 'fonte': 'NASA POWER'}
    r = clima.alinhar_calendario(dados, date(2026, 10, 1), date(2026, 10, 3))
    assert r['datas'] == ['2026-10-01', '2026-10-02', '2026-10-03']
    assert r['temp_max'] == [30, None, None]  # máxima < mínima descartada
    assert r['precip'] == [0, None, None]
    assert dias_consecutivos_secos(r) is None


def test_lacuna_nao_estende_seca():
    dados = serie(5, precip=0)
    dados['precip'][2] = None
    assert dias_consecutivos_secos(dados) == 2
    dados['precip'] = [0] * 5
    dados['datas'][-2] = '2026-09-03'
    assert dias_consecutivos_secos(dados) == 1


def test_precip_mensal_nao_compara_com_anual():
    dados = serie(365)
    fase = {'temp_ideal': (20, 30), 'precip_ideal_mm': (30, 60)}
    score = score_clima(dados, resumo_climatico(dados), fase)
    assert score['valor'] == 10
    assert score['detalhes']['precip_equivalente_30dias'] == 45
    assert score_clima(serie(15), {}, fase)['valor'] == 10


def test_ausencia_e_cobertura_insuficiente_nao_geram_sintese():
    dados = serie()
    dados['precip'][3] = None
    sc = score_clima(dados, {}, {'temp_ideal': (20, 30)})
    assert sc['valor'] is None
    assert score_geral({'clima': sc, 'risco': {'valor': 10}})['status'] == 'SEM_DADOS'


def test_nasa_parametros_e_nodata(monkeypatch):
    class Resposta:
        def raise_for_status(self): pass
        def json(self):
            return {'properties': {'parameter': {'T2M_MAX': {'20261001': 30, '20261002': -999},
                'T2M_MIN': {'20261001': 20}, 'PRECTOTCORR': {'20261001': -999}}}}
    argumentos = {}
    def get(url, **kwargs):
        argumentos.update(kwargs['params'])
        return Resposta()
    monkeypatch.setattr(clima.requests, 'get', get)
    dados = clima._tentar_nasa_api(0, 0, date(2026, 10, 1), date(2026, 10, 2))
    assert argumentos['start'] == '20261001'
    assert argumentos['end'] == '20261002'
    assert 'startDate' not in argumentos
    assert dados['temp_min'][1] is None
    assert dados['precip'][0] is None


def test_clima_fora_do_periodo_nao_afeta_fase(monkeypatch):
    dados = serie(90, inicio=date(2026, 8, 1))
    # Extremo antes do plantio não deve gerar alerta da fase atual.
    dados['temp_min'][0] = -5
    dados['temp_max'][0] = 45
    monkeypatch.setattr('safrasmart.analisar.buscar_dados_meteo', lambda *a, **kw: dados)
    r = analisar(-23, -46, 'soja', datetime(2026, 10, 1), 'argiloso', 'sequeiro',
                 observacoes='Não tem lagarta', usar_ndvi=False, hoje=date(2026, 10, 12))
    assert r['indices']['periodo_inicio'] == '2026-10-01'
    assert r['indices']['periodo_fim'] == '2026-10-11'
    assert r['indices']['dias_estresse_termico'] == 0
    assert r['indices']['risco_geada_pct'] == 0
    assert not r['recomendacao']['alertas_ativos']


def test_fontes_falham_resultado_parcial_sem_conclusao(monkeypatch):
    monkeypatch.setattr('safrasmart.analisar.buscar_dados_meteo', lambda *a, **kw: None)
    r = analisar(-23, -46, 'soja', datetime(2026, 10, 1), 'argiloso', 'sequeiro',
                 observacoes='chuva boa e solo fértil', usar_ndvi=False, hoje=date(2026, 10, 26))
    assert r['status'] == 'parcial'
    assert r['scores']['valor'] is None
    assert r['recomendacao']['status'] == 'SEM_DADOS'
    assert r['confiabilidade']['modelo_validado'] is False


def test_data_futura_e_dia_bissexto(monkeypatch):
    monkeypatch.setattr('safrasmart.analisar.buscar_dados_meteo', lambda *a, **kw: None)
    for data_plantio in (datetime(2028, 2, 29), datetime(2024, 2, 29)):
        r = analisar(-23, -46, 'soja', data_plantio, 'misto', 'sequeiro', usar_ndvi=False, hoje=date(2026, 10, 26))
        assert r['recomendacao']['status'] == 'SEM_DADOS'


def test_fases_sem_sobreposicao_e_cultura_invalida():
    assert fase_atual('soja', 20)[0] == 'V4-V6'
    assert fase_atual('soja', 120)[0] == 'Pos-Safra'
    with pytest.raises(ValueError):
        fase_atual('banana', 10)
