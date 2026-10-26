# SafraSmart

Aplicação Python/Flask de apoio à decisão agrícola para soja e milho, com PWA offline-first, histórico persistente e processamento em segundo plano. Os indicadores são experimentais: não representam probabilidade de sucesso, diagnóstico de doença ou recomendação validada de plantio.

## Rodar com um comando

Requer Python 3.10+ instalado. Na raiz do projeto, execute:

```bash
python iniciar.py
```

O comando cria `.venv`, instala as dependências (inclusive Earth Engine), cria `.env` se ele ainda não existir, valida a configuração, aplica as migrações e inicia servidor + worker no mesmo terminal. Não precisa ativar o ambiente virtual nem executar `pip`, migrações e worker separadamente. Nas próximas execuções, reaproveita o ambiente; reinstala quando os arquivos de dependências mudam ou faltam módulos.

Abra http://localhost:5000. Use `Ctrl+C` para encerrar. A primeira execução precisa de internet para instalar pacotes. Seu `.env` existente nunca é substituído.

## Colar o JSON do Earth Engine

No `.env`, cole o conteúdo **inteiro** do JSON baixado da conta de serviço entre as aspas simples:

```dotenv
START_WORKER=true
ENABLE_NDVI=true
GEE_SERVICE_ACCOUNT_JSON='COLE_AQUI_O_JSON_COMPLETO'
GEE_PROJECT=
MIN_NDVI_COVERAGE=0.5
```

Pode ocupar várias linhas, começando em `{` e terminando em `}`. Mantenha os escapes `\n` da chave privada. O projeto é lido do `project_id`, por isso `GEE_PROJECT` pode ficar vazio. Veja o [exemplo completo](docs/EARTH_ENGINE.md).

Se o `.env` ainda não existir, você pode copiar `.env.example` para `.env` no editor e preencher antes da primeira execução. Outra opção é deixar o comando criá-lo, encerrar, colar o JSON e executar `python iniciar.py` novamente. Sem credencial, o sistema funciona com clima e informa NDVI indisponível. Uma chave de API simples não substitui o JSON da conta de serviço.

Sem `DATABASE_URL`, usa SQLite em `instance/safrasmart.db`. Configure a conexão antes de iniciar para usar outro banco. Análises diretas pelo terminal (`python menu.py`) continuam disponíveis; elas não entram no histórico web. A opção web desse menu reutiliza a inicialização centralizada.

Para preparar tudo sem abrir o servidor:

```bash
python iniciar.py --preparar
```

## Conectar PostgreSQL

Crie um banco vazio no provedor escolhido. No `.env`, configure a conexão fornecida por ele:

```dotenv
DATABASE_URL=postgresql+psycopg://usuario:senha@host:5432/safrasmart?sslmode=require
```

Use os dados reais do provedor; codifique caracteres especiais da senha na URL. URLs iniciadas por `postgres://` e `postgresql://` também são aceitas pela configuração de ambiente. Não publique `.env` nem chaves de serviço.

O comando `python iniciar.py` aplica as migrações antes de iniciar a aplicação. Para revisar somente a preparação, use `python iniciar.py --preparar`.

API e worker precisam compartilhar a mesma `DATABASE_URL`. A migração cria propriedades, safras, análises e cache, com índices, chaves estrangeiras e restrições de idempotência. Trocar a URL não transfere os dados de um SQLite existente para PostgreSQL; faça uma migração dos dados separadamente se precisar conservar esse histórico.

Em Linux, para servir a API em produção:

```bash
gunicorn --bind 0.0.0.0:5000 --workers 2 safrasmart.api.server:app
```

Com Gunicorn, execute o worker como processo separado e configure HTTPS no serviço de hospedagem/proxy. A API não executa migrações automaticamente. `GET /api/health` verifica conexão/tabelas e retorna `worker.ativo` para distinguir servidor disponível de serviço de análise parado. Nenhuma credencial de banco real está incluída.

## Análise permanece na fila

Se estiver usando uma versão anterior ou iniciou somente Flask/Gunicorn, execute `python -m safrasmart.worker` em outro terminal com o mesmo ambiente e a mesma conexão. Cadastros aceitos permanecem no banco e são processados quando o worker inicia; não precisa enviá-los de novo.

Na versão atual, `python iniciar.py` prepara o banco e inicia servidor + worker local por padrão (`START_WORKER=true`). O endpoint de saúde indica `worker.ativo=false` quando nenhum worker renova seu sinal no banco. A interface informa processamento indisponível, fila, tentativa em andamento, nova tentativa e falha final separadamente. Recarregue a página após atualizar o código para carregar a interface nova.

Consultas externas têm limite por análise e até três tentativas. Ao desligar normalmente o servidor local, uma análise em execução é interrompida e devolvida à fila sem consumir uma tentativa. Em quedas abruptas, continua valendo a recuperação por lease. Não foram validados automaticamente os serviços externos nem a instância que roda no computador do usuário.

## Quando aparece “Dados insuficientes”

Essa mensagem é um resultado da análise, não significa que ela continua processando. A síntese e os avisos agora mostram o motivo específico:

| Motivo | Significado |
| --- | --- |
| `PLANTIO_HOJE` | Ainda não há dias completos após o plantio informado. Confira a data real. |
| `PLANTIO_FUTURO` | O histórico não permite avaliar uma fase futura nem definir sozinho a janela de plantio. |
| `JANELA_CURTA` | Há menos de 7 dias completos na janela da fase estimada, limite do índice experimental. |
| `COBERTURA_INSUFICIENTE` | Faltam dias de temperatura ou chuva; o relatório informa quantos estão disponíveis. |
| `CLIMA_INDISPONIVEL` | Nenhuma fonte climática forneceu dados utilizáveis; verificar conexão, timeouts e HTTP nos logs do servidor/worker. |

O formulário não preenche mais a data de hoje automaticamente. Informe a data real: alterar a data apenas para obter uma classificação muda o período analisado e invalida a interpretação.

Se o histórico vier incompleto na janela necessária, o backend tenta fontes alternativas e registra a origem de cada dia, sem transformar lacunas em zero. Consultas recentes podem usar o histórico de modelos do Forecast API para preencher dias ainda indisponíveis no arquivo. Esses registros continuam identificados como dados meteorológicos de modelo. Dados parciais não ficam bloqueando novas consultas no cache por seis horas.

A falta de NDVI, isoladamente, não impede uma síntese climática com cobertura suficiente. A chave Earth Engine não autentica as APIs de clima. Resultados já salvos não são recalculados automaticamente: após atualizar o código, salve uma nova análise para usar as correções.

Referência sobre histórico e dados recentes: https://open-meteo.com/en/docs/historical-weather-api

## Dashboard e colheita

A interface tem três áreas: **Visão geral**, **Nova análise** e **Histórico**. O dashboard mostra temperatura, chuva, NDVI, fase fenológica, cobertura das fontes e barras dos índices experimentais. Verde significa favorável (nota ≥ 7), amarelo atenção (≥ 5) e vermelho desfavorável (< 5). Dados ausentes aparecem em cinza, sem nota. Cobertura, progresso de calendário e NDVI não são classificados como saúde da lavoura.

No cadastro, informe a **data real da colheita**, se ela já ocorreu. Se o campo ficar vazio, o modal pergunta se você ainda não colheu:

- **Ainda não colhi**: salva essa confirmação e apresenta a faixa de maturação do calendário fenológico para orientar a avaliação da colheita.
- **Já colhi**: volta ao campo para informar a data antes de salvar.
- **Voltar** ou `Esc`: cancela o envio e conserva o formulário.

Datas anteriores ao plantio ou futuras são rejeitadas. Com uma colheita registrada, a fase é avaliada na data informada e as consultas de clima e satélite terminam antes dela, também respeitando o limite do ciclo estimado. A data e a confirmação ficam no JSON persistido de cada análise, sem exigir nova migração do banco. Alterar a colheita cria uma nova análise; não sobrescreve o histórico.

**A faixa exibida é uma referência de maturação, não uma data ótima de operação.** O protótipo usa o último intervalo das tabelas genéricas: soja, dias 90–119; milho para grãos, dias 105–139 após o plantio. São parâmetros experimentais herdados, sem calibração por cultivar e região. Ao ultrapassar a faixa, o painel pede revisão em campo; nunca presume que houve colheita nem avança as datas indefinidamente. Resultados antigos continuam acessíveis, mas precisam de uma nova análise para incluir esse planejamento.

O ponto de colheita depende do estádio observado, da umidade dos grãos, do manejo e das condições operacionais. A aplicação não mede umidade nem escolhe dias pela previsão meteorológica. As orientações para conferir em campo usam referências da [Embrapa para soja](https://www.infoteca.cnptia.embrapa.br/handle/doc/979883) e [milho](https://www.infoteca.cnptia.embrapa.br/handle/doc/241208); essas fontes não validam os intervalos de dias do protótipo.

O visual segue uma inspiração nas [Human Interface Guidelines da Apple](https://developer.apple.com/design/human-interface-guidelines/): hierarquia tipográfica, superfícies claras, navegação compacta e adaptação ao celular. Usa fontes do sistema e recursos locais, incluindo os novos estilos e componentes no cache offline.

## Funcionamento offline

Abra a aplicação uma vez com internet em HTTPS ou localhost e aguarde o service worker instalar. Cadastros são gravados primeiro no IndexedDB, com UUID; apenas confirmações individuais de persistência encerram o reenvio. Falhas parciais, servidor inacessível e resposta perdida preservam o registro. Resultados recebidos ficam disponíveis no dispositivo.

Novas consultas climáticas e de satélite precisam de internet no servidor. Ao reconectar, a fila é sincronizada automaticamente, com limite de 50 operações por lote e novas tentativas progressivas. Registros inválidos/conflitantes permanecem visíveis para revisão. O botão de exportação permite copiar os registros em JSON.

O histórico do servidor é isolado por uma credencial aleatória por dispositivo armazenada no IndexedDB. Isso não é um sistema de contas: não há login, recuperação de credencial nem acesso automático entre aparelhos. Limpar os dados do navegador perde essa credencial e a cópia offline; mantenha backups. Para serviço público com vários clientes, ainda é necessário implementar contas e controles operacionais contra abuso.

## NDVI opcional

As dependências do Earth Engine são instaladas pelo comando único. Cole o JSON completo da conta de serviço em `GEE_SERVICE_ACCOUNT_JSON` no `.env`. O projeto é lido automaticamente do campo `project_id`; `GEE_PROJECT` permite sobrescrevê-lo. Veja o [exemplo para copiar e colar](docs/EARTH_ENGINE.md). A conta precisa de acesso ao Earth Engine no Google Cloud. Use `ENABLE_NDVI=false` para desativar; sem credenciais, o relatório informa indisponibilidade e continua com os demais dados.

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

## Estrutura da inicialização

- `iniciar.py`: entrada única, sem dependências externas prévias.
- `safrasmart/bootstrap.py`: ambiente virtual, dependências e criação inicial do `.env`.
- `safrasmart/cli.py`: validação de configuração, migrações e inicialização.
- `safrasmart/runtime.py`: ciclo de vida do worker local.
- `safrasmart/credenciais_gee.py`: leitura do JSON da conta de serviço.

Quem já instalou as dependências pode executar `python -m safrasmart`, que pula somente a preparação do ambiente virtual. Os comandos antigos de API e worker continuam disponíveis para uso técnico; não são necessários no fluxo local recomendado. Em produção com Gunicorn, as migrações e o worker continuam sendo processos administrados separadamente.

## Testes

```bash
pip install -r requirements-dev.txt
python -m pytest -q
npm test
```

A suíte Python usa banco SQLite temporário e bloqueia chamadas meteorológicas externas. Cobre persistência, migrações, concorrência, isolamento entre dispositivos, validação, worker, lacunas climáticas, interpretação de observações e as regras de colheita. Os testes JavaScript verificam a fila diante de falhas parciais, respostas perdidas e reenvios, além de cores, notas ausentes e séries NDVI.

Para conferir os fluxos no navegador, com as dependências de desenvolvimento instaladas:

```bash
python -m playwright install chromium
python tests/e2e_dashboard.py
```

Esse teste inicia um servidor local e um SQLite temporário. Usa fixtures identificadas para clima e satélite, exercita IndexedDB, modal, datas, histórico, gráficos, visualização no celular, abertura offline e reconexão. Salva capturas em `test-results/`. Não comprova o acesso real às APIs externas. `--browser-config arquivo.json` permite usar um Chromium já instalado, com `path` e `args` no JSON; isso é apenas uma opção de teste.

Para testar com PostgreSQL, use `TEST_DATABASE_URL` **exclusivamente em um banco descartável**: a fixture remove e recria tabelas. Não aponte para produção.
