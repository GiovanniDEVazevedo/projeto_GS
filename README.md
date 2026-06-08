# 🌱 SafraSmart

Plataforma digital para **pequenos e médios agricultores** de soja e milho.  
O sistema analisa clima, solo, produtividade anterior, imagens de satélite e as observações do agricultor para gerar um **relatório completo** com notas, alertas e recomendações — tudo baseado em dados reais.

---

## Como executar

```
pip install -r requirements.txt
python menu.py
```

---

## 📁 menu.py — Tela inicial

| Função | O que faz |
|--------|-----------|
| `limpar_tela()` | Limpa o terminal para deixar a tela limpa |
| `carregar_usuario()` | Carrega o nome do agricultor salvo nas configurações |
| `salvar_usuario(nome)` | Salva o nome do agricultor para usar depois |
| `perguntar_nome()` | Pergunta o nome na primeira vez que o programa roda |
| `main()` | Mostra o menu com 5 opções e chama a função escolhida |

### Opções do menu:
1. **Nova análise (terminal)** — digita os dados no teclado e vê o relatório na tela
2. **Nova análise (web)** — ⚠️ BETA — abre um servidor para acessar pelo celular
3. **Executar demo** — roda 3 cenários prontos (Sorriso/MT, Cascavel/PR, Uruguaiana/RS)
4. **Trocar usuário** — muda o nome registrado
5. **Sair** — encerra o programa

---

## 📁 safrasmart/modelos.py — Perguntas ao agricultor

| Função | O que faz |
|--------|-----------|
| `tipo_cultura()` | Pergunta se vai plantar **soja** ou **milho** |
| `data_plantio()` | Pergunta a **data do plantio** (formato dd/MM/aaaa) |
| `tipo_solo()` | Pergunta o **tipo de solo**: arenoso, argiloso ou misto |
| `tipo_irrigacao()` | Pergunta o **tipo de irrigação**: sequeiro, aspersão ou gotejo |
| `prod_anterior()` | Pergunta **quantas sacas** colheu na última safra |
| `obs_user()` | Pergunta se o agricultor tem **observações** sobre a lavoura |

---

## 📁 safrasmart/clima.py — Busca dados do clima

| Função | O que faz |
|--------|-----------|
| `coordenadas()` | Pergunta a **latitude e longitude** e valida se estão dentro do Brasil |
| `buscar_dados_meteo(lat, lon, dias)` | Função principal. Tenta 3 APIs de clima em sequência até conseguir dados |
| `_tentar_archive_api(lat, lon, inicio, fim)` | Tenta a **Open-Meteo Archive** (melhor API, 365 dias de dados) |
| `_tentar_nasa_api(lat, lon, inicio, fim)` | Se a primeira falhar, tenta a **NASA POWER** (mais lenta) |
| `_tentar_forecast_api(lat, lon)` | Se todas falharem, tenta a **Open-Meteo Forecast** (só 92 dias) |
| `_extrair_dados(dados, fonte)` | Organiza os dados da API num formato padrão para o sistema usar |
| `resumo(dados)` | Mostra um resumo do clima na tela (temperatura, chuva, geada etc.) |

---

## 📁 safrasmart/indices.py — Calcula índices do clima

| Função | O que faz |
|--------|-----------|
| `media_movel_temperatura(dados, janela)` | Calcula a **média da temperatura dos últimos 7 dias** para ver tendências |
| `precip_acumulada(dados, inicio, fim)` | Soma a **chuva total** num período específico |
| `dias_consecutivos_secos(dados)` | Conta **quantos dias seguidos sem chuva** (desde o último dia com chuva) |
| `dias_estresse_termico(dados)` | Conta quantos dias a **temperatura passou de 35°C** |
| `risco_geada(dados)` | Calcula a **porcentagem de dias com risco de geada** (abaixo de 2°C) |
| `amplitude_termica(dados)` | Calcula a **diferença entre a temperatura máxima e mínima** de cada dia |
| `resumo_climatico(dados)` | Junta **todos os índices acima** num único resumo |

---

## 📁 safrasmart/regras.py — Fases da planta

| Função | O que faz |
|--------|-----------|
| `obter_tabela(cultura)` | Pega a **tabela de fases** da soja ou do milho |
| `fase_atual(cultura, dias_plantio)` | Descobre **em qual fase a planta está** baseado nos dias desde o plantio |
| `faixa_com_tolerancia(min, max, pct)` | Dá uma **margem de tolerância** de 20% para mais ou para menos |

### Fases da soja:
| Fase | Dias | O que acontece |
|------|------|----------------|
| VE-V3 | 0 a 20 | Germinação e emergência |
| V4-V6 | 20 a 40 | Crescimento vegetativo |
| R1-R2 | 40 a 55 | Floração |
| R3-R5 | 55 a 90 | Enchimento dos grãos |
| R6-R8 | 90 a 120 | Maturação |

### Fases do milho:
| Fase | Dias | O que acontece |
|------|------|----------------|
| VE-V3 | 0 a 20 | Germinação e emergência |
| V6-VT | 20 a 60 | Crescimento e pendoamento |
| R1 | 60 a 75 | Floração (espigamento) |
| R2-R4 | 75 a 105 | Enchimento dos grãos |
| R5-R6 | 105 a 140 | Maturação |

---

## 📁 safrasmart/produtividade.py — Potencial de produção

| Função | O que faz |
|--------|-----------|
| `identificar_estado(lat, lon)` | Descobre **qual estado** a propriedade está pelas coordenadas GPS |
| `potencial_ajustado(lat, lon, cultura, solo, irrigacao, ndvi)` | Calcula **quantas sacas por hectare** a propriedade pode produzir, considerando solo, irrigação e NDVI |

O sistema usa dados oficiais da **CONAB 2024/25** (governo federal) para saber a produtividade média de cada estado.

---

## 📁 safrasmart/ndvi.py — Imagens de satélite

| Função | O que faz |
|--------|-----------|
| `autenticar_gee(caminho_chave)` | Faz login no **Google Earth Engine** com a chave de serviço |
| `_executar_ndvi(lat, lon, inicio, fim, intervalo, buffer)` | **Processa as imagens Sentinel-2** e calcula o NDVI (saúde da planta) |
| `buscar_ndvi(lat, lon, inicio, fim, intervalo, buffer, timeout)` | Chama a função acima com **proteção de tempo limite** (90 segundos) |
| `ndvi_por_fase(dados_ndvi, plantio, fases)` | Calcula o **NDVI médio de cada fase** da cultura |

**O que é NDVI?** É um índice que mostra se a planta está saudável (verde) ou doente/morta. Vai de -1 a 1. Valores acima de 0,6 indicam vegetação saudável.

---

## 📁 safrasmart/observacao.py — Análise do texto do agricultor

| Função | O que faz |
|--------|-----------|
| `normalizar(texto)` | **Remove acentos** e deixa tudo em minúsculo para facilitar a busca |
| `_expandir_formas(palavra)` | **Gera variações** de gênero (ex: "rachado" vira "rachado, rachada, rachados, rachadas") |
| `analisar_obs(texto)` | **Procura palavras-chave** no texto do agricultor e classifica o sentimento |

### O que o sistema reconhece:
| Categoria | Exemplos |
|-----------|----------|
| **Pragas** | lagarta, ferrugem, percevejo, pulgão |
| **Doenças** | fungo, oídio, antracnose, mancha, mofo |
| **Clima bom** | chuva boa, úmido, fresco |
| **Clima ruim** | geada, seca, granizo, enchente, calor forte |
| **Solo bom** | úmido, solto, fértil |
| **Solo ruim** | rachado, duro, compactado, encharcado |
| **Sentimento bom** | bom, ótimo, excelente, tranquilo, satisfeito |
| **Sentimento ruim** | preocupado, perdendo, ruim, péssimo, horror |

---

## 📁 safrasmart/scores.py — Notas (0 a 10)

| Função | O que faz |
|--------|-----------|
| `score_clima(dados, indices, fase)` | **Nota para o clima**: compara temperatura e chuva com o ideal da fase |
| `score_solo(solo, irrigacao)` | **Nota para o solo**: argiloso nota mais alta, arenoso nota mais baixa |
| `score_historico(prod_ant, lat, lon, cultura, solo, irrig, ndvi)` | **Nota para o histórico**: compara a produção anterior com o potencial regional |
| `score_risco(analise_obs, indices, temp_media, temp_ideal)` | **Nota para o risco**: começa em 10 e desconta por problemas (geada, seca, falta de informação) |
| `score_geral(scores)` | **Nota final**: clima (40%) + solo (20%) + histórico (20%) + risco (20%) |
| `classificar(valor)` | **Classifica a nota** em texto: Recomendado (7+), Atenção (5-6,9), Não recomendado (0-4,9) |
| `_confianca_geral(confiancas)` | Define a **confiança geral** da análise |

### Tabela de classificação:
| Nota | Classificação | Significado |
|------|--------------|-------------|
| 8 a 10 | Ótimo | Pode plantar tranquilo |
| 6 a 7,9 | Bom | Monitorar de perto |
| 4 a 5,9 | Atenção | Risco considerável |
| 0 a 3,9 | Crítico | Repensar o plantio |

---

## 📁 safrasmart/recomendador.py — Recomendação final

| Função | O que faz |
|--------|-----------|
| `recomendar(scores, alertas_obs, resumo_indices)` | **Gera a recomendação final** com base nas notas, alertas e índices |
| `_ajustar_confianca(base, geral)` | **Combina a confiança** da recomendação com a confiança dos dados |
| `_calcular_probabilidade(valor, confianca, alertas)` | Calcula a **chance de sucesso** da safra em porcentagem |

### 3 níveis de recomendação:
- **Recomendado** (nota 7+): condições favoráveis para plantar
- **Atenção** (nota 5 a 6,9): condições regulares, ter cuidado
- **Não recomendado** (nota abaixo de 5): condições desfavoráveis, não plantar agora

---

## 📁 safrasmart/analisar.py — O coração do sistema

| Função | O que faz |
|--------|-----------|
| `analisar(lat, lon, cultura, plantio, solo, irrigacao, prod_ant, obs, usar_ndvi)` | **Executa o pipeline completo** passando por todas as 6 etapas |
| `exibir_relatorio(resultado)` | **Mostra o relatório bonito** na tela com todas as informações |
| `main()` | Versão para usar no **terminal**: pergunta os dados e chama `analisar()` |

### As 6 etapas do pipeline:
1. **Clima** — busca dados reais de temperatura e chuva
2. **Fenologia** — descobre em qual fase a planta está
3. **NDVI** — busca imagens de satélite (opcional)
4. **Observação** — analisa o texto do agricultor
5. **Scores** — calcula as notas
6. **Recomendação** — gera o parecer final

---

## 📁 safrasmart/demo.py — Demonstração automática

| Função | O que faz |
|--------|-----------|
| `rodar_demo()` | Executa **3 cenários prontos** para apresentação e mostra uma tabela comparativa |

### Cenários:
1. **Sorriso/MT** — Soja de alta produtividade (cenário positivo)
2. **Cascavel/PR** — Milho safrinha com estresse hídrico (cenário médio)
3. **Uruguaiana/RS** — Soja com excesso de chuvas (cenário negativo)

---

## 📁 safrasmart/api/server.py — Versão web ⚠️ BETA

| Função | O que faz |
|--------|-----------|
| `index()` | Mostra a **página inicial** do sistema no navegador |
| `api_analisar()` | **Recebe os dados do formulário web** e devolve o resultado em JSON |
| `api_sync()` | **Sincroniza análises** feitas offline quando volta a internet |
| `iniciar_servidor()` | **Liga o servidor** na rede Wi-Fi local para acesso pelo celular |

**⚠️ Esta função ainda está em fase de testes (BETA). Pode não funcionar corretamente em todos os dispositivos.**

---

## 📁 safrasmart/\_\_init\_\_.py

Arquivo **vazio**. Só existe para o Python entender que a pasta `safrasmart/` é um pacote e os imports funcionarem.

## 📁 safrasmart/api/\_\_init\_\_.py

Arquivo **vazio**. Mesma função do acima, mas para a subpasta `api/`.

---

## Como o sistema funciona por dentro

```
Agricultor digita dados
        ↓
menu.py chama analisar.py
        ↓
analisar.py executa as 6 etapas:
  1. clima.py → busca dados do tempo
  2. regras.py → descobre a fase da planta
  3. ndvi.py → busca satélite (opcional)
  4. observacao.py → analisa texto
  5. scores.py → calcula notas
  6. recomendador.py → gera parecer
        ↓
exibir_relatorio() mostra o resultado
```

Tudo em **dados reais**: Open-Meteo (clima), NASA POWER (clima), Sentinel-2 via Google Earth Engine (satélite), CONAB (produtividade média dos estados).

Nada de inteligência artificial nas decisões — apenas regras agronômicas, estatística e comparação com faixas ideais.
