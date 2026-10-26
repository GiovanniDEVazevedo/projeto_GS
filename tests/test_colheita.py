from datetime import date, datetime, timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from safrasmart.analisar import analisar
from safrasmart.colheita import planejar_colheita
from safrasmart.db import Analise
from safrasmart.validacao import EntradaInvalida, validar
from safrasmart.worker import processar_um


@pytest.mark.parametrize('alteracao', [
    {'data_colheita': '2026-02-30'}, {'data_colheita': '2026-09-30'},
    {'data_colheita': '2999-01-01'}, {'data_colheita': 123},
    {'data_colheita': '2026-10-02', 'colheita_realizada': False},
    {'colheita_realizada': True}, {'colheita_realizada': 'false'},
    {'colheita_realizada': 0}, {'data_colheita': []},
])
def test_rejeita_colheita_inconsistente(payload, alteracao):
    with pytest.raises(EntradaInvalida):
        validar({**payload, **alteracao})


def test_contrato_antigo_preserva_reenvio_idempotente(client, payload, headers):
    antigo = validar(payload)
    assert 'data_colheita' not in antigo
    assert 'colheita_realizada' not in antigo
    assert validar({**payload, 'data_colheita': None, 'colheita_realizada': None}) == antigo
    assert client.post('/api/analises', json=payload, headers=headers).status_code == 202
    assert client.post('/api/analises', json=payload, headers=headers).status_code == 202


def test_colheita_real_persistida_e_consultavel_apos_nova_conexao(client, app, payload, headers):
    entrada = {**payload, 'data_colheita': '2026-10-15'}
    assert client.post('/api/analises', json=entrada, headers=headers).status_code == 202
    repo = app.extensions['repo']
    with repo.session() as s:
        item = s.scalar(select(Analise))
        assert item.entrada['data_colheita'] == '2026-10-15'
        assert item.entrada['colheita_realizada'] is True
    # Mudança no estado da colheita exige uma nova análise, não sobrescreve o UUID.
    assert client.post('/api/analises', json={**entrada, 'data_colheita': '2026-10-16'}, headers=headers).status_code == 409
    assert processar_um(repo, executar=lambda d: {'colheita': {'data_colheita': d['data_colheita']}})
    assert client.get('/api/analises/' + payload['id'], headers=headers).json['resultado']['colheita']['data_colheita'] == '2026-10-15'


@pytest.mark.parametrize('cultura,primeiro,ultimo', [('soja', 90, 119), ('milho', 105, 139)])
def test_faixa_usa_maturacao_da_cultura_sem_estender_para_sempre(cultura, primeiro, ultimo):
    plantio = date(2026, 1, 1)
    r = planejar_colheita(cultura, plantio, plantio + timedelta(days=primeiro - 1), realizada=False)
    assert r['janela']['inicio'] == (plantio + timedelta(days=primeiro)).isoformat()
    assert r['janela']['fim'] == (plantio + timedelta(days=ultimo)).isoformat()
    assert r['status'] == 'AGUARDAR'
    assert planejar_colheita(cultura, plantio, plantio + timedelta(days=primeiro), realizada=False)['status'] == 'AVALIAR'
    assert planejar_colheita(cultura, plantio, plantio + timedelta(days=ultimo), realizada=False)['status'] == 'AVALIAR'
    depois = planejar_colheita(cultura, plantio, plantio + timedelta(days=ultimo + 1), realizada=False)
    assert depois['status'] == 'REVISAR'
    assert depois['realizada'] is False
    assert depois['progresso_ciclo_pct'] == 100
    assert depois['janela'] == r['janela']


def test_planejamento_antes_do_plantio_e_status_antigo_desconhecido():
    r = planejar_colheita('soja', date(2026, 11, 1), date(2026, 10, 26), realizada=False)
    assert r['status'] == 'PLANEJAMENTO'
    assert r['progresso_ciclo_pct'] == 0
    assert all(f['estado'] == 'futura' for f in r['fases'])
    antigo = planejar_colheita('soja', date(2026, 1, 1), date(2026, 10, 26))
    assert antigo['realizada'] is None
    assert antigo['status'] == 'NAO_INFORMADA'


def test_colheita_corta_clima_e_ndvi_na_data_informada(monkeypatch):
    buscar = Mock(return_value=None)
    ndvi = Mock(return_value=None)
    monkeypatch.setattr('safrasmart.analisar.buscar_dados_meteo', buscar)
    monkeypatch.setattr('safrasmart.analisar.gee_configurado', lambda: True)
    monkeypatch.setattr('safrasmart.ndvi.buscar_ndvi', ndvi)
    r = analisar(-12, -55, 'soja', datetime(2026, 7, 1), 'argiloso', 'sequeiro',
                 data_colheita='2026-10-10', hoje=date(2026, 10, 26))
    assert buscar.call_args.kwargs['fim'] == date(2026, 10, 9)
    assert ndvi.call_args.args[3] == datetime(2026, 10, 10)
    assert r['metadata']['data_analise'] == '2026-10-26'
    assert r['metadata']['contexto'] == 'historico_ate_colheita'
    assert r['fase']['dias_apos_plantio'] == 101
    assert r['fase']['data_referencia'] == '2026-10-10'
    assert r['colheita']['status'] == 'REGISTRADA'
    assert r['colheita']['estimada'] is False
    assert r['scores']['valor'] is None


def test_estimativa_de_colheita_nao_depende_das_apis(monkeypatch):
    monkeypatch.setattr('safrasmart.analisar.buscar_dados_meteo', lambda *a, **kw: None)
    r = analisar(-12, -55, 'milho', datetime(2026, 8, 1), 'misto', 'sequeiro', usar_ndvi=False,
                 colheita_realizada=False, hoje=date(2026, 10, 26))
    assert r['colheita']['status'] == 'AGUARDAR'
    assert r['colheita']['janela']['inicio'] == '2026-11-14'
    assert r['colheita']['janela']['fim'] == '2026-12-18'
    assert r['scores']['valor'] is None
    assert r['indices'] == {}
    assert r['ndvi'] is None
    assert r['confiabilidade']['modelo_validado'] is False


def test_worker_encaminha_campos_de_colheita(monkeypatch):
    from safrasmart import worker
    analisar_mock = Mock(return_value={'colheita': {'status': 'REGISTRADA'}})
    monkeypatch.setattr('safrasmart.analisar.analisar', analisar_mock)
    monkeypatch.setattr(worker, 'criar_engine', lambda _: Mock())
    monkeypatch.setattr(worker, 'CacheAnalitico', lambda _: None)
    monkeypatch.setattr(worker, 'Repositorio', lambda _: None)
    canal = Mock()
    worker._filho(canal, 'sqlite://', {'lat': 0, 'lon': 0, 'cultura': 'soja', 'data_plantio': '2026-01-01',
                 'solo': 'misto', 'irrigacao': 'sequeiro', 'prod_ant': None, 'observacoes': '',
                 'data_colheita': '2026-05-01', 'colheita_realizada': True})
    assert analisar_mock.call_args.kwargs['data_colheita'] == '2026-05-01'
    assert analisar_mock.call_args.kwargs['colheita_realizada'] is True
    canal.send.assert_called_once_with({'resultado': {'colheita': {'status': 'REGISTRADA'}}})
