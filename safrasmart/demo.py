from datetime import datetime
from .analisar import analisar, exibir_relatorio

# =============================================================================
# CENARIOS PARA DEMONSTRACAO AUTOMATIZADA
# =============================================================================
# 3 cenarios predefinidos que cobrem diferentes regioes, culturas e condicoes:
# 1. Sorriso/MT — Soja em alta produtividade (cenario positivo).
# 2. Cascavel/PR — Milho safrinha com estresse hidrico (cenario medio).
# 3. Uruguaiana/RS — Soja com excesso de chuvas (cenario negativo).
#
# Cada cenario tem:
#   "titulo": descricao para exibicao.
#   "lat"/"lon": coordenadas reais da regiao.
#   "cultura": "soja" ou "milho".
#   "data_plantio": data simulada de plantio.
#   "solo"/"irrigacao": condicoes da propriedade.
#   "prod_ant": produtividade anterior em sc/ha.
#   "obs": observacao do agricultor (texto livre).
#   "destaque": explicacao do que o cenario pretende demonstrar.
# =============================================================================
CENARIOS = [
    {
        "titulo": "Fazenda em Sorriso/MT — Soja de Alta Produtividade",
        "lat": -12.55, "lon": -55.72,
        "cultura": "soja",
        "data_plantio": datetime(2025, 10, 20),
        "solo": "argiloso",
        "irrigacao": "sequeiro",
        "prod_ant": 80.0,
        "obs": "plantio na epoca certa, chuvas regulares, lavoura bonita",
        "destaque": "Maior regiao produtora de soja do Brasil — solo argiloso e clima favoravel"
    },
    {
        "titulo": "Fazenda em Cascavel/PR — Milho Safrinha com Estresse Hidrico",
        "lat": -24.95, "lon": -53.46,
        "cultura": "milho",
        "data_plantio": datetime(2026, 1, 15),
        "solo": "misto",
        "irrigacao": "aspersao",
        "prod_ant": 95.0,
        "obs": "teve uma geada forte e a terra ta rachada",
        "destaque": "Parana com risco climatico — geada tardia e solo ressecado"
    },
    {
        "titulo": "Fazenda em Uruguaiana/RS — Soja com Excesso de Chuvas",
        "lat": -29.75, "lon": -57.09,
        "cultura": "soja",
        "data_plantio": datetime(2025, 11, 5),
        "solo": "arenoso",
        "irrigacao": "sequeiro",
        "prod_ant": 45.0,
        "obs": "muita chuva, solo encharcado, preocupado com a safra",
        "destaque": "Rio Grande do Sul com produtividade abaixo da media — solo arenoso e encharcamento"
    }
]


def rodar_demo():
    """
    EXECUTA a demonstracao automatizada com 3 cenarios predefinidos.
    
    PARAMETROS: nenhum — usa os cenarios definidos na constante CENARIOS.
    
    RETORNA: None — executa e exibe tudo no terminal.
    
    MOTIVO:
    Funcao criada para apresentacoes e pitches, demonstrando o SafraSmart
    sem necessidade de digitar dados manualmente. Cada cenario representa
    um perfil diferente de agricultor e regiao.
    
    FLUXO:
    1. Para cada cenario, chama analisar() com os dados predefinidos.
    2. Exibe o relatorio completo via exibir_relatorio().
    3. Mostra um resumo executivo (score, classificacao, alertas, acoes).
    4. Pausa entre cenarios para permitir comentarios do apresentador.
    5. Ao final, exibe uma tabela comparativa dos 3 cenarios.
    """
    print("=" * 55)
    print("   SAFRASMART — DEMONSTRACAO AUTOMATIZADA")
    print("   Plataforma de Decisoes Agricolas")
    print("=" * 55)

    resultados = []

    for i, cenario in enumerate(CENARIOS, 1):
        print(f"\n{'-' * 55}")
        print(f" CENARIO {i}: {cenario['titulo']}")
        print(f" {'-' * 55}")
        print(f" Destaque: {cenario['destaque']}")
        print(f"\n Executando analise...")
        print(f" Local: {cenario['lat']}, {cenario['lon']}")
        print(f" Cultura: {cenario['cultura']}, Plantio: {cenario['data_plantio'].strftime('%d/%m/%Y')}")

        resultado = analisar(
            lat=cenario['lat'], lon=cenario['lon'],
            cultura=cenario['cultura'],
            data_plantio_dt=cenario['data_plantio'],
            solo=cenario['solo'],
            irrigacao=cenario['irrigacao'],
            prod_ant=cenario['prod_ant'],
            observacoes=cenario['obs'],
            usar_ndvi=True
        )
        resultados.append(resultado)
        exibir_relatorio(resultado)

        scores = resultado.get("scores", {})
        rec = resultado.get("recomendacao", {})
        rp = rec.get("recomendacao_principal", {})

        print(f"\n RESUMO EXECUTIVO:")
        print(f"  Score Geral: {scores.get('valor', 'N/A')}/10 - {scores.get('classificacao', 'N/A')}")
        print(f"  Recomendacao: {rp.get('nivel', 'N/A')}")
        if rec.get("alertas_ativos"):
            print(f"  Alertas: {len(rec['alertas_ativos'])} ativo(s)")
        if rec.get("acoes_recomendadas"):
            print(f"  Acoes sugeridas: {len(rec['acoes_recomendadas'])}")

        if i < len(CENARIOS):
            input("\n Pressione Enter para o proximo cenario...")

    # Tabela comparativa final
    print(f"\n{'=' * 55}")
    print(" TABELA COMPARATIVA — RESUMO DOS 3 CENARIOS")
    print(f"{'=' * 55}")
    print(f"{'Local':20s} {'Score':>6s} {'Classif':>10s} {'Alertas':>8s} {'Acoes':>6s}")
    print(f"{'-' * 20} {'-' * 6} {'-' * 10} {'-' * 8} {'-' * 6}")
    for cenario, res in zip(CENARIOS, resultados):
        s = res.get("scores", {})
        r = res.get("recomendacao", {})
        n = s.get("valor", 0)
        c = s.get("classificacao", "-")
        al = len(r.get("alertas_ativos", []))
        ac = len(r.get("acoes_recomendadas", []))
        print(f"{cenario['titulo'][:20]:20s} {n:6.1f} {c:>10s} {al:8d} {ac:6d}")

    print(f"\n{'=' * 55}")
    print(" Fim da demonstracao SafraSmart")
    print(f"{'=' * 55}")


if __name__ == "__main__":
    rodar_demo()
