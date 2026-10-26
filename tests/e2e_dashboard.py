"""Fluxos reais de navegador, API, SQLite e IndexedDB; serviços externos são fixtures.

Instale requirements-dev.txt e o Chromium do Playwright. Execute:
    python tests/e2e_dashboard.py
--browser-config aceita um JSON local com path/args para Chromium já instalado.
"""
import argparse
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from safrasmart.analisar import analisar
from safrasmart.api.server import create_app
from safrasmart.db import migrar
from safrasmart.worker import processar_um


SAIDA = Path(__file__).resolve().parents[1] / 'test-results'
HOJE = date.today()


def registros(page):
    return page.evaluate("""async () => (await import('/static/storage.js')).todos()""")


def serie(fim, quente=False):
    inicio = fim - timedelta(days=364)
    return {'datas': [(inicio + timedelta(days=i)).isoformat() for i in range(365)],
            'temp_max': [55. if quente else 30.] * 365, 'temp_min': [45. if quente else 20.] * 365,
            'precip': [2.] * 365, 'fonte': 'Fixture de clima para teste de interface'}


def concluir(repo, *, quente=False, satelite=False, sem_clima=False):
    def executar(dados):
        with patch('safrasmart.analisar.buscar_dados_meteo', side_effect=lambda *a, **kw: None if sem_clima else serie(kw['fim'], quente)):
            r = analisar(dados['lat'], dados['lon'], dados['cultura'], datetime.fromisoformat(dados['data_plantio']),
                         dados['solo'], dados['irrigacao'], prod_ant=dados['prod_ant'], observacoes=dados['observacoes'],
                         usar_ndvi=False, data_colheita=dados.get('data_colheita'),
                         colheita_realizada=dados.get('colheita_realizada'), hoje=HOJE)
        if satelite:
            # Série explicitamente fictícia, restrita ao teste do gráfico.
            r['ndvi'] = {'datas': [(HOJE - timedelta(days=x)).isoformat() for x in [60, 45, 30, 15]],
                         'ndvi': [.35, .52, .72, .68], 'ndvi_media': .5675, 'ndvi_max': .72,
                         'total_imagens': 4, 'fonte': 'Fixture de satélite para teste de interface',
                         'area': 'Fixture em raio de 50 m.'}
        return r
    assert processar_um(repo, executar=executar)


def preencher(page, nome, *, dias=70, colheita=None):
    page.locator('nav [data-view="cadastro"]').click()
    page.locator('#propriedade').fill(nome)
    page.locator('#lat').fill('-12.55')
    page.locator('#lon').fill('-55.72')
    page.locator('#dataPlantio').fill((HOJE - timedelta(days=dias)).isoformat())
    page.locator('#dataColheita').fill(colheita or '')


def abrir_resultado(page, nome):
    page.locator('nav [data-view="historico"]').click()
    page.locator('#syncBtn').click()
    item = page.locator('.history-item').filter(has=page.locator('strong', has_text=nome))
    expect(item.locator('.status-pill')).to_have_text('Resultado disponível')
    item.click()
    expect(page.locator('#resultado')).to_be_visible()


def sem_overflow(page):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Há conteúdo escapando horizontalmente'


def executar(config):
    SAIDA.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='safrasmart-e2e-') as pasta, sync_playwright() as p:
        url_banco = 'sqlite:///' + str(Path(pasta) / 'e2e.db')
        migrar(url_banco)
        app = create_app({'TESTING': True, 'DATABASE_URL': url_banco})
        server = make_server('127.0.0.1', 0, app, threaded=True)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        options = {'headless': True}
        if config:
            options.update(executable_path=config['path'], args=config.get('args', []))
        browser = p.chromium.launch(**options)
        context = browser.new_context(viewport={'width': 1440, 'height': 1080}, locale='pt-BR', timezone_id='America/Sao_Paulo')
        page = context.new_page()
        erros = []
        page.on('pageerror', lambda error: erros.append(str(error)))
        try:
            page.goto(base)
            expect(page.locator('#btnAnalisar')).to_be_enabled()
            expect(page.locator('#emptyDashboard')).to_be_visible()
            page.screenshot(path=str(SAIDA / 'inicio-desktop.png'), full_page=True)
            preencher(page, 'Fazenda Horizonte')
            page.screenshot(path=str(SAIDA / 'cadastro-desktop.png'), full_page=True)
            page.locator('#btnAnalisar').click()
            expect(page.locator('#colheitaModal')).to_be_visible()
            page.keyboard.press('Shift+Tab')
            expect(page.get_by_role('button', name='Voltar', exact=True)).to_be_focused()
            page.screenshot(path=str(SAIDA / 'colheita-modal.png'))
            page.get_by_role('button', name='Voltar', exact=True).click()
            expect(page.locator('#btnAnalisar')).to_be_focused()
            assert len(registros(page)) == 0
            page.locator('#btnAnalisar').click()
            page.keyboard.press('Escape')
            expect(page.locator('#colheitaModal')).not_to_be_visible()
            assert len(registros(page)) == 0
            page.locator('#btnAnalisar').click()
            page.get_by_role('button', name='Já colhi · informar a data').click()
            expect(page.locator('#dataColheita')).to_be_focused()
            assert len(registros(page)) == 0
            # É possível corrigir a resposta: data vazia volta a abrir a confirmação.
            page.locator('#btnAnalisar').click()
            page.get_by_role('button', name='Ainda não colhi · calcular faixa').click()
            expect(page.locator('#viewDashboard')).to_be_visible()
            assert len(registros(page)) == 1
            assert registros(page)[0]['dados']['colheita_realizada'] is False
            page.locator('nav [data-view="historico"]').click()
            page.locator('#syncBtn').click()
            expect(page.locator('.history-item .status-pill')).to_have_text('Na fila do servidor')
            concluir(app.extensions['repo'], satelite=True)
            abrir_resultado(page, 'Fazenda Horizonte')
            expect(page.locator('#scoreValor')).to_have_text('Favorável')
            expect(page.locator('#scoresParciais .score-item').nth(0)).to_have_class('score-item good')
            expect(page.locator('#scoresParciais .score-item').nth(2)).to_have_class('score-item neutral')
            assert page.locator('#scoresParciais .score-item').nth(2).locator('[aria-valuenow]').count() == 0
            expect(page.locator('#ndviGrafico svg')).to_be_visible()
            expect(page.locator('#colheitaDatas')).to_contain_text(str(HOJE.year))
            assert page.locator('#faseTimeline .atual').count() == 1
            assert page.locator('#faseProgresso [role="meter"]').get_attribute('aria-valuenow') == '58'
            sem_overflow(page)
            page.screenshot(path=str(SAIDA / 'dashboard-desktop.png'), full_page=True)
            page.set_viewport_size({'width': 390, 'height': 844})
            sem_overflow(page)
            page.screenshot(path=str(SAIDA / 'dashboard-celular.png'), full_page=True)
            for width in [320, 768, 1024]:
                page.set_viewport_size({'width': width, 'height': 900})
                sem_overflow(page)
            page.set_viewport_size({'width': 390, 'height': 844})
            # Reabrir preserva o resultado e a escolha da colheita no IndexedDB.
            page.reload()
            expect(page.locator('#resultado')).to_be_visible()
            assert registros(page)[0]['dados']['colheita_realizada'] is False
            # Colheita real: validações nativas bloqueiam datas futuras e anteriores ao plantio.
            preencher(page, 'Talhão já colhido', dias=120, colheita=(HOJE - timedelta(days=121)).isoformat())
            page.locator('#btnAnalisar').click()
            assert len(registros(page)) == 1
            page.locator('#dataColheita').fill((HOJE + timedelta(days=1)).isoformat())
            page.locator('#btnAnalisar').click()
            assert len(registros(page)) == 1
            page.locator('#dataColheita').fill((HOJE - timedelta(days=15)).isoformat())
            page.locator('#btnAnalisar').click()
            expect(page.locator('#viewDashboard')).to_be_visible()
            expect(page.locator('#colheitaModal')).not_to_be_visible()
            page.locator('nav [data-view="historico"]').click()
            page.locator('#syncBtn').click()
            expect(page.locator('.history-item').filter(has_text='Talhão já colhido').locator('.status-pill')).to_have_text('Na fila do servidor')
            concluir(app.extensions['repo'], quente=True)
            abrir_resultado(page, 'Talhão já colhido')
            expect(page.locator('#colheitaEstado')).to_have_text('Colheita registrada')
            expect(page.locator('#scoresParciais .score-item').nth(0)).to_have_class('score-item bad')
            expect(page.locator('#cicloValor')).to_contain_text('105')
            assert next(r for r in registros(page) if r['dados']['propriedade'] == 'Talhão já colhido')['dados']['data_colheita'] == (HOJE - timedelta(days=15)).isoformat()
            sem_overflow(page)
            # O shell novo também abre offline; o envio fica aguardando reconexão.
            page.evaluate('navigator.serviceWorker.ready')
            page.reload()
            context.set_offline(True)
            preencher(page, '<img src=x onerror=alert(1)> Offline', dias=50)
            page.locator('#btnAnalisar').click()
            page.get_by_role('button', name='Ainda não colhi · calcular faixa').click()
            expect(page.locator('#viewDashboard')).to_be_visible()
            assert len(registros(page)) == 3
            page.reload()
            expect(page.locator('#emptyDashboard')).to_be_visible()
            page.locator('nav [data-view="historico"]').click()
            expect(page.locator('#historicoLista')).to_contain_text('<img src=x onerror=alert(1)> Offline')
            assert page.locator('#historicoLista img').count() == 0
            sem_overflow(page)
            context.set_offline(False)
            page.locator('#syncBtn').click()
            expect(page.locator('.history-item').filter(has_text='Offline').locator('.status-pill')).to_have_text('Na fila do servidor')
            concluir(app.extensions['repo'], sem_clima=True)
            abrir_resultado(page, 'Offline')
            expect(page.locator('#dashboardSubtitulo')).to_contain_text('<img src=x onerror=alert(1)> Offline')
            assert page.locator('#dashboardSubtitulo img').count() == 0
            expect(page.locator('#scoreValor')).to_have_text('Dados insuficientes')
            expect(page.locator('#scoreGeral')).to_have_attribute('data-tone', 'neutral')
            expect(page.locator('#ndviValor')).to_have_text('—')
            expect(page.locator('#ndviCard')).not_to_be_visible()
            assert not erros, erros
            print('OK: modal, cancelamento, datas, persistência, dashboard, cores, NDVI, celular, offline e reconexão. Nenhum erro JavaScript.')
            print(f'Capturas: {SAIDA}')
        finally:
            context.close()
            browser.close()
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            app.extensions['repo'].engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser-config', type=Path)
    args = parser.parse_args()
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    executar(json.loads(args.browser_config.read_text()) if args.browser_config else None)
