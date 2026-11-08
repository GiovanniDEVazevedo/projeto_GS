export function criarConsultaRegional({request, config, salvarConfig}) {
    const $ = id => document.getElementById(id);
    let revisao = 0;
    const laudo = {data: 'laudoData', profundidade_inicio_cm: 'laudoInicio',
        profundidade_fim_cm: 'laudoFim', argila_pct: 'laudoArgila'};
    const hidrico = {fim: 'hidricoFim', cad_mm: 'hidricoCAD',
        armazenamento_inicial_mm: 'hidricoInicial', kc: 'hidricoKc'};
    const vistoria = {hipotese: 'vistoriaHipotese', proximo_passo: 'vistoriaPasso', retorno: 'vistoriaRetorno'};
    const coletar = campos => Object.fromEntries(Object.entries(campos).map(([chave, id]) => [chave, $(id).value.trim()]));
    const preencher = (campos, valores) => {
        for (const [chave, id] of Object.entries(campos)) $(id).value = valores?.[chave] ?? '';
    };

    function preencherOpcional(campos, nome, temComplemento = false) {
        const valores = coletar(campos);
        if (!temComplemento && !Object.values(valores).some(Boolean)) return null;
        if (Object.values(valores).some(v => v === '')) throw new Error('Complete os campos de ' + nome + '.');
        return valores;
    }

    function laminasDiarias() {
        const dias = {};
        for (const linha of $('hidricoIrrigacao').value.trim().split('\n').filter(Boolean)) {
            const partes = linha.trim().match(/^([0-9]{4}-[0-9]{2}-[0-9]{2})\s*=\s*([0-9]+(?:[.,][0-9]+)?)$/);
            if (!partes || Object.hasOwn(dias, partes[1])) throw new Error('Use uma linha AAAA-MM-DD=mm por dia de irrigação.');
            dias[partes[1]] = Number(partes[2].replace(',', '.'));
        }
        return dias;
    }

    function listarMunicipios(municipios) {
        $('municipiosIBGE').replaceChildren(...municipios.map(m => new Option(m.nome + ' · ' + m.uf, m.codigo)));
    }

    function limparZarc() {
        revisao += 1;
        $('zarcRegra').replaceChildren(new Option('Selecione após consultar', ''));
        $('zarcInfo').textContent = '';
    }

    async function carregarMunicipios(online) {
        if (online) {
            const municipios = await request('/api/regional/municipios');
            await salvarConfig('municipios-regionais', municipios);
            listarMunicipios(municipios);
        } else listarMunicipios((await config('municipios-regionais')) || []);
    }

    async function consultar() {
        limparZarc();
        const numero = revisao;
        const safra = $('zarcSafra').value.trim();
        if (!/^20[0-9]{2}\/20[0-9]{2}$/.test(safra)) {
            $('zarcInfo').textContent = 'Informe a safra no formato AAAA/AAAA.';
            return;
        }
        const parametros = new URLSearchParams({safra, cultura: $('cultura').value, irrigacao: $('irrigacao').value});
        const codigo = $('municipioIBGE').value.trim();
        if (codigo) parametros.set('municipio', codigo);
        else {
            if (!$('lat').value || !$('lon').value) {
                $('zarcInfo').textContent = 'Informe o município ou a localização da lavoura.';
                return;
            }
            parametros.set('lat', $('lat').value);
            parametros.set('lon', $('lon').value);
        }
        const chave = 'zarc:' + parametros.toString();
        $('zarcInfo').textContent = 'Consultando as publicações…';
        try {
            let resposta;
            if (navigator.onLine) {
                resposta = await request('/api/regional/zarc?' + parametros);
                await salvarConfig(chave, resposta);
            } else resposta = await config(chave);
            if (numero !== revisao) return;
            for (const opcao of resposta?.opcoes || []) $('zarcRegra').add(new Option(opcao.rotulo, opcao.id));
            $('zarcInfo').textContent = resposta?.opcoes?.length
                ? 'Escolha a combinação oficial de cultivar, solo e manejo que corresponde à lavoura.'
                : 'Nenhuma combinação disponível para esse recorte nas publicações carregadas.';
        } catch (erro) {
            if (numero === revisao) $('zarcInfo').textContent = erro.message || 'Consulta indisponível.';
        }
    }

    for (const id of ['municipioIBGE', 'zarcSafra', 'cultura', 'irrigacao', 'lat', 'lon']) {
        $(id).addEventListener('input', limparZarc);
    }
    $('zarcBuscar').addEventListener('click', consultar);

    return {
        limparZarc,
        carregarMunicipios,
        preencher(dados) {
            $('municipioIBGE').value = dados.municipio_ibge || '';
            $('zarcSafra').value = dados.zarc?.safra || '';
            limparZarc();
            if (dados.zarc) $('zarcRegra').add(new Option('Combinação salva', dados.zarc.regra, true, true));
            preencher(laudo, dados.laudo_solo);
            preencher(hidrico, dados.hidrico);
            preencher(vistoria, dados.vistoria);
            $('hidricoIrrigacao').value = Object.entries(dados.hidrico?.irrigacao_diaria_mm || {})
                .map(([dia, mm]) => dia + '=' + mm).join('\n');
        },
        dados() {
            const codigo = $('municipioIBGE').value.trim();
            const regra = $('zarcRegra').value;
            const complementos = {};
            if (codigo) complementos.municipio_ibge = codigo;
            if (regra) complementos.zarc = {safra: $('zarcSafra').value.trim(), regra};
            const amostra = preencherOpcional(laudo, 'laudo de solo');
            const irrigacao = laminasDiarias();
            const parametros = preencherOpcional(hidrico, 'balanço hídrico', Object.keys(irrigacao).length > 0);
            const ficha = coletar(vistoria);
            if (amostra) complementos.laudo_solo = amostra;
            if (parametros) complementos.hidrico = {...parametros, irrigacao_diaria_mm: irrigacao};
            if (Object.values(ficha).some(Boolean)) complementos.vistoria = ficha;
            return complementos;
        },
    };
}
