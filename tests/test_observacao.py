import pytest
from safrasmart.observacao import analisar_obs
from safrasmart.recomendador import recomendar

# Corpus de regressão explícito (não é validação agronômica nem medição em campo).
CASOS = [
    ('Tem muita lagarta na plantação', {'lagarta'}),
    ('As lagartas apareceram', {'lagarta'}),
    ('Vi largartas nas folhas', {'lagarta'}),
    ('Encontrei lagata na soja', {'lagarta'}),
    ('Há percevejos no milho', {'percevejo'}),
    ('Apareceram pulgões', {'pulgao'}),
    ('Tem pulgao', {'pulgao'}),
    ('Tem mosca-branca', {'mosca branca'}),
    ('Há moscas brancas', {'mosca branca'}),
    ('Cochonilhas apareceram', {'cochonilha'}),
    ('As folhas têm ferrugem', {'ferrugem'}),
    ('Acho que é ferrujem', {'ferrugem'}),
    ('Apareceram fungos', {'fungo'}),
    ('Parece oídio', {'oidio'}),
    ('Suspeito de antracnose', {'antracnose'}),
    ('Folhas com manchas', {'mancha'}),
    ('Tem mofo', {'mofo'}),
    ('Teve geada ontem', {'geada'}),
    ('Estamos em estiagem', {'seca'}),
    ('Sem chuva há dias', {'seca'}),
    ('Falta de chuva na região', {'seca'}),
    ('Não chove há semanas', {'seca'}),
    ('Calor forte', {'calor forte'}),
    ('Granizo na plantação', {'granizo'}),
    ('Houve enchente', {'enchente'}),
    ('Ventania forte', {'ventania'}),
    ('A terra está rachada', {'rachado'}),
    ('Terras rachadas', {'rachado'}),
    ('Solo ressecado', {'rachado'}),
    ('O solo está compactado', {'compactado'}),
    ('Terras compactadas', {'compactado'}),
    ('A terra está dura', {'compactado'}),
    ('Solo encharcado', {'encharcado'}),
    ('As terras estão encharcadas', {'encharcado'}),
    ('Solo encharchado', {'encharcado'}),
    ('Excesso de água no solo', {'encharcado'}),
    ('Solo infértil', {'infertil'}),
    ('Terras inférteis', {'infertil'}),
    ('Não encontrei lagartas', set()),
    ('Nao tem lagarta', set()),
    ('Não há ferrugem', set()),
    ('Não vi sinais de lagarta', set()),
    ('Sem lagartas nem percevejos', set()),
    ('Nenhuma cochonilha encontrada', set()),
    ('Lavoura livre de pulgões', set()),
    ('Ausência de fungos', set()),
    ('Não está encharcado', set()),
    ('Não houve geada', set()),
    ('O solo não é infértil', set()),
    ('Não há falta de chuva', set()),
    ('Ano passado tivemos geada', set()),
    ('Na safra anterior teve lagarta', set()),
    ('Antigamente havia ferrugem', set()),
    ('Em 2025 tivemos percevejo', set()),
    ('A previsão é de geada amanhã', set()),
    ('Pode haver lagarta na próxima safra', set()),
    ('Estou preocupado', set()),
    ('Estou tranquilo e satisfeito', set()),
    ('Ótimo, a chuva boa deixou o solo úmido', set()),
    ('Solo fértil e solto', set()),
    ('Um livro sobre lagartamente', set()),
    ('', set()),
    ('Não tem lagarta, mas tem ferrugem', {'ferrugem'}),
    ('Não tem lagarta e há percevejos', {'percevejo'}),
    ('Ano passado teve geada, hoje tem pulgões', {'pulgao'}),
    ('Não sei se tem lagarta', {'lagarta'}),
    ('Não tenho certeza se é ferrugem', {'ferrugem'}),
    ('Não descarto lagarta', {'lagarta'}),
    ('Não só lagartas mas também percevejos', {'lagarta', 'percevejo'}),
    ('Lagartas ausentes', set()),
    ('Não está encharcado, está compactado', {'compactado'}),
]


@pytest.mark.parametrize('texto,esperado', CASOS)
def test_corpus(texto, esperado):
    res = analisar_obs(texto)
    assert {a['evento'] for a in res['alertas']} == esperado
    assert all(a['confirmacao'] == 'nao_verificada' for a in res['ocorrencias'])


def test_nega_historia_e_duvida_rastreaveis():
    assert analisar_obs('Não tem lagarta')['ocorrencias'][0]['presenca'] == 'negada'
    assert analisar_obs('Ano passado houve geada')['ocorrencias'][0]['temporalidade'] == 'historica'
    assert analisar_obs('Acho que apareceu ferrugem')['alertas'][0]['presenca'] == 'suspeita'
    r = analisar_obs('Solo infértil')
    assert not any(o['evento'] == 'fertil' for o in r['ocorrencias'])
    assert analisar_obs('lagarta lagarta lagarta')['total_alertas'] == 1


def test_encharcado_e_ferrugem_mapeados_corretamente():
    obs = analisar_obs('Solo encharcado e ferrugem nas folhas')
    r = recomendar({'geral': {'status': 'ATENCAO'}}, obs['alertas'], {})
    assert {a['tipo'] for a in r['alertas_ativos']} == {'excesso_hidrico', 'doenca'}
    assert all('adequada' not in a['mensagem'] for a in r['alertas_ativos'])
    assert 'probabilidade' not in r


def test_sentimento_nao_produz_alerta_agronomico():
    r = recomendar({'geral': None}, analisar_obs('Estou preocupado e pessimista')['alertas'], {})
    assert r['status'] == 'SEM_DADOS'
    assert r['alertas_ativos'] == []
