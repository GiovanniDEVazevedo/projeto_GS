import * as storage from './storage.js';
import {criarSincronizador, mensagemDaAnalise} from './sync.js';

const $ = id => document.getElementById(id);
let token;
let selecionada;
let origem = 'manual';
let precisao = null;
let intervalo = 15000;
let timer;
let atualizando = false;
let processamentoDisponivel = null;
const mensagem = texto => { $('mensagem').textContent = texto; };

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
    for (const registro of registros) {
        const nomes = {pendente: registro.sincronizado ? 'Na fila do servidor' : 'Salvo no dispositivo',
            processando: 'Em análise', ok: 'Resultado disponível', erro: 'Falha no processamento',
            invalido: 'Revisar dados', conflito: 'Conflito: crie uma nova análise'};
        const botao = textoElemento('button', `${registro.dados.propriedade || 'Propriedade'} · ${registro.dados.cultura} · ${nomes[registro.estado] || registro.estado}`, 'historico-item');
        botao.addEventListener('click', () => {
            selecionada = registro.id;
            preencherFormulario(registro.dados);
            if (registro.resultado) exibirResultado(registro.resultado);
            else { $('resultado').style.display = 'none'; mensagem(mensagemDaAnalise(registro, processamentoDisponivel)); }
        });
        $('historicoLista').append(botao);
    }
    if (selecionada) {
        const atual = registros.find(r => r.id === selecionada);
        if (atual?.resultado) exibirResultado(atual.resultado, false);
        else if (atual) mensagem(mensagemDaAnalise(atual, processamentoDisponivel));
    }
}

function preencherFormulario(dados) {
    for (const [campo, id] of Object.entries({propriedade: 'propriedade', lat: 'lat', lon: 'lon', cultura: 'cultura',
        data_plantio: 'dataPlantio', solo: 'solo', irrigacao: 'irrigacao', prod_ant: 'prodAnt', observacoes: 'observacoes'})) {
        $(id).value = dados[campo] ?? '';
    }
    origem = dados.origem_localizacao || 'manual';
    precisao = dados.precisao_m ?? null;
}

async function enviarAnalise() {
    const lat = Number($('lat').value);
    const lon = Number($('lon').value);
    if (!$('lat').value || !$('lon').value || !Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) {
        mensagem('Informe latitude e longitude válidas da propriedade.'); return;
    }
    if (!$('dataPlantio').value || !$('dataPlantio').validity.valid) { mensagem('Informe a data do plantio.'); return; }
    const prod = $('prodAnt').value === '' ? null : Number($('prodAnt').value);
    if (prod !== null && (!Number.isFinite(prod) || prod < 0 || prod > 1000)) { mensagem('Produtividade anterior: use de 0 a 1000 sc/ha.'); return; }
    $('btnAnalisar').disabled = true;
    $('loading').style.display = 'block';
    $('resultado').style.display = 'none';
    try {
        const id = crypto.randomUUID();
        const dados = {id, lat, lon, propriedade: $('propriedade').value.trim() || 'Minha propriedade',
            cultura: $('cultura').value, data_plantio: $('dataPlantio').value, solo: $('solo').value,
            irrigacao: $('irrigacao').value, prod_ant: prod, observacoes: $('observacoes').value,
            origem_localizacao: origem, precisao_m: precisao};
        await storage.salvar({id, dados, estado: 'pendente', sincronizado: false,
            criado_em: new Date().toISOString(), resultado: null});
        selecionada = id;
        mensagem('Registro salvo neste dispositivo. Será enviado quando o servidor estiver acessível.');
        await atualizarHistorico();
        void sincronizar();
    } catch (error) {
        mensagem('Não foi possível salvar no dispositivo. ' + error.message + ' Mantenha esta página aberta e copie os dados.');
    } finally {
        $('btnAnalisar').disabled = false;
        $('loading').style.display = 'none';
    }
}

function exibirResultado(r, rolar = true) {
    $('resultado').style.display = 'block';
    if (rolar) $('resultado').scrollIntoView({behavior: 'smooth'});
    const rec = r.recomendacao || {};
    const principal = rec.recomendacao_principal || {};
    const status = rec.status || r.scores?.status || 'SEM_DADOS';
    // Mapeamento exato: DESFAVORAVEL nunca recebe o estilo de FAVORAVEL.
    const estilos = {FAVORAVEL: 'recomendado', ATENCAO: 'atencao', DESFAVORAVEL: 'nao', SEM_DADOS: 'atencao'};
    $('scoreGeral').className = 'card score-geral ' + (estilos[status] || 'atencao');
    $('scoreValor').textContent = principal.nivel || 'Dados insuficientes';
    $('scoreClassif').textContent = principal.texto || '';
    $('scoreProb').textContent = rec.limitacao || '';
    $('scoresParciais').replaceChildren();
    const ind = r.indices || {};
    const mostrar = valor => valor === null || valor === undefined ? 'indisponível' : valor;
    const linhas = [
        ['Janela de observação', `${ind.periodo_inicio || '—'} a ${ind.periodo_fim || '—'}`],
        ['Temperatura média', `${mostrar(ind.temp_media_geral)} °C`],
        ['Chuva observada na janela', `${mostrar(ind.precip_total)} mm${ind.precip_completa ? '' : ' (parcial; há lacunas)'}`],
        ['Cobertura da temperatura', `${Math.round((ind.cobertura_temperatura || 0) * 100)}% dos dias`],
        ['Cobertura da chuva', `${Math.round((ind.cobertura_precipitacao || 0) * 100)}% dos dias`],
        ['Dias secos consecutivos observados', mostrar(ind.dias_consecutivos_secos)],
    ];
    for (const [nome, valor] of linhas) {
        const div = textoElemento('div', nome, 'indicador');
        div.append(textoElemento('small', String(valor)));
        $('scoresParciais').append(div);
    }
    $('faseInfo').textContent = `${r.fase?.nome_amigavel || 'Indisponível'} · ${r.fase?.dias_apos_plantio ?? '—'} dias. ${r.fase?.limitacao || ''}`;
    $('climaInfo').textContent = r.clima ? `${r.clima.fonte} · ${r.clima.periodo_inicio} a ${r.clima.periodo_fim}. Contexto: ${r.metadata?.contexto || '—'}.` : 'Dados meteorológicos indisponíveis.';
    const n = r.ndvi;
    $('ndviCard').style.display = n ? 'block' : 'none';
    $('ndviInfo').textContent = n ? `NDVI médio: ${mostrar(n.ndvi_media)}. Máximo: ${mostrar(n.ndvi_max)}. ${n.total_imagens} janela(s) válida(s). ${n.area || ''} Datas das últimas cenas: ${(n.datas || []).join(', ')}.` : '';
    for (const [card, lista, itens, formatar] of [
        ['alertasCard', 'alertasLista', rec.alertas_ativos || [], a => `${a.mensagem} [${a.severidade}; ${a.origem}]`],
        ['acoesCard', 'acoesLista', rec.acoes_recomendadas || [], a => a],
        ['errosCard', 'errosLista', r.erros || [], a => a],
    ]) {
        $(card).style.display = itens.length ? 'block' : 'none';
        $(lista).replaceChildren(...itens.map(item => textoElemento('div', formatar(item), 'alerta-item')));
    }
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
        $('dataPlantio').value = new Date().toLocaleDateString('en-CA');
        await atualizarHistorico();
        $('btnAnalisar').disabled = false;
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js', {scope: '/'}).catch(() => mensagem('Não foi possível preparar a abertura offline. Os registros locais continuam disponíveis nesta página.'));
        }
        if (navigator.storage?.persist) void navigator.storage.persist().catch(() => {});
        void sincronizar();
    } catch (error) { mensagem('Não foi possível preparar o armazenamento. ' + error.message); }
}

$('btnAnalisar').addEventListener('click', enviarAnalise);
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
