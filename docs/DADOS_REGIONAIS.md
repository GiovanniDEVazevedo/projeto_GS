# Talhões e dados regionais

## Iniciar no Windows

Na raiz do repositório, prepare as dependências e aplique a migração. Em seguida, carregue Sorriso (MT) no banco configurado para este checkout e inicie a aplicação.

```powershell
python iniciar.py --preparar
.\.venv\Scripts\python.exe -m safrasmart.regional piloto --municipios 5107925 --safra 2026/2027 --lat -12.55 --lon -55.72
python iniciar.py
```

No Linux ou macOS, use `.venv/bin/python` no segundo comando. Para ensaiar uma importação em outro banco SQLite, coloque `--banco sqlite:///piloto.db` antes de `piloto` e aponte também a aplicação para esse banco com `DATABASE_URL`.

O piloto carrega a malha municipal, cinco anos de produção (2020 a 2024), a tábua da safra solicitada e cerca de dez anos de clima. Use `python -m safrasmart.regional piloto --help` para escolher municípios, períodos e safra. O arquivo ZARC baixado do MAPA também pode ser fornecido com `--zarc-csv`. A importação prepara os dados antes de ativar as publicações no banco.

## Usar na análise

1. Abra **Nova análise**. Informe o nome da propriedade e use **Desenhar novo**. Marque os cantos do talhão em sequência no mapa, por GPS ou pelos campos de latitude e longitude. Ative o mapa base se precisar das referências do OpenStreetMap.
2. Guarde o contorno e escolha o talhão na lista. Para o exemplo de Sorriso, desenhe uma área próxima a latitude `-12.55` e longitude `-55.72`. O servidor valida o polígono, calcula uma área aproximada e determina o ponto usado nas consultas.
3. Para consultar o ZARC, expanda **Planejamento ZARC**, informe `2026/2027` e escolha a combinação da portaria conforme a cultura, o grupo da cultivar, a classe de solo e o manejo. A textura informada no cadastro fica em campo separado.
4. Salve e abra o resultado. **Contexto da lavoura** mostra o município, a PAM, a consulta ZARC, as janelas climáticas, o laudo e os registros da vistoria que estiverem disponíveis.

O contorno pode ser guardado antes de enviar uma análise. O navegador mantém o talhão e a fila de análises quando fica offline. A associação no servidor é feita ao sincronizar uma análise que usa o talhão. A tela também oferece o cadastro por coordenada para registros pontuais. Escolha um nome que identifique a propriedade no dispositivo, pois talhões novos com o mesmo nome de propriedade são agrupados.

O mapa base depende de conexão. O editor e os contornos são servidos junto com a aplicação. O NDVI usa o polígono quando informado, exclui pixels fora do limite e apresenta a cobertura e a contagem de pixels válidos nas janelas aceitas. A consulta Sentinel-2 exige as credenciais descritas em [Earth Engine](EARTH_ENGINE.md).

## Fontes

| Fonte | Unidade e recorte | Uso no painel |
| --- | --- | --- |
| [IBGE · Malhas municipais](https://www.ibge.gov.br/geociencias/organizacao-do-territorio/malhas-territoriais/15774-malhas.html) | Código IBGE, geometria SIRGAS 2000 e edição da malha | Vincula o ponto ou o contorno inteiro ao município |
| [IBGE · PAM/SIDRA](https://sidra.ibge.gov.br/pesquisa/pam/tabelas) | Tabela 1612 para o total anual. Tabela 839 para 1ª e 2ª safras de milho | Área em ha, produção em t e rendimento em kg/ha, com símbolos do SIDRA preservados |
| [MAPA · Tábua de risco ZARC](https://dados.agricultura.gov.br/dataset/tabua-de-risco-zoneamento-agricola-de-risco-climatico) | Safra, grupo, classe de solo, manejo e portaria | Mostra os decêndios indicados e a classe de risco publicada |
| [Open-Meteo · Archive API](https://open-meteo.com/en/docs/historical-weather-api) | ERA5 em dias UTC, grade aproximada de 25 km | Chuva, temperaturas e ET₀ regional, com cobertura e defasagem |
| [CHIRPS v3 · Climate Hazards Center](https://www.chc.ucsb.edu/data/chirps3) | RNL diário em grade de 0,05°, com edições final e preliminar em séries separadas | Acumulados e comparação de chuva dentro da mesma série |
| [INMET · Dados históricos](https://portal.inmet.gov.br/dadoshistoricos) | CSV horário de estação automática, agregado em dias UTC completos | Observação identificada por estação e comparação com modelo por dias pareados |
| [MapBiomas Solo](https://brasil.mapbiomas.org/iniciativas-e-produtos/solo/granulometria/) | Coleção 3 beta, estimativa em ponto de referência e camadas de 10 cm | Areia, silte e argila de referência. A amostra informada no laudo aparece separadamente |

Para complementar o município piloto, ative o ambiente Python e execute o comando da fonte desejada.

```text
python -m safrasmart.regional chirps --municipio 5107925 --lat -12.55 --lon -55.72 --inicio 2016-01-01 --fim 2025-12-31 --versao consulta-01
python -m safrasmart.regional mapbiomas --municipio 5107925 --lat -12.55 --lon -55.72 --profundidade 0
python -m safrasmart.regional inmet --municipio 5107925 --arquivo ARQUIVO_DA_ESTACAO.csv --versao 2025
```

As amostragens CHIRPS final e MapBiomas usam Earth Engine. Para carregar um recorte CHIRPS já extraído, use `chirps --arquivo RECORTE.csv --edicao final` ou `--edicao preliminar`, com município, coordenadas e versão. O CSV tem colunas `data,precipitacao_mm` e datas ISO. Preserve célula vazia nos dias sem valor.

Os anos agroclimáticos análogos usam janelas completas da mesma época e da mesma fonte. O painel compara a chuva com a mediana histórica e apresenta a distância padronizada por chuva e temperatura quando disponíveis. Os casos do talhão são registros do dispositivo que incluem retorno de vistoria e clima, fase, época e manejo compatíveis. A ordenação exige três safras anteriores. O balanço hídrico é uma estimativa regional de sete dias, com Kc, armazenamento e lâminas informados.

## Validação e reversão

- `python -m pytest -q` e `npm test` verificam os contratos e as regressões.
- `python tests/e2e_dashboard.py` exercita o contorno, a seleção offline, a sincronização, a consulta ZARC e o relatório no navegador.
- O workflow roda os testes também com um PostgreSQL descartável. Quando usar `TEST_DATABASE_URL`, escolha um banco exclusivo de teste, pois as fixtures removem as tabelas.
- `python -m safrasmart.regional listar` mostra as publicações. Use `python -m safrasmart.regional ativar ID` para reativar uma versão anterior do mesmo recorte. Os relatórios já concluídos mantêm a versão de fonte usada no processamento.
- A migração 0002 é aditiva. Em uma reversão de aplicativo, conserve as tabelas e o IndexedDB. Preserve a fila e retome a sincronização dos novos contornos quando a versão com suporte a talhões voltar.

O piloto técnico usa o isolamento por dispositivo. Contas compartilhadas com agrônomos e validação em propriedades reais são etapas separadas do piloto de software.
