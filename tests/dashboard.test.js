import test from 'node:test';
import assert from 'node:assert/strict';
import {visualDoIndice, formatarNumero, formatarData, amostrasNdvi} from '../safrasmart/api/static/dashboard.js';

test('zero é desfavorável; ausência ou nota inválida permanece sem dados', () => {
    assert.deepEqual(visualDoIndice({valor: 0}), {valor: 0, tom: 'bad', rotulo: 'Desfavorável'});
    for (const valor of [null, undefined, NaN, Infinity, -1, 11, '8', false]) {
        assert.deepEqual(visualDoIndice({valor}), {valor: null, tom: 'neutral', rotulo: 'Sem dados'});
    }
});

test('fronteiras de cor seguem as mesmas faixas do backend', () => {
    for (const [valor, tom] of [[4.9, 'bad'], [5, 'warning'], [6.9, 'warning'], [7, 'good'], [10, 'good']]) {
        assert.equal(visualDoIndice({valor}).tom, tom);
    }
});

test('números ausentes não viram zero nem usam notação inválida', () => {
    assert.equal(formatarNumero(null), '—');
    assert.equal(formatarNumero(NaN), '—');
    assert.equal(formatarNumero(0), '0');
    assert.equal(formatarNumero(0.753, 3), '0,753');
});

test('datas mantêm o dia civil e rejeitam datas normalizadas ou inválidas', () => {
    assert.match(formatarData('2026-01-01'), /01.*2026/);
    for (const valor of [undefined, null, '', '2026-02-30', '2026-13-01', '<script>']) assert.equal(formatarData(valor), '—');
});

test('NDVI mantém valores negativos reais, remove inválidos e preserva suas datas', () => {
    const r = amostrasNdvi({datas: ['2026-03-01', '2026-01-01', '2026-02-01', '2026-04-01', 'data'], ndvi: [.8, -.2, null, 2, .5]});
    assert.deepEqual(r, [{data: '2026-01-01', valor: -.2}, {data: '2026-03-01', valor: .8}]);
    assert.deepEqual(amostrasNdvi(null), []);
});
