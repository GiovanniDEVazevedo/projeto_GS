// Uma resposta HTTP 200 não confirma todos os itens. Somente a confirmação
// individual persistida pode mudar o estado local; os registros nunca são apagados.
const ESTADOS_SERVIDOR = new Set(['pendente', 'processando', 'ok', 'erro']);
export function criarSincronizador({storage, request}) {
    let executando = null;
    async function executar() {
        const registros = await storage.todos();
        const pendentes = registros.filter(r => !r.sincronizado && !['invalido', 'conflito'].includes(r.estado));
        for (let i = 0; i < pendentes.length; i += 50) {
            const lote = pendentes.slice(i, i + 50);
            const respostas = await request('/api/sync', {method: 'POST', body: JSON.stringify(lote.map(r => r.dados))});
            if (!Array.isArray(respostas)) throw new Error('Resposta de sincronização inválida.');
            for (const resposta of respostas) {
                if (!resposta || !lote.some(r => r.id === resposta.id)) continue;
                if (resposta.persistido === true && ESTADOS_SERVIDOR.has(resposta.status)) {
                    await storage.confirmar(resposta);
                } else if (['invalido', 'conflito'].includes(resposta.status)) {
                    await storage.confirmar({...resposta, persistido: false});
                }
            }
        }
        // Atualizar análises já aceitas, inclusive após reiniciar o navegador.
        const aceitos = (await storage.todos()).filter(r => r.sincronizado && ['pendente', 'processando'].includes(r.estado));
        for (const registro of aceitos) {
            try {
                const resposta = await request('/api/analises/' + encodeURIComponent(registro.id));
                if (resposta.id === registro.id && resposta.persistido === true && ESTADOS_SERVIDOR.has(resposta.status)) {
                    await storage.confirmar(resposta);
                }
            } catch (error) {
                // Cada item pode falhar independentemente; nunca excluir o histórico.
                if (error.status !== 404) throw error;
                // Banco restaurado/trocado: reenviar com o mesmo UUID é seguro.
                await storage.salvar({...registro, sincronizado: false, estado: 'pendente'});
            }
        }
    }
    return () => {
        if (!executando) executando = executar().finally(() => { executando = null; });
        return executando;
    };
}
