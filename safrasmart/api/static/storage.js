// As promessas de escrita só resolvem quando a transação foi confirmada.
let database;
export function abrirBanco() {
    if (!database) database = new Promise((resolve, reject) => {
        const request = indexedDB.open('safrasmart', 1);
        request.onupgradeneeded = () => {
            request.result.createObjectStore('registros', { keyPath: 'id' });
            request.result.createObjectStore('config');
        };
        request.onsuccess = () => {
            request.result.onversionchange = () => request.result.close();
            resolve(request.result);
        };
        request.onerror = () => reject(request.error);
        request.onblocked = () => reject(new Error('Feche as outras abas para atualizar o armazenamento.'));
    });
    return database;
}

async function transacao(loja, modo, operar) {
    const db = await abrirBanco();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(loja, modo);
        let valor;
        try {
            const req = operar(tx.objectStore(loja));
            req.onsuccess = () => { valor = req.result; };
        } catch (error) { tx.abort(); reject(error); }
        tx.oncomplete = () => resolve(valor);
        tx.onabort = () => reject(tx.error || new Error('Não foi possível salvar no dispositivo.'));
        tx.onerror = () => {}; // onabort informa o erro e impede confirmação indevida
    });
}

export const todos = () => transacao('registros', 'readonly', store => store.getAll());
export const obter = id => transacao('registros', 'readonly', store => store.get(id));
export const salvar = registro => transacao('registros', 'readwrite', store => store.put(registro));
export const config = chave => transacao('config', 'readonly', store => store.get(chave));
export const salvarConfig = (chave, valor) => transacao('config', 'readwrite', store => store.put(valor, chave));

export async function tokenDispositivo() {
    const db = await abrirBanco();
    return new Promise((resolve, reject) => {
        const tx = db.transaction('config', 'readwrite');
        const store = tx.objectStore('config');
        const request = store.get('token');
        let token;
        request.onsuccess = () => {
            token = request.result;
            if (!token) {
                token = Array.from(crypto.getRandomValues(new Uint8Array(32)), n => n.toString(16).padStart(2, '0')).join('');
                store.put(token, 'token');
            }
        };
        tx.oncomplete = () => resolve(token);
        tx.onabort = () => reject(tx.error);
    });
}

export async function confirmar(resposta) {
    const db = await abrirBanco();
    return new Promise((resolve, reject) => {
        const tx = db.transaction('registros', 'readwrite');
        const store = tx.objectStore('registros');
        const req = store.get(resposta.id);
        req.onsuccess = () => {
            if (!req.result) return;
            store.put({ ...req.result, estado: resposta.status, sincronizado: resposta.persistido === true,
                resultado: resposta.resultado || req.result.resultado || null, erro: resposta.erro || null,
                atualizado_em: resposta.atualizado_em || new Date().toISOString() });
        };
        tx.oncomplete = () => resolve();
        tx.onabort = () => reject(tx.error || new Error('Falha ao confirmar resultado local.'));
    });
}

export async function migrarLegado() {
    const antiga = localStorage.getItem('fila_pendente');
    if (!antiga) return;
    const fila = JSON.parse(antiga);
    if (!Array.isArray(fila)) throw new Error('A fila antiga está inválida. Exporte os dados antes de continuar.');
    const db = await abrirBanco();
    await new Promise((resolve, reject) => {
        const tx = db.transaction(['registros', 'config'], 'readwrite');
        const configStore = tx.objectStore('config');
        const req = configStore.get('legado_migrado');
        req.onsuccess = () => {
            if (req.result) return;
            for (const entrada of fila) {
                const id = crypto.randomUUID();
                tx.objectStore('registros').put({id, dados: {...entrada, id}, estado: 'pendente',
                    sincronizado: false, criado_em: new Date().toISOString(), resultado: null});
            }
            configStore.put(true, 'legado_migrado');
        };
        tx.oncomplete = resolve;
        tx.onabort = () => reject(tx.error);
    });
    localStorage.removeItem('fila_pendente');
}
