# Oracle Database — configuração e validação

O backend tem suporte de código ao Oracle Database usando SQLAlchemy 2.0 e python-oracledb em Thin mode. O alvo é Oracle 19c ou superior, incluindo XE 21c e Free. A validação disponível nesta entrega cobre tipos, serialização e SQL gerado; conexão e concorrência em uma instância Oracle real ainda precisam ser verificadas.

## 1. Preparar usuário e serviço

Use um usuário/schema exclusivo para o SafraSmart, com acesso ao serviço do banco. Para aplicar as migrações, o administrador deve conceder `CREATE SESSION`, `CREATE TABLE` e quota no tablespace apropriado. O dono das tabelas pode criar índices e constraints nelas. Não use `SYS` ou `SYSTEM` na aplicação.

Tenha estes dados, disponíveis também na conexão do SQL Developer:

| Dado | Exemplo ilustrativo |
| --- | --- |
| Usuário/schema | `safrasmart` |
| Host | `localhost` ou o servidor informado pela instituição |
| Porta | `1521` |
| Nome do serviço | `FREEPDB1`, `XEPDB1` ou o serviço fornecido |

O nome do serviço não é o nome da aplicação. Não assuma que o servidor da FIAP usa `FREEPDB1`; use os dados recebidos. Se sua conexão usar SID, veja a alternativa de URL abaixo.

## 2. Instalar e configurar

Na raiz do projeto, com o ambiente virtual ativo:

```bash
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha os três campos, removendo `#`:

```dotenv
ORACLE_USER=safrasmart
ORACLE_PASSWORD='sua_senha_real'
ORACLE_DSN=localhost:1521/FREEPDB1
```

Nessa forma, a aplicação monta a URL sem exigir codificação de `@`, `/`, `%` e `#` na senha. Não deixe `DATABASE_URL` definida para outro banco: ela tem prioridade. Os três campos precisam estar preenchidos juntos; configuração parcial gera erro, em vez de trocar silenciosamente para SQLite.

Para manter somente a URL, outra opção é:

```dotenv
DATABASE_URL=oracle+oracledb://usuario:senha@servidor:1521?service_name=ORCL
```

Codifique caracteres especiais da senha na URL. Se o administrador informar **SID**, a sintaxe SQLAlchemy é `oracle+oracledb://usuario:senha@servidor:1521/SID`. Nessa sintaxe, o trecho depois de `/` representa SID; para **service name**, use `?service_name=...` ou os três campos separados.

Thin mode conecta sem instalar Oracle Instant Client. A aplicação configura timeout de estabelecimento TCP de 10 segundos e não pede retries adicionais ao driver. Isso não representa limite total de uma consulta ou do pool. O pool usa verificação de conexão e reciclagem após 30 minutos.

## 3. Criar as tabelas

Antes de iniciar os processos:

```bash
python -m safrasmart.db upgrade
```

O comando aplica Alembic e registra a revisão `0002`. Usa o schema do usuário da conexão, sem criar outro usuário nem apagar tabelas de negócio. Execute com um único processo de migração, sem API/worker concorrendo com a atualização.

Para revisar o SQL antes de conectar:

```bash
python -m safrasmart.db upgrade --sql
```

O modo `--sql` gera SQL para o banco configurado; não abre conexão e não modifica tabelas. Para gerar SQL Oracle, configure uma URL Oracle ou os três campos acima antes do comando. Prefira aplicar pelo Alembic; o SQL de revisão usa delimitadores próprios do dialect Oracle.

## 4. Iniciar API e worker

Execute em dois terminais, com o mesmo ambiente e `.env`:

```bash
python -m safrasmart.api.server
```

```bash
python -m safrasmart.worker
```

Abra `http://localhost:5000`. `GET /api/health` deve responder `{"status":"ok"}` após conectar e consultar a tabela de análises. Crie um registro: ele deve sair de salvo no dispositivo para fila do servidor e depois mostrar o resultado. Confirme o histórico após reiniciar ambos os processos. Em produção, use Gunicorn, supervisão do worker e HTTPS.

## 5. Oracle Cloud / Autonomous com wallet

Extraia o wallet em um diretório seguro **fora do repositório**. Configure o alias existente em `tnsnames.ora`:

```dotenv
ORACLE_USER=safrasmart
ORACLE_PASSWORD='senha_do_usuario'
ORACLE_DSN=alias_real_high
ORACLE_CONFIG_DIR=/caminho/seguro/wallet
ORACLE_WALLET_LOCATION=/caminho/seguro/wallet
ORACLE_WALLET_PASSWORD='senha_do_wallet'
```

A senha do wallet e a do usuário podem ser diferentes. Thin mode usa o material PEM do wallet; confira que o pacote fornecido pelo serviço contém os arquivos necessários, incluindo `tnsnames.ora` e `ewallet.pem`. Permissões de rede, allowlists e configuração TLS continuam dependendo do serviço Oracle. Não desative a verificação TLS para contornar falhas.

Se o serviço oferecer TLS sem wallet, use a string TCPS indicada pelo provedor em `ORACLE_DSN`; não preencha as variáveis de wallet nesse caso.

## 6. Como os dados são armazenados

| Tabela | Conteúdo |
| --- | --- |
| `propriedades` | Identificação, localização e vínculo com a credencial do dispositivo |
| `safras` | Cultura, data de plantio, solo e irrigação |
| `analises` | Entrada JSON, resultado JSON, status, idempotência e controle do worker |
| `cache_dados` | Documentos climáticos/NDVI com expiração |
| `alembic_version` | Revisão aplicada do schema |

Campos JSON usam CLOB + constraints `IS JSON` no Oracle. Isso permite documentos maiores que o limite de VARCHAR2 sem exigir o tipo JSON nativo do Oracle 21c. O adaptador preserva acentos, valores ausentes e números; também aceita o retorno já decodificado do driver. Não foram adicionadas consultas SQL por chave JSON.

Timestamps usam `TIMESTAMP` e UTC sem fuso no armazenamento. O UUID de cada operação e sua assinatura continuam impedindo duplicação ou reuso do mesmo identificador com dados diferentes. O worker passa a sua URL efetiva ao subprocesso analítico, inclusive ao cache, em vez de abrir outro banco por engano.

SQLite continua disponível para desenvolvimento sem servidor. PostgreSQL permanece opcional com `pip install -r requirements-postgres.txt`. As migrações preservam o formato existente desses dois bancos.

**Trocar a conexão não copia dados entre bancos.** Esta entrega prepara um schema Oracle novo e mantém o banco anterior intacto. Se já houver histórico real em SQLite/PostgreSQL, planeje uma transferência separada, com backup, contagem de registros e conferência de resultados antes de trocar a produção. O histórico do navegador também é vinculado ao domínio e à credencial do dispositivo.

## 7. Testes

```bash
pip install -r requirements-dev.txt
python -m pytest -q
npm test
```

`tests/test_oracle.py` verifica configuração, senha com caracteres especiais, geração de schema/migrações Oracle, serialização CLOB e preservação no upgrade local. Esses testes não representam integração com servidor Oracle.

Para executar os testes de banco existentes em uma instância real, use um **schema exclusivo descartável** e uma URL Oracle de teste. A fixture apaga e recria as tabelas do SafraSmart e `alembic_version` em cada teste. Nunca use o schema de produção.

Linux/macOS:

```bash
export TEST_DATABASE_URL='oracle+oracledb://usuario_teste:senha@servidor:1521?service_name=ORCL'
export TEST_ALLOW_DATABASE_RESET=1
python -m pytest tests/test_api.py tests/test_cache.py tests/test_worker_recuperacao.py -q
```

PowerShell:

```powershell
$env:TEST_DATABASE_URL='oracle+oracledb://usuario_teste:senha@servidor:1521?service_name=ORCL'
$env:TEST_ALLOW_DATABASE_RESET='1'
python -m pytest tests/test_api.py tests/test_cache.py tests/test_worker_recuperacao.py -q
```

A autorização explícita de reset protege contra remoção acidental em bancos externos. Os testes bloqueiam APIs climáticas e usam resultados analíticos controlados: a integração meteorológica e Earth Engine deve ser validada à parte.

## Referências técnicas

- SQLAlchemy 2.0, dialect Oracle e conexão por service name/DSN: https://docs.sqlalchemy.org/en/20/dialects/oracle.html
- python-oracledb, conexão e Thin mode: https://python-oracledb.readthedocs.io/en/stable/user_guide/connection_handling.html
- python-oracledb, JSON em CLOB e retorno do driver: https://python-oracledb.readthedocs.io/en/stable/user_guide/json_data_type.html
