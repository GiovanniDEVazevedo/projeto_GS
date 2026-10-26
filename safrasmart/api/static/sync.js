// Uma resposta HTTP 200 não confirma todos os itens. Somente a confirmação
// individual persistida pode mudar o estado local; os registros nunca são apagados.
const ESTADOS_SERVIDOR = new Set(['pendente', 'processando', 'ok', 'erro']);

export function mensagemDaAnalise(registro, processamentoDisponivel = null) {
    if (!registro.sincronizado) return registro.erro || 'Registro salvo neste dispositivo. Aguardando acesso ao servidor para enviar.';
    if (registro.estado === 'erro') return (registro.erro || 'Não foi possível concluir a análise.') + ' Seus dados foram preservados.';
    if (['pendente', 'processando'].includes(registro.estado) && processamentoDisponivel === false) {
        return 'Seu pedido foi recebido e está salvo. O processamento está temporariamente indisponível; continuará quando o serviço voltar.';
    }
    if (registro.estado === 'pendente' && registro.erro) return 'A tentativa anterior falhou. O servidor fará uma nova tentativa automaticamente; seus dados estão salvos.';
    if (registro.estado === 'processando') return `Análise em andamento (tentativa ${registro.tentativas || 1} de 3). Consultando os dados climáticos e, quando configurado, o satélite.`;
    return 'Recebido pelo servidor. Na fila para iniciar a análise.';
}

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
