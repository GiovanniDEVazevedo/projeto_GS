import unicodedata


def normalizar(texto):
    texto = texto.lower()
    texto = unicodedata.normalize('NFKD', texto)
    texto = texto.encode('ASCII', 'ignore').decode('ASCII')
    return texto


def _expandir_formas(palavra):
    formas = {palavra}
    if palavra.endswith("o"):
        base = palavra[:-1]
        formas.update([base + "a", base + "os", base + "as"])
    elif palavra.endswith("a"):
        base = palavra[:-1]
        formas.update([base + "o", base + "os", base + "as"])
    return formas


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
