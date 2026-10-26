import test from 'node:test';
import assert from 'node:assert/strict';
import {criarSincronizador} from '../safrasmart/api/static/sync.js';

function fakeStorage(records) {
    const data = new Map(records.map(r => [r.id, structuredClone(r)]));
    return {
        data,
        async todos() { return [...data.values()].map(r => structuredClone(r)); },
        async salvar(r) { data.set(r.id, structuredClone(r)); },
        async confirmar(resposta) {
            const r = data.get(resposta.id);
            data.set(r.id, {...r, estado: resposta.status, sincronizado: resposta.persistido === true,
                resultado: resposta.resultado || r.resultado, erro: resposta.erro});
        },
    };
}
const record = id => ({id, dados: {id, cultura: 'soja'}, estado: 'pendente', sincronizado: false});

test('HTTP 200 parcial confirma apenas os UUIDs persistidos', async () => {
    const storage = fakeStorage([record('a'), record('b'), record('c')]);
    const sync = criarSincronizador({storage, request: async path => path === '/api/sync' ?
        [{id: 'a', status: 'ok', persistido: true, resultado: {sucesso: true}},
         {id: 'b', status: 'erro', persistido: false},
         {id: 'c', status: 'invalido', persistido: false, erro: 'cultura inválida'}] : null});
    await sync();
    assert.equal(storage.data.size, 3);
    assert.equal(storage.data.get('a').sincronizado, true);
    assert.equal(storage.data.get('b').sincronizado, false);
    assert.equal(storage.data.get('c').estado, 'invalido');
});

test('resposta perdida conserva a operação para reenvio', async () => {
    const storage = fakeStorage([record('a')]);
    const sync = criarSincronizador({storage, request: async () => { throw new Error('rede caiu'); }});
    await assert.rejects(sync());
    assert.equal(storage.data.get('a').sincronizado, false);
});

test('concorrência na mesma aba usa uma requisição de envio', async () => {
    const storage = fakeStorage([record('a')]);
    let chamadas = 0;
    const sync = criarSincronizador({storage, request: async () => {
        chamadas++;
        return [{id: 'a', status: 'ok', persistido: true}];
    }});
    await Promise.all([sync(), sync(), sync()]);
    assert.equal(chamadas, 1);
});

test('confirmação de UUID desconhecido ou status desconhecido não apaga registro', async () => {
    const storage = fakeStorage([record('a')]);
    await criarSincronizador({storage, request: async () => [
        {id: 'outro', persistido: true, status: 'ok'}, {id: 'a', persistido: true, status: 'surpresa'},
    ]})();
    assert.equal(storage.data.get('a').sincronizado, false);
});

test('registro criado durante sincronização é preservado', async () => {
    const storage = fakeStorage([record('a')]);
    await criarSincronizador({storage, request: async () => {
        await storage.salvar(record('novo'));
        return [{id: 'a', persistido: true, status: 'ok'}];
    }})();
    assert.equal(storage.data.get('novo').sincronizado, false);
    assert.equal(storage.data.size, 2);
});

test('estado aceito sobrevive até o resultado ser consultado', async () => {
    const storage = fakeStorage([{...record('a'), sincronizado: true, estado: 'processando'}]);
    await criarSincronizador({storage, request: async path => {
        assert.equal(path, '/api/analises/a');
        return {id: 'a', status: 'ok', persistido: true, resultado: {valor: 1}};
    }})();
    assert.deepEqual(storage.data.get('a').resultado, {valor: 1});
});

test('banco restaurado devolve 404: mesmo UUID volta à fila', async () => {
    const storage = fakeStorage([{...record('a'), sincronizado: true}]);
    await criarSincronizador({storage, request: async () => { const e = new Error(); e.status = 404; throw e; }})();
    assert.equal(storage.data.get('a').sincronizado, false);
});

test('falha ao gravar confirmação local conserva dados para nova tentativa', async () => {
    const storage = fakeStorage([record('a')]);
    storage.confirmar = async () => { throw new Error('quota'); };
    await assert.rejects(criarSincronizador({storage, request: async () => [{id: 'a', status: 'ok', persistido: true}]})());
    assert.equal(storage.data.get('a').sincronizado, false);
});

test('lotes respeitam limite de 50', async () => {
    const storage = fakeStorage(Array.from({length: 121}, (_, i) => record(String(i))));
    const tamanhos = [];
    await criarSincronizador({storage, request: async (_, opts) => {
        const lote = JSON.parse(opts.body);
        tamanhos.push(lote.length);
        return lote.map(r => ({id: r.id, status: 'ok', persistido: true}));
    }})();
    assert.deepEqual(tamanhos, [50, 50, 21]);
    assert.equal(storage.data.size, 121);
});

import {mensagemDaAnalise} from '../safrasmart/api/static/sync.js';

test('worker ausente não aparece como análise em andamento', () => {
    const texto = mensagemDaAnalise({...record('a'), sincronizado: true}, false);
    assert.match(texto, /processamento está temporariamente indisponível/);
    assert.match(texto, /está salvo/);
});

test('análise realmente em execução informa tentativa', () => {
    const texto = mensagemDaAnalise({...record('a'), sincronizado: true, estado: 'processando', tentativas: 2}, true);
    assert.match(texto, /tentativa 2 de 3/);
});

test('falha final não recebe mensagem de fila nem de nova tentativa', () => {
    const texto = mensagemDaAnalise({...record('a'), sincronizado: true, estado: 'erro', erro: 'Falhou após 3 tentativas.'}, false);
    assert.match(texto, /Falhou após 3 tentativas/);
    assert.doesNotMatch(texto, /indisponível|nova tentativa automaticamente/);
});

test('retry é distinguido de dados inválidos', () => {
    const texto = mensagemDaAnalise({...record('a'), sincronizado: true, erro: 'Falha temporária'}, true);
    assert.match(texto, /nova tentativa automaticamente/);
    assert.doesNotMatch(texto, /revise os dados/);
});
