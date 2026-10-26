# Google Earth Engine — colar as credenciais no .env

O backend usa a credencial **JSON da conta de serviço** do Google Cloud. Uma chave de API simples (`AIza...`) não substitui essa credencial.

## Configuração rápida

1. Na raiz do projeto, copie `.env.example` para `.env` e abra no editor. Configure:

```dotenv
START_WORKER=true
ENABLE_NDVI=true
GEE_SERVICE_ACCOUNT_JSON='COLE_AQUI_O_CONTEUDO_COMPLETO_DO_ARQUIVO_JSON'
GEE_PROJECT=
MIN_NDVI_COVERAGE=0.5
```

Substitua apenas `COLE_AQUI_O_CONTEUDO_COMPLETO_DO_ARQUIVO_JSON` pelo conteúdo inteiro do arquivo baixado do Google, começando em `{` e terminando em `}`. Mantenha as aspas simples externas. Pode colar o JSON formatado, em várias linhas; não precisa compactar.

A estrutura fica assim (exemplo ilustrativo, sem credencial válida):

```dotenv
ENABLE_NDVI=true
GEE_SERVICE_ACCOUNT_JSON='{
  "type": "service_account",
  "project_id": "seu-projeto-google-cloud",
  "private_key_id": "ID_DA_CHAVE_BAIXADA",
  "private_key": "-----BEGIN PRIVATE KEY-----\nCONTEUDO_DA_CHAVE_BAIXADA\n-----END PRIVATE KEY-----\n",
  "client_email": "sua-conta@seu-projeto-google-cloud.iam.gserviceaccount.com",
  "client_id": "ID_DA_CONTA",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs"
}'
GEE_PROJECT=
MIN_NDVI_COVERAGE=0.5
```

O exemplo acima mostra o formato; use **o JSON original completo**, incluindo quaisquer campos adicionais que ele contenha. Preserve os escapes `\n` dentro de `private_key`. Não cole apenas o trecho entre `BEGIN PRIVATE KEY` e `END PRIVATE KEY`.

`GEE_PROJECT` pode ficar vazio: a aplicação lê `project_id` automaticamente. Preencha-o apenas se precisar usar outro projeto habilitado e acessível à conta de serviço.

2. Execute um único comando:

```bash
python iniciar.py
```

Ele cria/reutiliza o ambiente virtual, instala as dependências do Earth Engine, valida o formato do JSON, aplica migrações e inicia servidor + worker. Não solicita o caminho de um arquivo de chave. Para recarregar um `.env` editado, encerre com `Ctrl+C` e execute o mesmo comando novamente.

Novas análises com data de plantio anterior a hoje passam a tentar a consulta NDVI. Uma análise concluída anteriormente não é recalculada automaticamente; salve uma nova para testar.

## Onde obter o JSON

No [Google Cloud — Contas de serviço](https://console.cloud.google.com/iam-admin/serviceaccounts), escolha o projeto e a conta de serviço usada pela aplicação. Na área de chaves dessa conta, crie uma chave do tipo **JSON**, se a política do projeto permitir, e abra o arquivo baixado para copiar o conteúdo.

O projeto precisa estar registrado para uso do Earth Engine, ter a Earth Engine API ativada e conceder acesso adequado à conta de serviço. Uma chave válida, isoladamente, não configura essas permissões.

## Cuidados com a chave

Coloque a credencial real somente no seu `.env` local ou em um gerenciador de segredos da hospedagem. `.env.example` contém apenas exemplos e é publicado no GitHub. Não cole chaves reais nele, no frontend ou na conversa.

O `.env` é ignorado pelo Git. Para produção em serviços que suportam Application Default Credentials (ADC), o Google recomenda usar identidades gerenciadas em vez de distribuir chaves privadas; esse fluxo de colagem atende à configuração local solicitada e não adiciona suporte ADC ao backend.

## Validação desta implementação

Os testes verificam leitura do `.env` multilinha, preservação da chave e de seus escapes, prioridade entre configurações, compatibilidade legada e mensagens que não exibem o segredo. Não foi feita autenticação real no Google nem usada uma chave privada real nesta alteração.

Referência oficial: https://developers.google.com/earth-engine/guides/service_account
