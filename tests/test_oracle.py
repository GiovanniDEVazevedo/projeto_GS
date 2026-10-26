"""Compatibilidade Oracle sem simular uma conexão como se fosse integração real."""
import io
import json
import pickle
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import oracle, postgresql, sqlite
from sqlalchemy.engine import URL
from sqlalchemy.schema import CreateIndex, CreateTable

from safrasmart.config import database_url, oracle_connect_args
from safrasmart.db import Analise, Base, criar_engine, migrar
from safrasmart.tipos_db import DocumentoJSON
from safrasmart.worker import processar_um


@pytest.fixture
def sem_config_banco(monkeypatch):
    for campo in ('DATABASE_URL', 'ORACLE_USER', 'ORACLE_PASSWORD', 'ORACLE_DSN',
                  'ORACLE_CONFIG_DIR', 'ORACLE_WALLET_LOCATION', 'ORACLE_WALLET_PASSWORD'):
        monkeypatch.delenv(campo, raising=False)


def test_conexao_por_campos_preserva_senha_especial(sem_config_banco, monkeypatch):
    senha = 'senha@/%# :ç'
    monkeypatch.setenv('ORACLE_USER', 'safrasmart')
    monkeypatch.setenv('ORACLE_PASSWORD', senha)
    monkeypatch.setenv('ORACLE_DSN', 'servidor:1521/FREEPDB1')
    url = database_url()
    assert url.drivername == 'oracle+oracledb'
    assert url.password == senha
    # Gerar argumentos não abre conexão; valida o contrato com o driver real.
    engine = criar_engine(url)
    args, kwargs = engine.dialect.create_connect_args(engine.url)
    assert args == []
    assert kwargs == {'user': 'safrasmart', 'password': senha, 'dsn': 'servidor:1521/FREEPDB1'}
    assert senha not in str(url)
    assert engine.hide_parameters
    assert pickle.loads(pickle.dumps(url)) == url  # subprocesso do worker
    engine.dispose()


def test_url_tem_precedencia_e_normaliza_driver(sem_config_banco, monkeypatch):
    monkeypatch.setenv('ORACLE_DSN', 'outro_servico')
    monkeypatch.setenv('DATABASE_URL', 'oracle://conta:senha@servidor:1521?service_name=ORCL')
    url = database_url()
    assert url.drivername == 'oracle+oracledb'
    engine = criar_engine(url)
    _, kwargs = engine.dialect.create_connect_args(url)
    assert 'SERVICE_NAME=ORCL' in kwargs['dsn']
    assert 'HOST=servidor' in kwargs['dsn']
    engine.dispose()


@pytest.mark.parametrize('campo', ['ORACLE_USER', 'ORACLE_PASSWORD', 'ORACLE_DSN'])
def test_oracle_incompleto_nao_cai_silenciosamente_em_sqlite(sem_config_banco, monkeypatch, campo):
    monkeypatch.setenv(campo, 'configurado')
    with pytest.raises(ValueError, match='Configure ORACLE_USER'):
        database_url()


def test_url_explicita_isola_testes_do_ambiente_oracle(sem_config_banco, monkeypatch):
    monkeypatch.setenv('ORACLE_USER', 'incompleto')
    assert database_url('sqlite:///:memory:').get_backend_name() == 'sqlite'


def test_sem_configuracao_mantem_banco_local(sem_config_banco):
    assert database_url().get_backend_name() == 'sqlite'


def test_wallet_fora_da_url(sem_config_banco, monkeypatch):
    monkeypatch.setenv('ORACLE_CONFIG_DIR', '/seguro/wallet')
    monkeypatch.setenv('ORACLE_WALLET_LOCATION', '/seguro/wallet')
    monkeypatch.setenv('ORACLE_WALLET_PASSWORD', 'senha-wallet')
    args = oracle_connect_args()
    assert args['config_dir'] == '/seguro/wallet'
    assert args['wallet_location'] == '/seguro/wallet'
    assert args['wallet_password'] == 'senha-wallet'
    assert args['tcp_connect_timeout'] == 10
    assert args['retry_count'] == 0


@pytest.mark.parametrize('dialect', [oracle.dialect(), sqlite.dialect(), postgresql.dialect()], ids=['oracle', 'sqlite', 'postgresql'])
def test_schema_compila_nos_tres_bancos(dialect):
    tabelas = {table.name: str(CreateTable(table).compile(dialect=dialect)) for table in Base.metadata.sorted_tables}
    for table in Base.metadata.sorted_tables:
        for index in table.indexes:
            assert str(CreateIndex(index).compile(dialect=dialect))
    if dialect.name == 'oracle':
        assert 'entrada CLOB NOT NULL' in tabelas['analises']
        assert 'resultado CLOB' in tabelas['analises']
        assert 'entrada IS JSON' in tabelas['analises']
        assert 'resultado IS JSON' in tabelas['analises']
        assert 'conteudo IS JSON' in tabelas['cache_dados']
        assert 'lease_ate TIMESTAMP' in tabelas['analises']
    else:
        assert 'entrada JSON NOT NULL' in tabelas['analises']
        assert 'IS JSON' not in tabelas['analises']


def test_migracoes_geram_sql_oracle_sem_conectar():
    saida = io.StringIO()
    migrar('oracle+oracledb://', sql=True, output_buffer=saida)
    sql = saida.getvalue()
    assert 'CREATE TABLE propriedades' in sql
    assert 'entrada CLOB NOT NULL' in sql
    assert 'MODIFY lease_ate TIMESTAMP' in sql
    assert 'CHECK (entrada IS JSON)' in sql
    assert 'CHECK (resultado IS JSON)' in sql
    assert 'CHECK (conteudo IS JSON)' in sql
    assert "'0002'" in sql


@pytest.mark.parametrize('documento', [None, {}, {'observacoes': 'solo úmido 🌱', 'faltantes': [None, True, 0, -23.551]}, {'texto': 'a' * 100000}])
def test_documento_oracle_ciclo_json_sem_truncamento(documento):
    tipo = DocumentoJSON()
    dialect = oracle.dialect()
    armazenado = tipo.process_bind_param(documento, dialect)
    assert tipo.process_result_value(armazenado, dialect) == documento


def test_documento_oracle_lob_bytes_e_objetos_do_driver():
    tipo = DocumentoJSON()
    dialect = oracle.dialect()
    assert tipo.process_result_value(io.StringIO('{"valor": null}'), dialect) == {'valor': None}
    assert tipo.process_result_value(b'{"valor": 2}', dialect) == {'valor': 2}
    nativo = {'numero': Decimal('1.25'), 'dias': [Decimal('30'), None], 'ok': True}
    resultado = tipo.process_result_value(nativo, dialect)
    assert resultado == {'numero': 1.25, 'dias': [30, None], 'ok': True}
    assert json.dumps(resultado)


def test_documento_oracle_recusa_nan():
    with pytest.raises(ValueError):
        DocumentoJSON().process_bind_param({'valor': float('nan')}, oracle.dialect())


def test_worker_reutiliza_url_real_da_fila(app, payload, monkeypatch):
    from safrasmart.validacao import validar
    repo = app.extensions['repo']
    repo.registrar('owner', validar(payload))
    conexoes = []
    def executar(dados, url):
        conexoes.append(url)
        return {'resultado': 'fixture'}
    monkeypatch.setattr('safrasmart.worker.executar_isolado', executar)
    assert processar_um(repo)
    assert conexoes == [repo.engine.url]


def test_upgrades_existentes_preservam_dados(tmp_path):
    from safrasmart.repositorio import Repositorio
    from safrasmart.validacao import validar
    from uuid import uuid4
    url = URL.create('sqlite', database=str(tmp_path / 'upgrade.db'))
    migrar(url, revision='0001')
    repo = Repositorio(criar_engine(url))
    dados = validar({'id': str(uuid4()), 'lat': -23.55, 'lon': -46.63,
                    'cultura': 'milho', 'data_plantio': '2026-10-01', 'solo': 'argiloso',
                    'irrigacao': 'sequeiro', 'observacoes': 'solo úmido'})
    repo.registrar('owner', dados)
    migrar(url)
    migrar(url)  # repetir upgrade não perde dados
    assert repo.obter('owner', dados['id'])['persistido'] is True
    with repo.session() as session:
        assert session.scalar(select(Analise)).entrada == dados
    repo.engine.dispose()
