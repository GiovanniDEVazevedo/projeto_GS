# SafraSmart

Aplicação Python/Flask de apoio à decisão agrícola para soja e milho, com PWA offline-first, histórico persistente e processamento em segundo plano. Os indicadores são experimentais: não representam probabilidade de sucesso, diagnóstico de doença ou recomendação validada de plantio.

## Executar localmente

Requer Python 3.10+; Node.js é usado somente nos testes JavaScript.

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
# Windows PowerShell: Copy-Item .env.example .env
python -m safrasmart.db upgrade
python -m safrasmart.api.server
```

Em outro terminal, ative o mesmo ambiente e execute:

```bash
python -m safrasmart.worker
```

Abra http://localhost:5000. Sem configurar `DATABASE_URL`, usa SQLite em `instance/safrasmart.db`. A API recebe/persiste solicitações; o worker precisa estar ativo para gerar resultados. O menu de terminal continua disponível com `python menu.py`; análises diretas pelo terminal não entram no histórico web.

## Conectar PostgreSQL

Crie um banco vazio no provedor escolhido. No `.env`, configure a conexão fornecida por ele:

```dotenv
DATABASE_URL=postgresql+psycopg://usuario:senha@host:5432/safrasmart?sslmode=require
```

Use os dados reais do provedor; codifique caracteres especiais da senha na URL. URLs iniciadas por `postgres://` e `postgresql://` também são aceitas pela configuração de ambiente. Não publique `.env` nem chaves de serviço.

Aplique as migrações antes de iniciar API e worker:

```bash
python -m safrasmart.db upgrade
```

API e worker precisam compartilhar a mesma `DATABASE_URL`. A migração cria propriedades, safras, análises e cache, com índices, chaves estrangeiras e restrições de idempotência. Trocar a URL não transfere os dados de um SQLite existente para PostgreSQL; faça uma migração dos dados separadamente se precisar conservar esse histórico.

Em Linux, para servir a API em produção:

```bash
gunicorn --bind 0.0.0.0:5000 --workers 2 safrasmart.api.server:app
```

Execute o worker como processo separado e configure HTTPS no serviço de hospedagem/proxy. A API não executa migrações automaticamente. `GET /api/health` verifica conexão e tabelas. Nenhuma credencial de banco real está incluída.

## Funcionamento offline

Abra a aplicação uma vez com internet em HTTPS ou localhost e aguarde o service worker instalar. Cadastros são gravados primeiro no IndexedDB, com UUID; apenas confirmações individuais de persistência encerram o reenvio. Falhas parciais, servidor inacessível e resposta perdida preservam o registro. Resultados recebidos ficam disponíveis no dispositivo.

Novas consultas climáticas e de satélite precisam de internet no servidor. Ao reconectar, a fila é sincronizada automaticamente, com limite de 50 operações por lote e novas tentativas progressivas. Registros inválidos/conflitantes permanecem visíveis para revisão. O botão de exportação permite copiar os registros em JSON.

O histórico do servidor é isolado por uma credencial aleatória por dispositivo armazenada no IndexedDB. Isso não é um sistema de contas: não há login, recuperação de credencial nem acesso automático entre aparelhos. Limpar os dados do navegador perde essa credencial e a cópia offline; mantenha backups. Para serviço público com vários clientes, ainda é necessário implementar contas e controles operacionais contra abuso.

## NDVI opcional

```bash
pip install -r requirements-ndvi.txt
```

Configure `GEE_KEY_PATH` e `GEE_PROJECT` no `.env`, com acesso ao Earth Engine habilitado na conta de serviço. Ou use `ENABLE_NDVI=false`. Sem credenciais, o relatório informa indisponibilidade e continua com os demais dados.

O cálculo usa Sentinel-2 SR, máscara por pixel SCL, cobertura mínima configurável e amostra em raio de 50 metros. Não representa a propriedade inteira nem diagnostica a causa de baixo vigor. O trabalho é isolado em processo para permitir encerramento efetivo por timeout.

## Correções e confiabilidade

- Valores climáticos ausentes permanecem ausentes; indicadores mostram cobertura e período.
- Chuva é comparada em períodos equivalentes, com janela da fase estimada; não há comparação de acumulado anual com faixa mensal.
- Texto usa limites de palavras, variações explícitas, negação, suspeita e temporalidade. Relatos não são diagnósticos e sentimento não determina risco.
- Solo encharcado gera atenção a excesso hídrico. Estados visuais usam códigos exatos.
- Percentuais de sucesso foram removidos; referências de solo/produtividade sem sustentação não geram notas.
- Cache persistente reduz consultas repetidas. Processamento tem lease, recuperação após interrupção e até três tentativas; workers atrasados não sobrescrevem resultados novos.
- Entradas são validadas; resultados são renderizados com `textContent`; API não entra no cache do service worker.

As faixas agronômicas ainda precisam de calibração com especialistas. Planejamento de plantio requer referências regionais como o ZARC. Não foram implementados polígonos/PostGIS, diagnóstico automático, previsão de produtividade ou sincronização entre contas.

## Testes

```bash
pip install -r requirements-dev.txt
python -m pytest -q
npm test
```

A suíte Python usa banco SQLite temporário e bloqueia chamadas meteorológicas externas. Cobre persistência, migrações, concorrência, isolamento entre dispositivos, validação, worker, lacunas climáticas e interpretação de observações. Os testes JavaScript verificam a fila diante de falhas parciais, respostas perdidas e reenvios.

Para testar com PostgreSQL, use `TEST_DATABASE_URL` **exclusivamente em um banco descartável**: a fixture remove e recria tabelas. Não aponte para produção.
