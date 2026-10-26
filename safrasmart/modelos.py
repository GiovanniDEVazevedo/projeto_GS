"""Entradas do terminal com repetição iterativa e validação."""
from datetime import datetime


def _escolher(titulo, opcoes):
    while True:
        print(titulo)
        for i, opcao in enumerate(opcoes, 1):
            print(f"{i}. {opcao}")
        texto = input("> ").strip()
        if texto.isdigit() and 1 <= int(texto) <= len(opcoes):
            return opcoes[int(texto) - 1]
        print("Opção inválida, tente novamente.")


def tipo_cultura():
    return _escolher("Cultura", ["milho", "soja"])


def tipo_solo():
    return _escolher("Tipo de solo", ["arenoso", "argiloso", "misto"])


def tipo_irrigacao():
    return _escolher("Irrigação", ["sequeiro", "aspersao", "gotejo"])


def data_plantio():
    while True:
        try:
            return datetime.strptime(input("Data do plantio (dd/MM/aaaa): "), "%d/%m/%Y")
        except ValueError:
            print("Data inválida.")


def prod_anterior():
    from .validacao import EntradaInvalida, numero
    while True:
        texto = input("Produtividade anterior em sc/ha (Enter se desconhecida): ").strip()
        if not texto:
            return None
        try:
            return numero(texto, "prod_ant", 0, 1000)
        except EntradaInvalida as erro:
            print(erro)


def obs_user():
    while True:
        texto = input("Observações da lavoura: ")
        if len(texto) <= 4000:
            return texto
        print("Use até 4000 caracteres.")
