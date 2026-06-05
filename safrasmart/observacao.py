import unicodedata


def normalizar(texto):
    """
    NORMALIZA o texto removendo acentos e convertendo para minusculas.
    
    PARAMETROS:
        texto (str): texto bruto digitado pelo agricultor.
    
    RETORNA: str — texto em lowercase sem acentos.
        Ex: "Está sêca" -> "esta seca"
    
    MOTIVO:
    Agricultores podem digitar com ou sem acentos, em maiusculas ou minusculas.
    A normalizacao garante que a busca por palavras-chave funcione
    independentemente dessas variacoes.
    
    PROCESSO:
    1. lower(): converte para minusculas.
    2. normalize('NFKD'): decompoe caracteres acentuados (ex: "é" -> "e" + "'").
    3. encode('ASCII', 'ignore'): remove os acentos (caracteres nao-ASCII).
    4. decode(): volta para string.
    """
    texto = texto.lower()
    texto = unicodedata.normalize('NFKD', texto)
    texto = texto.encode('ASCII', 'ignore').decode('ASCII')
    return texto


def _expandir_formas(palavra):
    """
    EXPANDE uma palavra em suas variacoes de genero e numero.
    
    PARAMETROS:
        palavra (str): palavra ja normalizada (ex: "rachado").
    
    RETORNA: set[str] — conjunto com as variacoes.
        Ex: "rachado" -> {"rachado", "rachada", "rachados", "rachadas"}
        Ex: "rachada" -> {"rachada", "rachado", "rachados", "rachadas"}
        Ex: "seca" -> {"seca", "seco", "secos", "secas"}
    
    MOTIVO DOS PARAMETROS:
    palavra: a entrada pode ser masculina ou feminina. A expansao cobre
    ambas as formas para匹配 com o texto do agricultor.
    
    LIMITACAO CONHECIDA:
    "seca" (substantivo = estiagem) expande para "seco" (adjetivo), que
    pode causar falsos positivos. Uma melhoria futura seria usar
    lematizacao em vez de expansao por sufixo.
    """
    formas = {palavra}
    if palavra.endswith("o"):
        base = palavra[:-1]
        formas.update([base + "a", base + "os", base + "as"])
    elif palavra.endswith("a"):
        base = palavra[:-1]
        formas.update([base + "o", base + "os", base + "as"])
    return formas


# =============================================================================
# DICIONARIO DE PALAVRAS-CHAVE PARA ANALISE DE OBSERVACOES
# =============================================================================
# Estrutura: {categoria: [(palavra, severidade), ...]}
#
# As categorias sao divididas em 3 dimensoes (clima, solo, sentimento)
# e cada uma tem variantes positivas (boas) e negativas (ruins).
#
# As categorias POSITIVAS sao FILTRADAS em analisar.py antes de passar
# para o recomendador, porque o recomendador so lida com alertas de risco.
# Mas elas sao mantidas no dict para contagem de sentimento.
#
# Categorias:
#   pragas / doencas: sempre negativas, severidade varia.
#   clima_positivo / solo_positivo: usadas so para sentimento.
#   clima_negativo / solo_negativo: geram alertas no recomendador.
#   sentimento_positivo / sentimento_negativo: influenciam score de risco.
# =============================================================================
PALAVRAS = {
    "pragas": [
        ("lagarta", "alta"), ("ferrugem", "alta"), ("percevejo", "alta"),
        ("pulgao", "media"), ("mosca branca", "media"), ("cochonilha", "media")
    ],
    "doencas": [
        ("fungo", "alta"), ("oidio", "alta"), ("antracnose", "alta"),
        ("mancha", "media"), ("mofo", "media")
    ],
    "clima_positivo": [
        ("chuva boa", "baixa"), ("umido", "baixa"), ("fresco", "baixa")
    ],
    "clima_negativo": [
        ("geada", "alta"), ("seca", "alta"), ("granizo", "alta"),
        ("enchente", "alta"), ("estiagem", "alta"),
        ("calor forte", "media"), ("ventania", "media")
    ],
    "solo_positivo": [
        ("umido", "baixa"), ("solto", "baixa"), ("fertil", "baixa")
    ],
    "solo_negativo": [
        ("rachado", "media"), ("duro", "media"),
        ("compactado", "alta"), ("encharcado", "alta")
    ],
    "sentimento_positivo": [
        ("bom", "baixa"), ("otimo", "baixa"), ("excelente", "baixa"),
        ("tranquilo", "baixa"), ("satisfeito", "baixa")
    ],
    "sentimento_negativo": [
        ("preocupado", "alta"), ("perdendo", "alta"),
        ("ruim", "baixa"), ("pessimo", "baixa"), ("horror", "alta")
    ]
}


def analisar_obs(texto):
    """
    ANALISA o texto livre do agricultor e extrai alertas, sentimento e tags.
    
    PARAMETROS:
        texto (str): observacao livre digitada pelo agricultor
            (ex: "teve uma geada forte e a terra ta rachada").
    
    RETORNA: dict com 5 chaves:
        "texto_original" (str): o texto exato digitado (sem modificacoes).
        "alertas" (list[dict]): cada alerta tem {"categoria", "palavra",
            "severidade"}. Ex: [{"categoria": "clima_negativo", "palavra":
            "geada", "severidade": "alta"}, ...].
        "sentimento" (str): "positivo", "negativo" ou "neutro" baseado na
            contagem de alertas positivos vs negativos.
        "tags" (list[str]): palavras-chave unicas encontradas (sem repeticoes).
        "total_alertas" (int): quantidade total de alertas.
    
    Se o texto for vazio, retorna sentimento "neutro" e alertas vazio.
    
    MOTIVO DOS PARAMETROS:
    texto: unico parametro necessario — e a observacao em linguagem natural.
    O processamento e intencionalmente simples (busca de substring) porque:
    1. Agricultores usam vocabulario limitado e repetitivo.
    2. Modelos de NLP complexos seriam overkill para este dominio.
    3. A abordagem e deterministicamente reproduzivel (mesmo texto = mesmo resultado).
    
    FLUXO:
    1. Normaliza o texto (remove acentos, lowercase).
    2. Substitui hifen por espaco (para capturar "mosca-branca" como "mosca branca").
    3. Para cada palavra no dicionario, expande formas e verifica se aparece.
    4. Conta positivos vs negativos para determinar sentimento.
    5. Retorna o dict estruturado.
    """
    if not texto or not texto.strip():
        return {
            "texto_original": texto,
            "alertas": [],
            "sentimento": "neutro",
            "tags": [],
            "total_alertas": 0
        }

    texto_norm = normalizar(texto)
    texto_norm = texto_norm.replace("-", " ")

    alertas = []
    tags = []

    for categoria, palavras in PALAVRAS.items():
        for palavra, severidade in palavras:
            palavra_norm = normalizar(palavra)
            formas = _expandir_formas(palavra_norm)

            encontrou = False
            for forma in formas:
                if forma in texto_norm:
                    encontrou = True
                    break

            if encontrou:
                alertas.append({
                    "categoria": categoria,
                    "palavra": palavra,
                    "severidade": severidade
                })
                if palavra not in tags:
                    tags.append(palavra)

    # Classifica o sentimento comparando quantidade de alertas positivos vs negativos
    cont_positivo = 0
    cont_negativo = 0

    for alerta in alertas:
        cat = alerta["categoria"]
        if cat in ("sentimento_positivo", "clima_positivo", "solo_positivo"):
            cont_positivo += 1
        elif cat in ("sentimento_negativo", "clima_negativo", "solo_negativo",
                      "pragas", "doencas"):
            cont_negativo += 1

    if cont_positivo > cont_negativo:
        sentimento = "positivo"
    elif cont_negativo > cont_positivo:
        sentimento = "negativo"
    else:
        sentimento = "neutro"

    return {
        "texto_original": texto,
        "alertas": alertas,
        "sentimento": sentimento,
        "tags": tags,
        "total_alertas": len(alertas)
    }


if __name__ == "__main__":
    print("Teste 1 - Vazio:")
    print(analisar_obs(""))
    print()

    print("Teste 2 - Pragas:")
    print(analisar_obs("Estou preocupado, tem lagarta na lavoura"))
    print()

    print("Teste 3 - Feminino:")
    print(analisar_obs("teve uma geada forte e a terra ta rachada"))
    print()

    print("Teste 4 - Positivo:")
    print(analisar_obs("otimo, a chuva boa deixou o solo umido"))
    print()

    print("Teste 5 - Acentos:")
    print(analisar_obs("Está sêca, a situação é péssima"))
    print()

    print("Teste 6 - Plural:")
    print(analisar_obs("as terras estao rachadas e compactadas"))
    print()

    print("Teste 7 - Hifen:")
    print(analisar_obs("tem mosca-branca na lavoura"))
