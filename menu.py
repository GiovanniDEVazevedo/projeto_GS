def main():
    """
    MENU PRINCIPAL do SafraSmart — ponto de entrada da aplicacao.
    
    PARAMETROS: nenhum — interage via terminal com opcoes numericas.
    
    RETORNA: None — o loop so termina quando o usuario escolhe "Sair".
    
    OPCOES:
    [1] Nova analise (terminal): executa o pipeline completo via CLI.
        Chama analisar.py:main() que coleta dados via modelos.py.
    
    [2] Nova analise (web): inicia servidor Flask para acesso via navegador
        ou celular na mesma rede WiFi.
        Chama api.server:iniciar_servidor() e depois encerra o menu.
    
    [3] Executar demo: roda 3 cenarios predefinidos para apresentacao.
        Chama demo.py:rodar_demo().
    
    [4] Sair: encerra o programa.
    
    MOTIVO:
    Interface unificada que permite escolher entre as 3 formas de uso
    do SafraSmart sem precisar executar scripts separados.
    """
    print("\n" + "=" * 40)
    print("            SAFRASMART")
    print("    Plataforma de Decisoes Agricolas")
    print("=" * 40)

    while True:
        print("\n[1] Nova analise (terminal)")
        print("[2] Nova analise (web)")
        print("[3] Executar demo")
        print("[4] Sair")
        opcao = input("\nEscolha: ").strip()

        if opcao == "1":
            # Import tardio para evitar carregar todos os modulos desnecessariamente
            from analisar import main as analisar_main
            analisar_main()
        elif opcao == "2":
            from api.server import iniciar_servidor
            iniciar_servidor()
            break  # Servidor web bloqueia a execucao, entao saimos do menu
        elif opcao == "3":
            from demo import rodar_demo
            rodar_demo()
        elif opcao == "4":
            print("Saindo...")
            break
        else:
            print("Opcao invalida")


if __name__ == "__main__":
    main()
