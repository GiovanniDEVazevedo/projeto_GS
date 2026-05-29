from datetime import datetime
def tipo_cultura():
    print("selecione o tipode cultura\n 1.milho\n 2.soja\n")
    opcao = int(input(">"))
    if opcao == 1:
        cultura = "milho"
    elif opcao == 2:
        cultura = "soja"
    else:
        print("valor invalido!")
        tipo_cultura()
    return cultura
def data_plantio():
    data = input("digite a data do plantio(dd/MM/aaaa)\n >")
    objeto_data = datetime.strptime(data , "%d/%m/%Y")
    return objeto_data
def tipo_solo():
    print("qual o tipo de solo\n 1. Arenoso\n 2. Argiloso\n 3.misto\n")
    opcao = int(input("> "))
    match opcao:
        case 1:
            solo = "arenoso"
        case 2:
            solo = "argiloso"
        case 3: 
            solo = "misto"
        case _ :
            print("valor invalido!")
            tipo_solo()
    return solo
def tipo_irrigacao():
    print("selecione o tipo de irrigacao\n 1.sequeiro\n 2.aspersao\n 3.gotejo")
    opcao = int(input("> "))
    match opcao:
        case 1:
            irrigacao = "sequeiro"
        case 2: 
            irrigacao = "aspersao"
        case 3:
            irrigacao = "gotejo"
        case _:
            print("valor invalido!")
            tipo_irrigacao()
    return irrigacao
def prod_anterior():
    prod = int(input("digite o numero de sacas da ultima coleita\n>"))
    return prod
def obs_user():
    obs = input("digite suas observacoes sobre o plantio\n>")
    return obs
