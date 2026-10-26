"""Extração determinística de relatos; não diagnostica pragas ou doenças."""
import re
import unicodedata

VERSAO = "2.0.0"


def normalizar(texto):
    return unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode().replace("-", " ")


# Vocabulário explícito evita tratar 'fértil' como parte de 'infértil'.
# Erros conhecidos são aceitos, sem fuzzy matching que invente evidências.
REGRAS = [
    ("pragas", "lagarta", r"lagartas?|largartas?|lagatas?", "alta"),
    ("pragas", "percevejo", r"percevejos?", "alta"),
    ("pragas", "pulgao", r"pulgao|pulgoes", "media"),
    ("pragas", "mosca branca", r"moscas? brancas?", "media"),
    ("pragas", "cochonilha", r"cochonilhas?", "media"),
    ("doencas", "ferrugem", r"ferrugem|ferrujem", "alta"),
    ("doencas", "fungo", r"fungos?", "alta"),
    ("doencas", "oidio", r"oidio", "alta"),
    ("doencas", "antracnose", r"antracnose", "alta"),
    ("doencas", "mancha", r"manchas?", "media"),
    ("doencas", "mofo", r"mofo", "media"),
    ("clima_negativo", "geada", r"geadas?", "alta"),
    ("clima_negativo", "seca", r"seca|estiagem|sem chuvas?|falta de chuvas?|nao chove(?:u)?", "alta"),
    ("clima_negativo", "granizo", r"granizo", "alta"),
    ("clima_negativo", "enchente", r"enchentes?|alagamento", "alta"),
    ("clima_negativo", "calor forte", r"calor forte|muito quent[ea]s?", "media"),
    ("clima_negativo", "ventania", r"ventanias?", "media"),
    ("solo_negativo", "rachado", r"rachad[oa]s?|ressecad[oa]s?|(?:solo|terra) (?:esta |ta |parece )?sec[oa]", "media"),
    ("solo_negativo", "compactado", r"compactad[oa]s?|(?:solo|terra) (?:esta |ta |parece )?dur[oa]", "alta"),
    ("solo_negativo", "encharcado", r"encharcad[oa]s?|encharchad[oa]s?|excesso de agua", "alta"),
    ("solo_negativo", "infertil", r"infertil|inferteis", "media"),
    ("solo_positivo", "umido", r"umid[oa]s?", "baixa"),
    ("solo_positivo", "fertil", r"fertil|ferteis", "baixa"),
    ("solo_positivo", "solto", r"solt[oa]s?", "baixa"),
    ("clima_positivo", "chuva boa", r"chuva boa|chuvas regulares", "baixa"),
]
PADROES = [(cat, evento, re.compile(r"\b(?:" + padrao + r")\b"), sev) for cat, evento, padrao, sev in REGRAS]
DIVISOR = re.compile(r"[.!?;,\n]+|\b(?:mas|porem|contudo|entretanto|agora|hoje)\b|\be (?=(?:apareceu|surgiu|tem|ha|o solo|a terra|as folhas)\b)")
NEGACAO = re.compile(r"\b(?:nao|sem|nem|nenhum|nenhuma|ausencia de|livre de)\b")
INCERTEZA = re.compile(r"\b(?:acho|talvez|parece|suspeit\w*|possivel|possivelmente|pode|medo de|nao sei|nao tenho certeza|nao descarto|nao descartamos)\b")
HISTORICO = re.compile(r"\b(?:ano passado|safra passada|safra anterior|antigamente|anos atras|no passado)\b|\bem 20\d{2}\b")
FUTURO = re.compile(r"\b(?:amanha|proxim[oa]|previsao|vai ter|podera)\b")


def analisar_obs(texto):
    texto = texto or ""
    norm = normalizar(texto)
    ocorrencias = []
    for clausula in DIVISOR.split(norm):
        for categoria, evento, padrao, severidade in PADROES:
            for match in padrao.finditer(clausula):
                prefixo = clausula[:match.start()]
                # 'não sei se há' expressa dúvida; 'não só' não nega a ocorrência.
                prefixo_negacao = re.sub(r"\bnao (?:so|apenas)\b", "", prefixo)
                duvida = bool(INCERTEZA.search(prefixo))
                negada = bool(NEGACAO.search(prefixo_negacao)) and not duvida
                posterior = clausula[match.end():]
                if re.match(r"\s+(?:nao (?:tem|ha|apareceu)|ausente|ausentes)\b", posterior):
                    negada = True
                temporalidade = "historica" if HISTORICO.search(clausula) else "futura" if FUTURO.search(clausula) else "atual"
                ocorrencias.append({"categoria": categoria, "evento": evento, "palavra": evento,
                    "presenca": "negada" if negada else "suspeita" if duvida else "relatada",
                    "temporalidade": temporalidade, "confirmacao": "nao_verificada",
                    "origem": "relato_produtor", "severidade": severidade,
                    "trecho_normalizado": clausula.strip()})
    # Evitar que um mesmo evento repetido multiplique a penalidade.
    unicas = {}
    for item in ocorrencias:
        unicas.setdefault((item["categoria"], item["evento"], item["presenca"], item["temporalidade"]), item)
    ocorrencias = list(unicas.values())
    alertas = [o for o in ocorrencias if o["presenca"] != "negada" and o["temporalidade"] == "atual"
               and o["categoria"] in {"pragas", "doencas", "clima_negativo", "solo_negativo"}]
    return {"texto_original": texto, "ocorrencias": ocorrencias, "alertas": alertas,
            "sentimento": "nao_utilizado", "tags": sorted({o["evento"] for o in ocorrencias}),
            "total_alertas": len(alertas), "versao_interpretador": VERSAO}
