import io
import json
import sys
from datetime import date, datetime
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest
from dotenv import dotenv_values

from safrasmart.credenciais_gee import carregar_dados_gee, gee_configurado
from safrasmart.ndvi import autenticar_gee


@pytest.fixture
def credencial(monkeypatch):
    for chave in ('GEE_SERVICE_ACCOUNT_JSON', 'GEE_KEY_PATH', 'GEE_PROJECT'):
        monkeypatch.delenv(chave, raising=False)
    return {'type': 'service_account', 'project_id': 'projeto-exemplo',
            'client_email': 'teste@projeto-exemplo.iam.gserviceaccount.com',
            'private_key': '-----BEGIN PRIVATE KEY-----\nEXEMPLO_SEM_VALIDADE\n-----END PRIVATE KEY-----\n',
            'token_uri': 'https://oauth2.googleapis.com/token'}


def test_colar_json_multilinha_preserva_escape_de_chave(credencial, monkeypatch):
    conteudo = "GEE_SERVICE_ACCOUNT_JSON='" + json.dumps(credencial, indent=2) + "'\nGEE_PROJECT=\n"
    valores = dotenv_values(stream=io.StringIO(conteudo))
    for k, v in valores.items():
        monkeypatch.setenv(k, v)
    assert gee_configurado()
    assert carregar_dados_gee() == credencial
    assert '\nEXEMPLO_SEM_VALIDADE\n' in carregar_dados_gee()['private_key']


def test_arquivo_relativo_a_raiz_e_utf8_bom(credencial, monkeypatch, tmp_path):
    (tmp_path / 'conta.json').write_text(json.dumps(credencial), encoding='utf-8-sig')
    monkeypatch.setattr('safrasmart.credenciais_gee.ROOT', tmp_path)
    monkeypatch.setenv('GEE_KEY_PATH', 'conta.json')
    assert gee_configurado()
    assert carregar_dados_gee() == credencial


def test_json_no_ambiente_tem_prioridade(credencial, monkeypatch):
    monkeypatch.setenv('GEE_SERVICE_ACCOUNT_JSON', json.dumps(credencial))
    monkeypatch.setenv('GEE_KEY_PATH', '/arquivo/inexistente.json')
    assert carregar_dados_gee() == credencial


def test_caminho_explicito_preserva_contrato_anterior(credencial, monkeypatch, tmp_path):
    caminho = tmp_path / 'conta.json'
    caminho.write_text(json.dumps(credencial), encoding='utf-8')
    monkeypatch.setenv('GEE_SERVICE_ACCOUNT_JSON', 'invalido')
    assert carregar_dados_gee(caminho) == credencial


@pytest.mark.parametrize('valor', ['', '   '])
def test_configuracao_vazia(credencial, monkeypatch, valor):
    monkeypatch.setenv('GEE_SERVICE_ACCOUNT_JSON', valor)
    monkeypatch.setenv('GEE_KEY_PATH', valor)
    assert not gee_configurado()
    with pytest.raises(RuntimeError, match='Configure GEE_SERVICE_ACCOUNT_JSON'):
        carregar_dados_gee()


@pytest.mark.parametrize('valor', ['SEGREDO_NAO_EXIBIR', '{"private_key": "SEGREDO_NAO_EXIBIR"', '[]', '{"type":"api_key"}'])
def test_erro_nao_expoe_credencial(credencial, monkeypatch, valor):
    monkeypatch.setenv('GEE_SERVICE_ACCOUNT_JSON', valor)
    with pytest.raises(RuntimeError) as error:
        carregar_dados_gee()
    assert 'SEGREDO_NAO_EXIBIR' not in str(error.value)


@pytest.mark.parametrize('campo', ['client_email', 'private_key', 'token_uri'])
def test_json_incompleto_informa_campo(credencial, monkeypatch, campo):
    del credencial[campo]
    monkeypatch.setenv('GEE_SERVICE_ACCOUNT_JSON', json.dumps(credencial))
    with pytest.raises(RuntimeError, match=campo):
        carregar_dados_gee()


def test_caminho_inexistente_tem_erro_controlado(credencial, monkeypatch):
    monkeypatch.setenv('GEE_KEY_PATH', '/inexistente/SEGREDO_NAO_EXIBIR.json')
    with pytest.raises(RuntimeError) as error:
        carregar_dados_gee()
    assert 'SEGREDO_NAO_EXIBIR' not in str(error.value)


@pytest.mark.parametrize('override,esperado', [('', 'projeto-exemplo'), ('outro-projeto', 'outro-projeto')])
def test_inicializacao_usa_json_e_projeto(credencial, monkeypatch, override, esperado):
    monkeypatch.setenv('GEE_SERVICE_ACCOUNT_JSON', json.dumps(credencial))
    monkeypatch.setenv('GEE_PROJECT', override)
    credentials = SimpleNamespace(from_service_account_info=Mock(return_value='credencial-fixture'))
    google = ModuleType('google')
    google.__path__ = []
    oauth = ModuleType('google.oauth2')
    oauth.__path__ = []
    oauth.service_account = SimpleNamespace(Credentials=credentials)
    google.oauth2 = oauth
    ee = SimpleNamespace(Initialize=Mock(), data=SimpleNamespace(setDeadline=Mock(), setMaxRetries=Mock()))
    monkeypatch.setitem(sys.modules, 'google', google)
    monkeypatch.setitem(sys.modules, 'google.oauth2', oauth)
    monkeypatch.setitem(sys.modules, 'ee', ee)
    autenticar_gee()
    credentials.from_service_account_info.assert_called_once_with(credencial, scopes=['https://www.googleapis.com/auth/earthengine'])
    ee.Initialize.assert_called_once_with('credencial-fixture', project=esperado)


def test_projeto_ausente_tem_erro_claro(credencial, monkeypatch):
    del credencial['project_id']
    monkeypatch.setenv('GEE_SERVICE_ACCOUNT_JSON', json.dumps(credencial))
    with pytest.raises(RuntimeError, match='Defina GEE_PROJECT'):
        autenticar_gee()


def test_pipeline_aceita_json_sem_caminho(credencial, monkeypatch):
    from safrasmart.analisar import analisar
    monkeypatch.setenv('GEE_SERVICE_ACCOUNT_JSON', json.dumps(credencial))
    monkeypatch.setattr('safrasmart.analisar.buscar_dados_meteo', lambda *a, **k: None)
    consultar = Mock(return_value={'ndvi': [.5], 'ndvi_medio_geral': .5, 'ndvi_max': .5, 'datas': ['2026-10-10']})
    monkeypatch.setattr('safrasmart.ndvi.buscar_ndvi', consultar)
    resultado = analisar(-23, -46, 'soja', datetime(2026, 10, 1), 'misto', 'sequeiro', hoje=date(2026, 10, 26))
    consultar.assert_called_once()
    assert resultado['ndvi']['ndvi_media'] == .5
