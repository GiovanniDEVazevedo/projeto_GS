// O contorno fica disponível no dispositivo. O mapa base é uma camada opcional.
export function criarControleTalhoes({salvar, aoSelecionar}) {
    const $ = id => document.getElementById(id);
    const lista = new Map();
    const seletor = $('talhaoSelecionado');
    let atual = null;
    let mapa;
    let camada;
    let base;
    let pontos = [];
    let sessaoEditor = 0;

    function atualizarOpcoes() {
        seletor.replaceChildren(new Option('Usar apenas uma coordenada', ''));
        for (const item of lista.values()) seletor.add(new Option(item.propriedade + ' · ' + item.nome, item.id));
        seletor.value = atual?.id || '';
    }

    function selecionar(talhao, avisar = true) {
        atual = talhao || null;
        if (atual) lista.set(atual.id, atual);
        atualizarOpcoes();
        $('talhaoInfo').textContent = atual
            ? (atual.area_ha == null ? 'Contorno salvo no dispositivo.' : 'Área aproximada de ' +
                new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 3}).format(atual.area_ha) + ' ha.')
            : 'Escolha um talhão salvo ou desenhe o limite no mapa.';
        if (avisar) aoSelecionar(atual);
    }

    function renderizar() {
        camada.clearLayers();
        const latLngs = pontos.map(([lon, lat]) => [lat, lon]);
        const estilo = {color: '#16624e', weight: 3, interactive: false};
        if (pontos.length >= 3) window.L.polygon(latLngs, estilo).addTo(camada);
        else if (pontos.length > 1) window.L.polyline(latLngs, estilo).addTo(camada);
        for (const posicao of latLngs) window.L.circleMarker(posicao, {...estilo, radius: 4}).addTo(camada);
        $('talhaoPontos').textContent = pontos.length + ' vértice(s).';
        $('talhaoDesfazer').disabled = !pontos.length;
        $('talhaoGuardar').disabled = pontos.length < 3;
    }

    function adicionar(lat, lon, centralizar = false) {
        if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 85 || Math.abs(lon) > 180) {
            $('talhaoErro').textContent = 'Informe latitude e longitude válidas para o vértice.';
            return;
        }
        if (pontos.length >= 500) {
            $('talhaoErro').textContent = 'O limite é de 500 vértices.';
            return;
        }
        const par = [Number(lon.toFixed(7)), Number(lat.toFixed(7))];
        if (pontos.some(p => p[0] === par[0] && p[1] === par[1])) {
            $('talhaoErro').textContent = 'Esse vértice já foi registrado.';
            return;
        }
        $('talhaoErro').textContent = '';
        pontos.push(par);
        renderizar();
        if (centralizar) mapa.setView([lat, lon], Math.max(mapa.getZoom(), 16));
    }

    function abrir() {
        if (!window.L) {
            $('talhaoInfo').textContent = 'Recarregue a página para carregar o editor do mapa.';
            return;
        }
        pontos = [];
        sessaoEditor += 1;
        $('talhaoNome').value = '';
        $('talhaoErro').textContent = '';
        $('talhaoGpsVertice').disabled = false;
        $('verticeLat').value = '';
        $('verticeLon').value = '';
        $('talhaoModal').showModal();
        if (!mapa) {
            mapa = window.L.map('talhaoMapa', {maxZoom: 19, minZoom: 3, worldCopyJump: true});
            camada = window.L.layerGroup().addTo(mapa);
            mapa.on('click', ({latlng}) => adicionar(latlng.lat, latlng.wrap().lng));
        }
        const lat = $('lat').valueAsNumber;
        const lon = $('lon').valueAsNumber;
        const ponto = Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 85 && Math.abs(lon) <= 180;
        mapa.setView(ponto ? [lat, lon] : [-14, -52], ponto ? 16 : 4);
        mapa.invalidateSize();
        renderizar();
        $('talhaoNome').focus();
    }

    function alternarMapaBase() {
        if ($('talhaoMapaBase').checked) {
            if (!base) base = window.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19, referrerPolicy: 'origin',
                attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            });
            base.addTo(mapa);
        } else if (base) base.remove();
    }

    seletor.addEventListener('change', () => selecionar(lista.get(seletor.value)));
    $('talhaoNovo').addEventListener('click', abrir);
    $('talhaoFechar').addEventListener('click', () => $('talhaoModal').close());
    $('talhaoMapaBase').addEventListener('change', alternarMapaBase);
    $('talhaoDesfazer').addEventListener('click', () => { pontos.pop(); renderizar(); });
    $('talhaoAdicionarVertice').addEventListener('click', () =>
        adicionar($('verticeLat').valueAsNumber, $('verticeLon').valueAsNumber, true));
    $('talhaoGpsVertice').addEventListener('click', () => {
        if (!navigator.geolocation) {
            $('talhaoErro').textContent = 'GPS indisponível. Use o mapa ou informe as coordenadas.';
            return;
        }
        const sessao = sessaoEditor;
        $('talhaoGpsVertice').disabled = true;
        navigator.geolocation.getCurrentPosition(({coords}) => {
            if (sessao !== sessaoEditor || !$('talhaoModal').open) return;
            $('talhaoGpsVertice').disabled = false;
            if (coords.accuracy <= 30) adicionar(coords.latitude, coords.longitude, true);
            else $('talhaoErro').textContent = 'A precisão está em ' + Math.round(coords.accuracy) + ' m. Tente novamente ou ajuste pelo mapa.';
        }, () => {
            if (sessao !== sessaoEditor || !$('talhaoModal').open) return;
            $('talhaoGpsVertice').disabled = false;
            $('talhaoErro').textContent = 'A posição do GPS não foi obtida.';
        }, {enableHighAccuracy: true, timeout: 15000, maximumAge: 0});
    });
    $('talhaoGuardar').addEventListener('click', async () => {
        const nome = $('talhaoNome').value.trim();
        if (!nome) {
            $('talhaoErro').textContent = 'Informe o nome do talhão.';
            $('talhaoNome').focus();
            return;
        }
        if (pontos.length < 3) return;
        const n = pontos.length;
        const area = pontos.reduce((soma, [x, y], i) => {
            const [a, b] = pontos[(i + 1) % n];
            return soma + (x - pontos[0][0]) * (b - pontos[0][1]) - (a - pontos[0][0]) * (y - pontos[0][1]);
        }, 0);
        if (Math.abs(area) < 1e-12) {
            $('talhaoErro').textContent = 'Os vértices precisam delimitar uma área.';
            return;
        }
        const [lon, lat] = pontos.reduce(([x, y], p) => [x + p[0] / n, y + p[1] / n], [0, 0]);
        const talhao = {id: crypto.randomUUID(), nome, lat, lon,
            propriedade: $('propriedade').value.trim() || 'Minha propriedade',
            geometria: {type: 'Polygon', coordinates: [[...pontos, pontos[0]]]}};
        $('talhaoGuardar').disabled = true;
        try {
            await salvar(talhao);
            selecionar(talhao);
            $('talhaoModal').close();
        } catch {
            $('talhaoErro').textContent = 'O contorno não foi salvo. Mantenha o editor aberto e tente novamente.';
            $('talhaoGuardar').disabled = false;
        }
    });

    return {
        atualizar(talhoes) {
            for (const item of talhoes) lista.set(item.id, item);
            selecionar(lista.get(atual?.id), false);
        },
        selecionar,
        valor: () => atual,
    };
}
