import * as storage from './storage.js';
import {criarSincronizador, mensagemDaAnalise} from './sync.js';
import {renderizarDashboard, formatarData} from './dashboard.js';

const $ = id => document.getElementById(id);
let token;
let selecionada;
let origem = 'manual';
let precisao = null;
let intervalo = 15000;
let timer;
let atualizando = false;
let processamentoDisponivel = null;
let salvando = false;
let resultadoExibido;
const mensagem = texto => { $('mensagem').textContent = texto; };

function mostrarView(nome, focar = true) {
    const views = {dashboard: ['viewDashboard', 'dashboardTitulo'], cadastro: ['viewCadastro', 'cadastroTitulo'], historico: ['viewHistorico', 'historicoTitulo']};
    if (!views[nome]) return;
    for (const [chave, [id]] of Object.entries(views)) $(id).hidden = chave !== nome;
    for (const botao of document.querySelectorAll('nav [data-view]')) {
        botao.classList.toggle('active', botao.dataset.view === nome);
        if (botao.dataset.view === nome) botao.setAttribute('aria-current', 'page');
        else botao.removeAttribute('aria-current');
    }
    if (focar) { $(views[nome][1]).focus({preventScroll: true}); window.scrollTo({top: 0, behavior: 'auto'}); }
}

function mostrarPendente(registro) {
    $('resultado').hidden = true;
    $('emptyDashboard').hidden = false;
    $('emptyTitulo').textContent = ['erro', 'invalido', 'conflito'].includes(registro.estado) ? 'Seus dados estão preservados.' : 'Sua análise está a caminho.';
    $('emptyTexto').textContent = mensagemDaAnalise(registro, processamentoDisponivel);
    $('dashboardSubtitulo').textContent = `${registro.dados.propriedade || 'Lavoura'} · ${registro.dados.cultura.toUpperCase()} · Plantio em ${formatarData(registro.dados.data_plantio)}`;
}

async function request(url, options = {}) {
    const response = await fetch(url, {...options, cache: 'no-store', signal: AbortSignal.timeout(12000),
        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token, ...options.headers}});
    let dados;
    try { dados = await response.json(); } catch { throw new Error('O servidor respondeu em formato inesperado.'); }
    if (!response.ok) {
        const error = new Error(dados.erro || 'Servidor indisponível.');
        error.status = response.status;
        throw error;
    }
    return dados;
}
const sincronizarFila = criarSincronizador({storage, request});

async function sincronizar() {
    if (atualizando || !token) return;
    atualizando = true;
    clearTimeout(timer);
    try {
        const health = await fetch('/api/health', {cache: 'no-store', signal: AbortSignal.timeout(5000)});
        if (!health.ok) throw new Error('Servidor ou banco indisponível.');
        const diagnostico = await health.json();
        processamentoDisponivel = typeof diagnostico.worker?.ativo === 'boolean' ? diagnostico.worker.ativo : null;
        await sincronizarFila();
        $('statusBadge').textContent = processamentoDisponivel === false ? 'Servidor disponível · análises pausadas' : 'Servidor disponível';
        $('statusBadge').className = processamentoDisponivel === false ? 'badge atencao' : 'badge online';
        intervalo = 15000;
    } catch {
        processamentoDisponivel = null;
        $('statusBadge').textContent = 'Sem acesso ao servidor';
        $('statusBadge').className = 'badge offline';
        intervalo = Math.min(intervalo * 2, 120000);
    } finally {
        atualizando = false;
        await atualizarHistorico().catch(error => mensagem(error.message));
        timer = setTimeout(sincronizar, intervalo);
    }
}

function textoElemento(tag, texto, classe) {
    const el = document.createElement(tag);
    el.textContent = texto;
    if (classe) el.className = classe;
    return el;
}

async function atualizarHistorico() {
    const registros = (await storage.todos()).sort((a, b) => b.criado_em.localeCompare(a.criado_em));
    const pendentes = registros.filter(r => !r.sincronizado).length;
    const processando = registros.filter(r => r.sincronizado && ['pendente', 'processando'].includes(r.estado)).length;
    $('filaInfo').textContent = `${registros.length} registro(s) salvo(s). ${pendentes} aguardando envio/revisão. ${processando} aguardando análise.`;
    $('historicoLista').replaceChildren();
    if (!registros.length) $('historicoLista').append(textoElemento('p', 'Suas análises aparecerão aqui. Crie a primeira para começar.', 'history-empty'));
    for (const registro of registros) {
        const nomes = {pendente: registro.sincronizado ? 'Na fila do servidor' : 'Salvo no dispositivo',
            processando: 'Em análise', ok: 'Resultado disponível', erro: 'Falha no processamento',
            invalido: 'Revisar dados', conflito: 'Criar nova análise'};
        const botao = textoElemento('button', '', 'history-item');
        botao.type = 'button';
        const copy = textoElemento('span', '');
        copy.append(textoElemento('strong', registro.dados.propriedade || 'Propriedade'),
            textoElemento('small', `${registro.dados.cultura.toUpperCase()} · Plantio: ${formatarData(registro.dados.data_plantio)} · ${registro.dados.data_colheita ? 'Colheita: ' + formatarData(registro.dados.data_colheita) : registro.dados.colheita_realizada === false ? 'Ainda não colhida' : 'Colheita não informada'}`));
        const tom = registro.estado === 'ok' ? 'info' : ['erro', 'invalido', 'conflito'].includes(registro.estado) ? 'warning' : 'neutral';
        botao.append(copy, textoElemento('span', nomes[registro.estado] || registro.estado, 'status-pill ' + tom));
        botao.addEventListener('click', () => {
            selecionada = registro.id;
            preencherFormulario(registro.dados);
            if (registro.resultado) { exibirResultado(registro.resultado, false, registro.dados); mensagem(''); }
            else { mostrarPendente(registro); mensagem(mensagemDaAnalise(registro, processamentoDisponivel)); }
            mostrarView('dashboard');
        });
        $('historicoLista').append(botao);
    }
    // Ao reabrir, apresentar o registro mais recente. Análises sem resultado não
    // reutilizam o dashboard de outra lavoura.
    if (!selecionada && registros.length) selecionada = registros[0].id;
    if (selecionada) {
        const atual = registros.find(r => r.id === selecionada);
        if (atual?.resultado) {
            exibirResultado(atual.resultado, false, atual.dados);
            if (!$('viewDashboard').hidden) mensagem('');
        }
        else if (atual) { mostrarPendente(atual); mensagem(mensagemDaAnalise(atual, processamentoDisponivel)); }
    }
}

function preencherFormulario(dados) {
    for (const [campo, id] of Object.entries({propriedade: 'propriedade', lat: 'lat', lon: 'lon', cultura: 'cultura',
        data_plantio: 'dataPlantio', data_colheita: 'dataColheita', solo: 'solo', irrigacao: 'irrigacao', prod_ant: 'prodAnt', observacoes: 'observacoes'})) {
        $(id).value = dados[campo] ?? '';
    }
    $('dataColheita').required = false;
    atualizarLimitesDatas();
    origem = dados.origem_localizacao || 'manual';
    precisao = dados.precisao_m ?? null;
}

function atualizarLimitesDatas() {
    const hoje = new Date();
    const isoHoje = `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}-${String(hoje.getDate()).padStart(2, '0')}`;
    $('dataColheita').max = isoHoje;
    $('dataColheita').min = $('dataPlantio').value || '1981-01-01';
    $('dataPlantio').min = '1981-01-01';
    $('dataPlantio').max = `${hoje.getFullYear() + 2}-12-31`;
}

function confirmarColheita() {
    const modal = $('colheitaModal');
    return new Promise(resolve => {
        modal.returnValue = '';
        modal.addEventListener('close', () => resolve(modal.returnValue), {once: true});
        modal.showModal();
    });
}

async function enviarAnalise() {
    if (salvando) return;
    atualizarLimitesDatas();
    if (!$('analiseForm').reportValidity()) return;
    const lat = Number($('lat').value), lon = Number($('lon').value);
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) {
        mensagem('Informe latitude e longitude válidas da propriedade.'); return;
    }
    const prod = $('prodAnt').value === '' ? null : Number($('prodAnt').value);
    if (prod !== null && (!Number.isFinite(prod) || prod < 0 || prod > 1000)) { mensagem('Produtividade anterior: use de 0 a 1000 sc/ha.'); return; }
    salvando = true;
    $('btnAnalisar').disabled = true;
    try {
        if (!$('dataColheita').value) {
            const resposta = await confirmarColheita();
            if (resposta === 'informar_data') {
                mensagem('Informe a data real em que a colheita foi realizada para continuar.');
                $('dataColheita').focus();
                return;
            }
            if (resposta !== 'nao_realizada') {
                $('btnAnalisar').disabled = false;
                $('btnAnalisar').focus();
                return;
            }
        }
        $('loading').hidden = false;
        const id = crypto.randomUUID();
        const dados = {id, lat, lon, propriedade: $('propriedade').value.trim() || 'Minha propriedade',
            cultura: $('cultura').value, data_plantio: $('dataPlantio').value, solo: $('solo').value,
            data_colheita: $('dataColheita').value || null, colheita_realizada: Boolean($('dataColheita').value),
            irrigacao: $('irrigacao').value, prod_ant: prod, observacoes: $('observacoes').value,
            origem_localizacao: origem, precisao_m: precisao};
        await storage.salvar({id, dados, estado: 'pendente', sincronizado: false,
            criado_em: new Date().toISOString(), resultado: null});
        selecionada = id;
        $('dataColheita').required = false;
        mensagem('Registro salvo neste dispositivo. Será enviado quando o servidor estiver acessível.');
        await atualizarHistorico();
        mostrarView('dashboard');
        void sincronizar();
    } catch (error) {
        mensagem('Não foi possível salvar no dispositivo. ' + error.message + ' Mantenha esta página aberta e copie os dados.');
    } finally {
        salvando = false;
        $('btnAnalisar').disabled = false;
        $('loading').hidden = true;
    }
}

function exibirResultado(r, rolar = true, dados = {}) {
    $('resultado').hidden = false;
    $('emptyDashboard').hidden = true;
    // A consulta periódica não deve fechar a tabela NDVI nem remover o foco
    // quando o resultado persistido continua igual.
    const assinatura = JSON.stringify([selecionada, r, dados]);
    if (assinatura !== resultadoExibido) {
        renderizarDashboard(r, dados);
        resultadoExibido = assinatura;
    }
    if (rolar) { mostrarView('dashboard'); $('resultado').scrollIntoView({behavior: 'smooth'}); }
}

async function definirLocalizacao(lat, lon, fonte = 'manual', accuracy = null) {
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) throw new Error('Localização inválida.');
    $('lat').value = lat.toFixed(6);
    $('lon').value = lon.toFixed(6);
    origem = fonte;
    precisao = accuracy;
    await storage.salvarConfig('localizacao', {lat, lon, fonte, accuracy});
    $('localInfo').textContent = fonte === 'gps' ? `GPS capturado. Precisão informada: ${Math.round(accuracy)} m.` :
        fonte === 'manual' ? 'Coordenadas informadas manualmente.' : 'Localização aproximada. Ajuste as coordenadas para a área da lavoura antes de analisar.';
}

function capturarGPS() {
    if (!window.isSecureContext) { mensagem('GPS e modo offline exigem HTTPS ou localhost.'); return; }
    if (!navigator.geolocation) { mensagem('GPS indisponível neste navegador. Informe as coordenadas.'); return; }
    $('gpsBtn').disabled = true;
    navigator.geolocation.getCurrentPosition(async pos => {
        try { await definirLocalizacao(pos.coords.latitude, pos.coords.longitude, 'gps', pos.coords.accuracy); }
        catch (error) { mensagem(error.message); }
        finally { $('gpsBtn').disabled = false; }
    }, error => {
        mensagem('Não foi possível capturar GPS. ' + error.message + ' Informe as coordenadas ou escolha uma busca aproximada.');
        $('gpsBtn').disabled = false;
    }, {enableHighAccuracy: true, timeout: 15000, maximumAge: 0});
}

async function buscarLocalizacao(tipo) {
    const botao = $(tipo === 'ip' ? 'ipBtn' : 'geoBtn');
    botao.disabled = true;
    try {
        if (tipo === 'cidade' && !$('cidadeInput').value.trim()) { mensagem('Informe a cidade e o estado.'); return; }
        const url = tipo === 'ip' ? 'https://ipinfo.io/json' : 'https://nominatim.openstreetmap.org/search?format=json&countrycodes=br&limit=1&q=' + encodeURIComponent($('cidadeInput').value.trim());
        const response = await fetch(url, {signal: AbortSignal.timeout(10000)});
        if (!response.ok) throw new Error('Busca temporariamente indisponível.');
        const dados = await response.json();
        const coords = tipo === 'ip' ? dados.loc?.split(',') : dados[0] && [dados[0].lat, dados[0].lon];
        if (!coords) throw new Error('Localização não encontrada.');
        await definirLocalizacao(Number(coords[0]), Number(coords[1]), tipo);
    } catch (error) { mensagem(error.message); }
    finally { botao.disabled = false; }
}

async function exportar() {
    // A cópia inclui dados, sem a credencial de acesso do dispositivo.
    const blob = new Blob([JSON.stringify(await storage.todos(), null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = 'safrasmart-registros.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function iniciar() {
    atualizarLimitesDatas();
    $('btnAnalisar').disabled = true;
    try {
        if (!window.isSecureContext) throw new Error('Abra por HTTPS ou localhost para salvar e usar o modo offline.');
        await storage.abrirBanco();
        token = await storage.tokenDispositivo();
        await storage.migrarLegado();
        let local = await storage.config('localizacao');
        if (!local) {
            const antigo = localStorage.getItem('safra_localizacao');
            if (antigo) {
                local = JSON.parse(antigo);
                await storage.salvarConfig('localizacao', local);
                localStorage.removeItem('safra_localizacao');
            }
        }
        if (local) await definirLocalizacao(local.lat, local.lon, local.fonte, local.accuracy);
        await atualizarHistorico();
        $('btnAnalisar').disabled = false;
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js', {scope: '/'}).catch(() => mensagem('Não foi possível preparar a abertura offline. Os registros locais continuam disponíveis nesta página.'));
        }
        if (navigator.storage?.persist) void navigator.storage.persist().catch(() => {});
        void sincronizar();
    } catch (error) { mensagem('Não foi possível preparar o armazenamento. ' + error.message); }
}

$('analiseForm').addEventListener('submit', event => { event.preventDefault(); void enviarAnalise(); });
$('colheitaModal').addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const botoes = [...$('colheitaModal').querySelectorAll('button:not([disabled])')];
    const primeiro = botoes[0], ultimo = botoes.at(-1);
    if (event.shiftKey && document.activeElement === primeiro) { event.preventDefault(); ultimo.focus(); }
    else if (!event.shiftKey && document.activeElement === ultimo) { event.preventDefault(); primeiro.focus(); }
});
for (const botao of document.querySelectorAll('[data-view]')) botao.addEventListener('click', event => {
    event.preventDefault(); mostrarView(botao.dataset.view);
});
$('dataPlantio').addEventListener('change', atualizarLimitesDatas);
$('dataColheita').addEventListener('input', () => { $('dataColheita').required = false; });
$('syncBtn').addEventListener('click', sincronizar);
$('exportBtn').addEventListener('click', () => exportar().catch(error => mensagem(error.message)));
$('gpsBtn').addEventListener('click', capturarGPS);
$('ipBtn').addEventListener('click', () => buscarLocalizacao('ip'));
$('geoBtn').addEventListener('click', () => buscarLocalizacao('cidade'));
for (const id of ['lat', 'lon']) $(id).addEventListener('change', () => {
    origem = 'manual'; precisao = null;
    if ($('lat').value && $('lon').value) definirLocalizacao(Number($('lat').value), Number($('lon').value)).catch(error => mensagem(error.message));
});
window.addEventListener('online', sincronizar);
window.addEventListener('offline', () => { $('statusBadge').textContent = 'Sem conexão'; $('statusBadge').className = 'badge offline'; });
document.addEventListener('visibilitychange', () => { if (!document.hidden) void sincronizar(); });
void iniciar();
