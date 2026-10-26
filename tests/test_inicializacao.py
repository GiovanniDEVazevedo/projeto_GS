import json
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import inspect

from safrasmart import bootstrap, cli
from safrasmart.db import criar_engine


@pytest.fixture
def projeto(tmp_path, monkeypatch):
    raiz = tmp_path / 'projeto com espacos'
    raiz.mkdir()
    (raiz / '.env.example').write_text('START_WORKER=true\nENABLE_NDVI=false\nPORT=5000\n', encoding='utf-8')
    (raiz / 'requirements.txt').write_text('Flask==3.1.3\n', encoding='utf-8')
    (raiz / 'requirements-ndvi.txt').write_text('-r requirements.txt\nearthengine-api==1.7.28\n', encoding='utf-8')
    monkeypatch.setattr(bootstrap, 'ROOT', raiz)
    for campo, valor in {'START_WORKER': 'true', 'ENABLE_NDVI': 'false', 'PORT': '5000',
                         'GEE_SERVICE_ACCOUNT_JSON': '', 'GEE_KEY_PATH': '', 'GEE_PROJECT': '',
                         'MIN_NDVI_COVERAGE': '.5', 'DATABASE_URL': f'sqlite:///{raiz / "teste.db"}'}.items():
        monkeypatch.setenv(campo, valor)
    return raiz


def python_fake(raiz):
    import os
    caminho = raiz / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.touch()
    return caminho


def test_env_criado_sem_substituir_credenciais(projeto, capsys):
    destino = bootstrap.preparar_env()
    assert destino.read_text() == (projeto / '.env.example').read_text()
    destino.write_text('GEE_SERVICE_ACCOUNT_JSON=SEGREDO_QUE_NAO_PODE_SUMIR', encoding='utf-8')
    bootstrap.preparar_env()
    assert 'SEGREDO_QUE_NAO_PODE_SUMIR' in destino.read_text()
    assert 'SEGREDO_QUE_NAO_PODE_SUMIR' not in capsys.readouterr().out


def test_template_ausente_nao_cria_env_vazio(projeto):
    (projeto / '.env.example').unlink()
    with pytest.raises(FileNotFoundError):
        bootstrap.preparar_env()
    assert not (projeto / '.env').exists()


def test_dependencias_sao_reutilizadas_e_reinstaladas_quando_mudam(projeto, monkeypatch):
    python = python_fake(projeto)
    run = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(bootstrap.subprocess, 'run', run)
    assert bootstrap.preparar_ambiente() == python
    assert 'pip' in run.call_args.args[0]
    run.reset_mock()
    assert bootstrap.preparar_ambiente() == python
    assert run.call_count == 1
    assert run.call_args.args[0][1] == '-c'  # verifica imports, não reinstala
    (projeto / 'requirements.txt').write_text('Flask==3.1.3\nrequests==2.34.2\n')
    run.reset_mock()
    bootstrap.preparar_ambiente()
    assert 'pip' in run.call_args.args[0]


def test_instalacao_falha_nao_marca_ambiente_como_pronto(projeto, monkeypatch):
    python_fake(projeto)
    monkeypatch.setattr(bootstrap.subprocess, 'run', Mock(side_effect=subprocess.CalledProcessError(1, ['pip'])))
    with pytest.raises(subprocess.CalledProcessError):
        bootstrap.preparar_ambiente()
    assert not (projeto / '.venv' / '.safrasmart-dependencias').exists()


def test_bootstrap_propaga_flags_e_codigo_de_saida(projeto, monkeypatch):
    python = python_fake(projeto)
    monkeypatch.setattr(bootstrap, 'preparar_ambiente', lambda: python)
    run = Mock(return_value=SimpleNamespace(returncode=7))
    monkeypatch.setattr(bootstrap.subprocess, 'run', run)
    assert bootstrap.main(['--preparar']) == 7
    assert run.call_args.args[0] == [str(python), '-m', 'safrasmart', '--preparar']
    assert run.call_args.kwargs['cwd'] == projeto
    assert run.call_args.kwargs['env']['VIRTUAL_ENV'] == str(projeto / '.venv')


def test_configuracao_e_migracoes_antes_do_servidor(projeto, monkeypatch):
    ordem = []
    monkeypatch.setattr('safrasmart.db.migrar', lambda: ordem.append('migrar'))
    monkeypatch.setattr('safrasmart.api.server.iniciar_servidor', lambda: ordem.append('servidor'))
    assert cli.main([]) == 0
    assert ordem == ['migrar', 'servidor']


def test_preparar_aplica_migracoes_reais_sem_iniciar_http(projeto, monkeypatch):
    servidor = Mock()
    monkeypatch.setattr('safrasmart.api.server.iniciar_servidor', servidor)
    assert cli.main(['--preparar']) == 0
    engine = criar_engine(f'sqlite:///{projeto / "teste.db"}')
    try:
        assert {'analises', 'safras', 'propriedades', 'cache_dados', 'alembic_version'} <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    servidor.assert_not_called()
    assert cli.main(['--preparar']) == 0  # migração repetida é idempotente


def test_json_invalido_falha_antes_de_migrar_e_sem_expor_segredo(projeto, monkeypatch, capsys):
    monkeypatch.setenv('ENABLE_NDVI', 'true')
    monkeypatch.setenv('GEE_SERVICE_ACCOUNT_JSON', 'SEGREDO_NAO_EXIBIR')
    migrar = Mock()
    monkeypatch.setattr('safrasmart.db.migrar', migrar)
    assert cli.main(['--preparar']) == 1
    migrar.assert_not_called()
    saida = capsys.readouterr()
    assert 'JSON completo' in saida.err
    assert 'SEGREDO_NAO_EXIBIR' not in saida.err + saida.out


def test_json_no_env_usa_projeto_do_proprio_documento(projeto, monkeypatch):
    monkeypatch.setenv('ENABLE_NDVI', 'true')
    monkeypatch.setenv('GEE_SERVICE_ACCOUNT_JSON', json.dumps({'type': 'service_account', 'project_id': 'exemplo',
        'client_email': 'exemplo@exemplo.iam.gserviceaccount.com', 'private_key': 'EXEMPLO SEM VALIDADE',
        'token_uri': 'https://oauth2.googleapis.com/token'}))
    # Valida estrutura local; não faz autenticação ou consulta à API externa.
    cli.validar_configuracao()


def test_erro_banco_nao_abre_servidor_nem_expoe_url(projeto, monkeypatch, capsys):
    monkeypatch.setattr('safrasmart.db.migrar', Mock(side_effect=ValueError('postgresql://usuario:SENHA_NAO_EXIBIR@host/banco')))
    servidor = Mock()
    monkeypatch.setattr('safrasmart.api.server.iniciar_servidor', servidor)
    assert cli.main([]) == 1
    servidor.assert_not_called()
    saida = capsys.readouterr()
    assert 'SENHA_NAO_EXIBIR' not in saida.out + saida.err


@pytest.mark.parametrize('campo,valor', [('PORT', 'senha_nao_exibir'), ('PORT', '0'), ('PORT', '65536'),
                                         ('START_WORKER', 'errado'), ('ENABLE_NDVI', 'errado'),
                                         ('MIN_NDVI_COVERAGE', 'nan'), ('MIN_NDVI_COVERAGE', '2')])
def test_opcoes_invalidas_recebem_erro_controlado(projeto, monkeypatch, campo, valor):
    monkeypatch.setenv('ENABLE_NDVI', 'true')
    monkeypatch.setenv(campo, valor)
    with pytest.raises(cli.ConfiguracaoInvalida):
        cli.validar_configuracao()
