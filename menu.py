import json
import os
import sys

ARQUIVO_CONFIG = os.path.join(os.path.dirname(__file__), ".usuario_config.json")


def limpar_tela():
    """
    LIMPA o terminal de acordo com o sistema operacional.
    Usa 'cls' no Windows e 'clear' no Linux/macOS.
    """
    os.system("cls" if sys.platform.startswith("win") else "clear")


def carregar_usuario():
    """
    CARREGA os dados do usuario salvos no arquivo de configuracao.
    
    PARAMETROS: nenhum.
    RETORNA: str — nome do usuario, ou None se nao houver configuracao salva.
    """
    if os.path.exists(ARQUIVO_CONFIG):
        try:
            with open(ARQUIVO_CONFIG, "r") as f:
                dados = json.load(f)
                return dados.get("nome")
        except (json.JSONDecodeError, IOError):
            return None
    return None


def salvar_usuario(nome):
    """
    SALVA o nome do usuario no arquivo de configuracao para uso futuro.
    
    PARAMETROS:
        nome (str): nome do usuario.
    RETORNA: None.
    """
    try:
        with open(ARQUIVO_CONFIG, "w") as f:
            json.dump({"nome": nome}, f)
    except IOError:
        pass


def perguntar_nome():
    """
    PERGUNTA o nome do usuario no primeiro uso e salva para proximas sessoes.
    
    PARAMETROS: nenhum.
    RETORNA: str — nome informado pelo usuario.
    """
    print("\n--- Bem-vindo ao SafraSmart! ---")
    nome = input("Por favor, digite seu nome: ").strip()
    if not nome:
        nome = "Agricultor"
    salvar_usuario(nome)
    print(f"Prazer em conhece-lo(a), {nome}!\n")
    return nome


def main():
    """
    MENU PRINCIPAL do SafraSmart — personalizado com o nome do usuario.
    
    Fluxo:
    1. Carrega ou pergunta o nome do usuario.
    2. Exibe menu personalizado com 5 opcoes.
    3. Executa a opcao escolhida em loop ate o usuario sair.
    
    OPCOES:
    [1] Nova analise (terminal): executa o pipeline completo via CLI.
    [2] Nova analise (web): inicia servidor Flask para acesso via navegador.
    [3] Executar demo: roda 3 cenarios predefinidos para apresentacao.
    [4] Trocar usuario: permite alterar o nome registrado.
    [5] Sair: encerra o programa.
    """
    nome = carregar_usuario()
    if not nome:
        limpar_tela()
        nome = perguntar_nome()

    while True:
        limpar_tela()
        print("=" * 40)
        print(f"    SAFRASMART")
        print(f"    Ola, {nome}!")
        print("    Plataforma de Decisoes Agricolas")
        print("=" * 40)

        print("\n[1] Nova analise (terminal)")
        print("[2] Nova analise (web)")
        print("[3] Executar demo")
        print("[4] Trocar usuario")
        print("[5] Sair")
        opcao = input("\nEscolha: ").strip()

        if opcao == "1":
            limpar_tela()
            from safrasmart.analisar import main as analisar_main
            analisar_main()
            input("\nPressione Enter para voltar ao menu...")
        elif opcao == "2":
            limpar_tela()
            from safrasmart.api.server import iniciar_servidor
            iniciar_servidor()
            break
        elif opcao == "3":
            limpar_tela()
            from safrasmart.demo import rodar_demo
            rodar_demo()
            input("\nPressione Enter para voltar ao menu...")
        elif opcao == "4":
            limpar_tela()
            nome = perguntar_nome()
            input("\nPressione Enter para voltar ao menu...")
        elif opcao == "5":
            limpar_tela()
            print(f"\nSaindo... Ate logo, {nome}!")
            break
        else:
            input("Opcao invalida. Pressione Enter para continuar...")


if __name__ == "__main__":
    main()
