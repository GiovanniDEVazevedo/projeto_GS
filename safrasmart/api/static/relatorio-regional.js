const MENSAGENS = {
    municipio_nao_identificado: 'O ponto ou o contorno está fora dos municípios carregados.',
    municipio_sem_cobertura: 'O município escolhido ainda não tem um recorte carregado.',
    municipio_diverge_da_area: 'O ponto ou o contorno diverge da malha do município escolhido.',
    regional_indisponivel: 'A consulta regional ficou indisponível nesta análise.',
    consulta_incompleta: 'Escolha a safra e a combinação da portaria no formulário de análise.',
    sem_referencia: 'Sem publicação carregada para essa combinação.',
    combinacao_indisponivel: 'A combinação salva não consta na publicação ativa para este recorte.',
    parametros_ausentes: 'Informe data da janela, armazenamento e Kc para solicitar a estimativa.',
    fonte_et0_ausente: 'Carregue uma série com chuva e ET₀ no município.',
    janela_fora_do_cultivo: 'A janela de sete dias deve estar entre o plantio e a véspera da data de referência.',
    dados_diarios_incompletos: 'Falta chuva, ET₀ ou irrigação diária na janela.',
};
const RECORTES = {total_anual: 'Total anual', primeira_safra: '1ª safra', segunda_safra: '2ª safra'};

export function renderizarRelatorioRegional(regional, casosTalhao, dados, {elemento, formatarNumero, formatarData}) {
    const card = document.getElementById('regionalCard');
    const raiz = document.getElementById('regionalResultado');
    raiz.replaceChildren();
    card.hidden = !regional && !dados.talhao && !dados.laudo_solo && !dados.vistoria;
    if (card.hidden) return;
    const texto = (pai, valor) => pai.append(elemento('p', valor, 'microcopy'));
    function secao(titulo) {
        const detalhes = elemento('details');
        detalhes.append(elemento('summary', titulo));
        raiz.append(detalhes);
        return detalhes;
    }
    function tabela(pai, colunas, registros) {
        const caixa = elemento('div', undefined, 'regional-table');
        const t = elemento('table'), cabecalho = elemento('thead'), corpo = elemento('tbody'), linha = elemento('tr');
        for (const titulo of colunas) {
            const th = elemento('th', titulo);
            th.scope = 'col';
            linha.append(th);
        }
        cabecalho.append(linha);
        for (const valores of registros) {
            const tr = elemento('tr');
            for (const valor of valores) tr.append(elemento('td', valor));
            corpo.append(tr);
        }
        t.append(cabecalho, corpo);
        caixa.append(t);
        pai.append(caixa);
    }
    function mostrarFonte(pai, fonte) {
        if (!fonte) return;
        const p = elemento('p', [fonte.fonte, fonte.versao, fonte.natureza].filter(Boolean).join(' · '), 'microcopy');
        if (fonte.url?.startsWith('https://')) {
            const a = elemento('a', 'Ver fonte', 'text-link');
            a.href = fonte.url;
            a.target = '_blank';
            a.rel = 'noopener noreferrer';
            p.append(document.createTextNode(' · '), a);
        }
        pai.append(p);
        if (fonte.ponto) {
            texto(pai, 'Ponto de referência ' + formatarNumero(fonte.ponto.lat, 4) + ', ' +
                formatarNumero(fonte.ponto.lon, 4) + (fonte.fuso ? ' · Dias em ' + fonte.fuso : ''));
        }
    }
    function medida(item) {
        if (item?.valor != null) return formatarNumero(item.valor, 2);
        return item?.original ? '— (' + item.original + ')' : '—';
    }
    if (dados.talhao) {
        const area = dados.talhao.area_ha == null ? '' : ' · Área aproximada de ' + formatarNumero(dados.talhao.area_ha, 3) + ' ha';
        texto(raiz, dados.talhao.nome + area);
    }
    if (dados.laudo_solo) {
        const laudo = dados.laudo_solo;
        const profundidade = laudo.profundidade_cm || [laudo.profundidade_inicio_cm, laudo.profundidade_fim_cm];
        const pai = secao('Amostra de solo informada');
        texto(pai, formatarData(laudo.data) + ' · ' + profundidade.join('–') + ' cm · Argila ' + laudo.argila_pct + '%');
    }
    if (dados.vistoria) {
        const pai = secao('Ficha de vistoria');
        for (const [campo, rotulo] of Object.entries({hipotese: 'Hipótese', proximo_passo: 'Próxima verificação ou ação', retorno: 'Revisita'})) {
            if (dados.vistoria[campo]) texto(pai, rotulo + ' · ' + dados.vistoria[campo]);
        }
    }
    if (casosTalhao) {
        const pai = secao('Safras registradas no mesmo talhão');
        texto(pai, 'Compara registros anteriores do dispositivo com cultura, época, fase e manejo compatíveis.');
        if (casosTalhao.casos?.length) {
            tabela(pai, ['Plantio anterior', 'Chuva na janela', 'Temperatura', 'Retorno informado'],
                casosTalhao.casos.map(c => [formatarData(c.plantio), formatarNumero(c.chuva_mm, 2) + ' mm',
                    formatarNumero(c.temp_media_c, 2) + ' °C', c.retorno]));
        } else texto(pai, 'A comparação exige pelo menos três safras anteriores com retorno registrado e clima comparável.');
    }
    if (!regional) return;
    if (regional.status !== 'disponivel') {
        texto(raiz, MENSAGENS[regional.status] || 'Contexto regional indisponível.');
        return;
    }
    const m = regional.municipio;
    texto(raiz, m.nome + ' · ' + m.uf + ' · IBGE ' + m.codigo +
        (m.versao_malha ? ' · Malha ' + m.versao_malha : ' · Município informado no cadastro'));

    const pam = secao('Histórico municipal · PAM');
    texto(pam, regional.pam.limitacao);
    if (!regional.pam.series.length) texto(pam, 'Sem série PAM carregada para esta cultura.');
    for (const serie of regional.pam.series) {
        mostrarFonte(pam, serie.fonte);
        tabela(pam, ['Ano', 'Recorte', 'Área colhida (ha)', 'Produção (t)', 'Rendimento (kg/ha)'],
            serie.registros.map(r => [r.ano, RECORTES[r.recorte], medida(r.medidas.area_colhida),
                medida(r.medidas.producao), medida(r.medidas.rendimento)]));
    }

    const zarc = secao('Janelas oficiais · ZARC');
    mostrarFonte(zarc, regional.zarc.fonte);
    if (regional.zarc.status === 'disponivel') {
        texto(zarc, regional.zarc.safra + ' · ' + regional.zarc.rotulo);
        if (regional.zarc.janelas.length) tabela(zarc, ['Início', 'Fim', 'Risco publicado'],
            regional.zarc.janelas.map(j => [j.inicio, j.fim, j.risco_pct + '%']));
        else texto(zarc, 'Nenhum decêndio indicado nessa combinação da publicação.');
        const portaria = elemento('a', 'Conferir a portaria no MAPA', 'text-link');
        portaria.href = regional.zarc.url_portarias;
        portaria.target = '_blank';
        portaria.rel = 'noopener noreferrer';
        zarc.append(portaria);
    } else texto(zarc, MENSAGENS[regional.zarc.status] || 'Consulta ZARC indisponível.');

    const clima = secao('Séries agroclimáticas regionais');
    if (!regional.clima.length) texto(clima, 'Sem série agroclimática carregada.');
    for (const serie of regional.clima) {
        mostrarFonte(clima, serie.fonte);
        if (!serie.janelas.length) {
            texto(clima, 'Sem observações anteriores à data de referência.');
            continue;
        }
        texto(clima, 'Último dia disponível ' + formatarData(serie.ultimo_dia) + ' · Defasagem de ' + serie.atraso_dias + ' dia(s).');
        tabela(clima, ['Janela', 'Dias com chuva registrada', 'Chuva (mm)', 'Temperatura média (°C)', 'Dias secos (< 1 mm)'],
            serie.janelas.map(j => [j.dias + ' dias', j.dias_chuva + '/' + j.dias,
                j.chuva_parcial_mm == null ? formatarNumero(j.chuva_mm, 2) : formatarNumero(j.chuva_parcial_mm, 2) + ' parcial',
                formatarNumero(j.temp_media_c, 2), formatarNumero(j.dias_secos)]));
        const analogos = serie.anos_analogos;
        if (analogos?.status === 'disponivel') {
            texto(clima, 'Anos agroclimáticos semelhantes · ' + analogos.amostras + ' janelas históricas completas. ' +
                'Diferença de chuva para a mediana histórica ' + formatarNumero(analogos.anomalias_mediana.chuva_mm, 2) + ' mm.');
            tabela(clima, ['Período até', 'Chuva (mm)', 'Temperatura (°C)', 'Distância padronizada'],
                analogos.casos.map(c => [formatarData(c.fim), formatarNumero(c.chuva_mm, 2),
                    formatarNumero(c.temp_media_c, 2), formatarNumero(c.distancia, 4)]));
        } else texto(clima, 'A comparação de anos exige a janela recente e pelo menos três janelas históricas completas.');
    }
    for (const v of regional.validacao_estacoes || []) {
        texto(clima, v.fonte_estacao.fonte + ' · ' + v.fonte_estacao.recorte +
            ' · Distância do ponto de modelo ' + formatarNumero(v.distancia_km) + ' km.');
        if (v.status === 'disponivel') texto(clima, v.dias_pareados + ' dias pareados · Viés de chuva ' +
            formatarNumero(v.vies_mm, 2) + ' mm/dia · Erro absoluto médio ' + formatarNumero(v.erro_absoluto_medio_mm, 2) + ' mm/dia.');
    }

    const solo = secao('Granulometria de referência · MapBiomas Solo');
    if (!regional.solo.length) texto(solo, 'Sem amostra regional do MapBiomas carregada.');
    for (const amostra of regional.solo) {
        mostrarFonte(solo, amostra.fonte);
        const fracoes = Object.entries(amostra.fracoes_pct).map(([k, v]) => k + ' ' + (v == null ? '—' : formatarNumero(v, 2) + '%'));
        texto(solo, amostra.profundidade_cm.join('–') + ' cm · Pixel de ' + amostra.resolucao_m + ' m · ' + fracoes.join(' · '));
    }

    const balanco = secao('Balanço hídrico regional estimado');
    const bh = regional.balanco_hidrico;
    mostrarFonte(balanco, bh.fonte);
    if (bh.status === 'estimativa') {
        texto(balanco, bh.limitacao + ' Distância até o ponto do modelo de ' + formatarNumero(bh.distancia_modelo_km) + ' km.');
        tabela(balanco, ['Dia', 'ET₀ (mm)', 'ETc (mm)', 'Armazenamento (mm)', 'Demanda não atendida (mm)'],
            bh.dias.map(d => [formatarData(d.data), formatarNumero(d.et0_mm, 2), formatarNumero(d.etc_mm, 2),
                formatarNumero(d.armazenamento_mm, 2), formatarNumero(d.demanda_nao_atendida_mm, 2)]));
    } else texto(balanco, MENSAGENS[bh.status] || 'Estimativa hídrica indisponível.');
}
