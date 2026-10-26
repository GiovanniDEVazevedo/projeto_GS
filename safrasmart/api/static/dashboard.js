// A apresentação usa os indicadores do motor; não transforma lacunas em zero.
export const numeroValido = valor => typeof valor === 'number' && Number.isFinite(valor);
export const formatarNumero = (valor, casas = 1) => numeroValido(valor)
    ? new Intl.NumberFormat('pt-BR', {maximumFractionDigits: casas}).format(valor) : '—';

export function formatarData(valor) {
    if (typeof valor !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(valor)) return '—';
    const data = new Date(valor + 'T12:00:00Z');
    if (!Number.isFinite(data.getTime()) || data.toISOString().slice(0, 10) !== valor) return '—';
    return new Intl.DateTimeFormat('pt-BR', {day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC'}).format(data);
}

export function visualDoIndice(indice) {
    const valor = indice?.valor;
    if (!numeroValido(valor) || valor < 0 || valor > 10) return {valor: null, tom: 'neutral', rotulo: 'Sem dados'};
    return valor >= 7 ? {valor, tom: 'good', rotulo: 'Favorável'}
        : valor >= 5 ? {valor, tom: 'warning', rotulo: 'Atenção'} : {valor, tom: 'bad', rotulo: 'Desfavorável'};
}

export function amostrasNdvi(ndvi) {
    return (ndvi?.datas || []).map((data, i) => ({data, valor: ndvi.ndvi?.[i]}))
        .filter(p => numeroValido(p.valor) && p.valor >= -1 && p.valor <= 1 && formatarData(p.data) !== '—')
        .sort((a, b) => a.data.localeCompare(b.data));
}

const $ = id => document.getElementById(id);
function elemento(tag, texto, classe) {
    const el = document.createElement(tag);
    if (texto !== undefined) el.textContent = texto;
    if (classe) el.className = classe;
    return el;
}
function estado(id, texto, tom = 'neutral') {
    $(id).textContent = texto;
    $(id).className = ($(id).classList.contains('status-pill') ? 'status-pill ' : 'metric-state ') + tom;
}
function metrica(id, valor, unidade = '', casas = 1) {
    const el = $(id);
    el.replaceChildren(document.createTextNode(formatarNumero(valor, casas)));
    if (numeroValido(valor) && unidade) el.append(elemento('small', ' ' + unidade));
}
function barra(nome, valor, maximo, rotulo, tom, detalhe = '') {
    const disponivel = numeroValido(valor) && valor >= 0 && valor <= maximo;
    const item = elemento('div', undefined, 'score-item ' + tom);
    const titulo = elemento('div', undefined, 'bar-heading');
    titulo.append(elemento('strong', nome), elemento('span', rotulo));
    const trilho = elemento('div', undefined, 'bar-track' + (disponivel ? '' : ' unavailable'));
    trilho.setAttribute('aria-label', nome + ': ' + rotulo);
    if (disponivel) {
        trilho.setAttribute('role', 'meter');
        trilho.setAttribute('aria-valuemin', '0');
        trilho.setAttribute('aria-valuemax', String(maximo));
        trilho.setAttribute('aria-valuenow', String(valor));
        trilho.setAttribute('aria-valuetext', rotulo);
        const fill = elemento('div', undefined, 'bar-fill');
        fill.style.setProperty('--fill', (valor / maximo * 100) + '%');
        trilho.append(fill);
    } else trilho.setAttribute('role', 'img');
    item.append(titulo, trilho);
    if (detalhe) item.append(elemento('p', detalhe, 'microcopy'));
    return item;
}

function renderizarColheita(c) {
    const tons = {REGISTRADA: 'info', NAO_INFORMADA: 'neutral', PLANEJAMENTO: 'info', AGUARDAR: 'info', AVALIAR: 'warning', REVISAR: 'warning'};
    estado('colheitaEstado', c?.titulo || 'Registro anterior', tons[c?.status] || 'neutral');
    $('colheitaRotulo').textContent = c?.realizada ? 'Data real informada pelo produtor' : c?.janela?.rotulo || 'Colheita ainda não informada';
    $('colheitaDatas').textContent = c?.realizada ? formatarData(c.data_colheita)
        : c?.janela ? formatarData(c.janela.inicio) + ' — ' + formatarData(c.janela.fim) : '—';
    $('colheitaDescricao').textContent = c?.descricao || 'Crie uma nova análise para registrar a colheita ou calcular a faixa estimada de maturação.';
    $('colheitaCriterios').replaceChildren(...(c?.realizada ? [] : c?.criterios || []).map(texto => elemento('li', texto)));
    $('colheitaLimitacao').textContent = c?.limitacao || 'A data de colheita não é presumida a partir do calendário.';
    // O destino é escolhido pela cultura, sem inserir uma URL arbitrária do resultado.
    const links = ['https://www.infoteca.cnptia.embrapa.br/handle/doc/979883', 'https://www.infoteca.cnptia.embrapa.br/handle/doc/241208'];
    $('colheitaFonte').hidden = !links.includes(c?.referencia_agronomica);
    if (!$('colheitaFonte').hidden) $('colheitaFonte').href = c.referencia_agronomica;
    $('faseProgresso').replaceChildren();
    $('faseTimeline').replaceChildren();
    if (c) {
        const progresso = numeroValido(c.progresso_ciclo_pct) ? Math.max(0, Math.min(100, c.progresso_ciclo_pct)) : null;
        $('faseProgresso').append(barra('Tempo no ciclo de referência', progresso, 100, formatarNumero(progresso, 0) + '%', 'info', 'Progresso do calendário. Chegar a 100% não confirma que a colheita ocorreu.'));
        for (const fase of c.fases || []) {
            const classe = ['concluida', 'atual', 'futura'].includes(fase.estado) ? fase.estado : 'futura';
            const li = elemento('li', undefined, classe);
            li.append(elemento('strong', fase.codigo), elemento('span', fase.nome));
            if (fase.estado === 'atual') li.append(elemento('em', 'Fase estimada'));
            $('faseTimeline').append(li);
        }
    }
}

function renderizarNdvi(n) {
    const pontos = amostrasNdvi(n);
    $('ndviCard').hidden = !n;
    $('ndviGrafico').replaceChildren();
    if (!n) return;
    if (!pontos.length) {
        $('ndviGrafico').append(elemento('p', 'Não há uma série temporal válida para desenhar.', 'chart-empty'));
    } else {
        const ns = 'http://www.w3.org/2000/svg';
        const svg = document.createElementNS(ns, 'svg');
        svg.setAttribute('viewBox', '0 0 520 190');
        svg.setAttribute('role', 'img');
        svg.setAttribute('aria-label', `NDVI em ${pontos.length} observações. Os valores estão na tabela abaixo. Sem classificação de saúde.`);
        const criar = (tag, attrs, texto) => {
            const el = document.createElementNS(ns, tag);
            for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, String(value));
            if (texto !== undefined) el.textContent = texto;
            svg.append(el);
            return el;
        };
        const primeira = Date.parse(pontos[0].data), ultima = Date.parse(pontos.at(-1).data);
        const x = p => primeira === ultima ? 275 : 38 + (Date.parse(p.data) - primeira) / (ultima - primeira) * 464;
        const y = p => 20 + (1 - p.valor) / 2 * 126;
        for (const v of [-1, 0, 1]) {
            const altura = y({valor: v});
            criar('line', {x1: 38, y1: altura, x2: 502, y2: altura, stroke: '#e8e8ed', 'stroke-dasharray': '3 5'});
            criar('text', {x: 5, y: altura + 4, class: 'chart-label'}, formatarNumero(v));
        }
        criar('polyline', {points: pontos.map(p => x(p) + ',' + y(p)).join(' '), fill: 'none', stroke: '#447fa5', 'stroke-width': 2.5, 'stroke-linejoin': 'round'});
        for (const p of pontos) {
            const circle = criar('circle', {cx: x(p), cy: y(p), r: 4, fill: '#447fa5', stroke: '#fff', 'stroke-width': 2});
            const title = document.createElementNS(ns, 'title');
            title.textContent = formatarData(p.data) + ': ' + formatarNumero(p.valor, 3);
            circle.append(title);
        }
        criar('text', {x: 38, y: 176, class: 'chart-label'}, formatarData(pontos[0].data));
        criar('text', {x: 502, y: 176, class: 'chart-label', 'text-anchor': 'end'}, formatarData(pontos.at(-1).data));
        const detalhes = elemento('details', undefined, 'chart-table');
        detalhes.append(elemento('summary', 'Ver valores das observações'));
        const tabela = elemento('table');
        const thead = elemento('thead'), head = elemento('tr');
        for (const titulo of ['Data da cena', 'NDVI']) { const th = elemento('th', titulo); th.scope = 'col'; head.append(th); }
        thead.append(head); tabela.append(thead);
        const tbody = elemento('tbody');
        for (const p of pontos) { const tr = elemento('tr'); tr.append(elemento('td', formatarData(p.data)), elemento('td', formatarNumero(p.valor, 3))); tbody.append(tr); }
        tabela.append(tbody); detalhes.append(tabela);
        $('ndviGrafico').append(svg, detalhes);
    }
    $('ndviInfo').textContent = `${n.fonte || 'Sentinel-2'} · ${n.total_imagens ?? pontos.length} janela(s) válida(s). ${n.area || ''} A cor do gráfico não classifica a saúde da lavoura.`;
}

export function renderizarDashboard(r, dados = {}) {
    const meta = r.metadata || {}, ind = r.indices || {}, parciais = r.scores?.parciais || {};
    const geral = visualDoIndice(r.scores);
    $('dashboardSubtitulo').textContent = `${dados.propriedade || 'Lavoura'} · ${(meta.cultura || dados.cultura || 'cultura não informada').toUpperCase()} · Plantio em ${formatarData(meta.data_plantio || dados.data_plantio)}`;
    $('scoreGeral').dataset.tone = geral.tom;
    estado('scoreValor', geral.valor === null ? 'Dados insuficientes' : geral.rotulo, geral.tom);
    $('indiceValor').textContent = formatarNumero(geral.valor);
    $('scoreClassif').textContent = r.recomendacao?.recomendacao_principal?.texto || r.scores?.detalhes?.motivo || 'Os indicadores disponíveis estão abaixo.';
    $('scoreProb').textContent = r.recomendacao?.limitacao || 'Índice experimental, sem validação agronômica.';
    const temp = visualDoIndice({valor: parciais.clima?.detalhes?.score_temp});
    const chuva = visualDoIndice({valor: parciais.clima?.detalhes?.score_precip});
    metrica('tempValor', ind.temp_media_geral, '°C');
    metrica('chuvaValor', ind.precip_total, 'mm');
    metrica('ndviValor', r.ndvi?.ndvi_media, '', 3);
    metrica('cicloValor', r.fase?.dias_apos_plantio, 'dias', 0);
    estado('tempEstado', numeroValido(ind.temp_media_geral) ? temp.valor === null ? 'Sem classificação' : temp.rotulo : 'Sem dados', temp.tom);
    estado('chuvaEstado', !numeroValido(ind.precip_total) ? 'Sem dados' : !ind.precip_completa ? 'Dados parciais' : chuva.valor === null ? 'Sem classificação' : chuva.rotulo, !ind.precip_completa && numeroValido(ind.precip_total) ? 'warning' : chuva.tom);
    estado('ndviEstado', numeroValido(r.ndvi?.ndvi_media) ? 'Observação de satélite' : 'Sem dados', numeroValido(r.ndvi?.ndvi_media) ? 'info' : 'neutral');
    estado('cicloEstado', r.colheita?.realizada ? 'Na data da colheita' : 'Fase estimada', 'info');
    $('tempDetalhe').textContent = r.fase?.temp_ideal ? `Referência experimental da fase: ${r.fase.temp_ideal[0]}–${r.fase.temp_ideal[1]} °C.` : 'Sem referência para esta fase.';
    $('chuvaDetalhe').textContent = numeroValido(ind.precip_total) ? `${formatarData(ind.periodo_inicio)} a ${formatarData(ind.periodo_fim)}${ind.precip_completa ? '' : '. Total parcial; há lacunas'}.` : 'As fontes não forneceram chuva utilizável.';
    $('cicloDetalhe').textContent = r.fase?.nome_amigavel || 'Fase indisponível.';
    $('scoresParciais').replaceChildren();
    for (const [nome, indice, detalhe] of [
        ['Condições climáticas', parciais.clima, parciais.clima?.detalhes?.motivo || 'Temperatura e chuva comparadas com a fase estimada.'],
        ['Sinais de risco', parciais.risco, 'Nota maior indica menos sinais de risco nas evidências disponíveis; não comprova segurança.'],
        ['Condições do solo', parciais.solo, parciais.solo?.detalhes?.motivo || 'Sem análise de solo para pontuar.'],
        ['Histórico produtivo', parciais.historico, parciais.historico?.detalhes?.motivo || 'Sem base comparável para pontuar.'],
    ]) {
        const visual = visualDoIndice(indice);
        const rotulo = visual.valor === null ? 'Sem dados' : formatarNumero(visual.valor) + '/10 · ' + visual.rotulo;
        $('scoresParciais').append(barra(nome, visual.valor, 10, rotulo, visual.tom, detalhe));
    }
    $('coberturaBarras').replaceChildren();
    for (const [nome, fracao] of [['Temperatura', ind.cobertura_temperatura], ['Chuva', ind.cobertura_precipitacao]]) {
        const pct = numeroValido(fracao) && fracao >= 0 && fracao <= 1 ? Math.round(fracao * 100) : null;
        $('coberturaBarras').append(barra(nome, pct, 100, pct === null ? 'Sem dados' : `${pct}% dos dias`, pct === null ? 'neutral' : pct === 100 ? 'info' : 'warning'));
    }
    $('climaInfo').textContent = r.clima ? `${r.clima.fonte} · Janela avaliada: ${formatarData(ind.periodo_inicio)} a ${formatarData(ind.periodo_fim)}. Cobertura mede disponibilidade dos dados, não a qualidade da lavoura.` : 'Fontes meteorológicas indisponíveis. Nenhuma condição foi presumida.';
    $('faseCodigo').textContent = r.fase?.nome || '—';
    $('faseInfo').replaceChildren(document.createTextNode(r.fase?.nome_amigavel || 'Fase indisponível'), elemento('small', `${formatarNumero(r.fase?.dias_apos_plantio, 0)} dias após o plantio · Referência: ${formatarData(r.fase?.data_referencia || meta.data_analise)}.`));
    $('faseLimitacao').textContent = r.fase?.limitacao || 'Fase estimada por calendário; varia com cultivar, região e manejo.';
    renderizarColheita(r.colheita);
    renderizarNdvi(r.ndvi);
    const rec = r.recomendacao || {};
    for (const [card, lista, itens, tag] of [['acoesCard', 'acoesLista', rec.acoes_recomendadas || [], 'li'], ['errosCard', 'errosLista', r.erros || [], 'li']]) {
        $(card).hidden = !itens.length;
        $(lista).replaceChildren(...itens.map(texto => elemento(tag, texto)));
    }
    $('alertasCard').hidden = !rec.alertas_ativos?.length;
    $('alertasLista').replaceChildren(...(rec.alertas_ativos || []).map(a => {
        const tom = {alta: 'bad', media: 'warning', baixa: 'info'}[a.severidade] || 'neutral';
        const item = elemento('div', a.mensagem, 'alert-item ' + tom);
        item.append(elemento('small', `Severidade ${a.severidade || 'não informada'} · ${a.origem || 'relato não verificado'}`));
        return item;
    }));
    $('resultadoReferencia').textContent = `Análise de ${formatarData(meta.data_analise)} · Motor ${meta.versao_motor || 'anterior'} · ${r.colheita?.realizada ? 'Histórico até a véspera da colheita informada' : 'Monitoramento por calendário estimado'}.`;
}
