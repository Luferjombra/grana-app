import {
  DEFER,
  assignMany,
  buildUnits,
  deferredCount,
  initialAssignment,
  orphans,
  removeItem,
  resolvedCount,
  restoreItem,
  toConfirmRows,
  totalCount,
  type Assignment,
} from './import-tray';
import type { ImportGroup, ImportItem } from './imports';

function item(over: Partial<ImportItem> = {}): ImportItem {
  return {
    occurred_at: '2024-12-05',
    amount: '10.00',
    type: 'expense',
    description: 'LOJA',
    external_id: null,
    likely_duplicate: false,
    category_id: null,
    ...over,
  };
}

function group(over: Partial<ImportGroup> = {}): ImportGroup {
  const items = over.items ?? [item()];
  return {
    merchant_key: 'LOJA',
    label: 'LOJA',
    suggested_category_id: null,
    needs_category: items.some((i) => i.type === 'expense'),
    count: items.length,
    total: '10.00',
    likely_duplicates: 0,
    ...over,
    items,
  };
}

/** O grupo "BOLETO" do extrato real: mesma chave, naturezas diferentes. */
const BOLETO = group({
  merchant_key: 'BOLETO',
  label: 'BOLETO',
  items: [
    item({ description: 'BOLETO ENERGIA', amount: '284.10' }),
    item({ description: 'BOLETO ESCOLA', amount: '890.00' }),
    item({ description: 'BOLETO SAUDE', amount: '512.40' }),
  ],
});

describe('buildUnits', () => {
  it('faz uma unidade por grupo quando nada foi tirado', () => {
    const units = buildUnits([BOLETO]);
    expect(units).toHaveLength(1);
    expect(units[0].count).toBe(3);
    expect(units[0].canSplit).toBe(true);
  });

  it('transforma item tirado em unidade própria, sem descartar o lançamento', () => {
    const units = buildUnits([BOLETO], { 0: [1] });

    expect(units).toHaveLength(2);
    expect(units[0].count).toBe(2);
    expect(units[1].isLoose).toBe(true);
    expect(units[1].label).toBe('BOLETO ESCOLA');
    // o total de lançamentos não muda ao tirar item do grupo
    expect(totalCount(units)).toBe(3);
  });

  it('não oferece divisão em grupo de um item só', () => {
    expect(buildUnits([group()])[0].canSplit).toBe(false);
  });

  it('some com o grupo quando todos os itens saíram, sem perder lançamento', () => {
    const units = buildUnits([BOLETO], { 0: [0, 1, 2] });

    expect(units).toHaveLength(3);
    expect(units.every((unit) => unit.isLoose)).toBe(true);
    expect(totalCount(units)).toBe(3);
  });

  it('ordena índices tirados numericamente', () => {
    // sort() sem comparador ordenaria [1, 10, 2]
    const grande = group({
      items: Array.from({ length: 12 }, (_, n) => item({ description: `L${n}` })),
    });
    const units = buildUnits([grande], { 0: [10, 2, 1] });

    expect(units.filter((u) => u.isLoose).map((u) => u.itemIndex)).toEqual([1, 2, 10]);
  });
});

describe('contabilidade', () => {
  const units = buildUnits([BOLETO]);

  it('unidade sem destino é órfã e não conta como resolvida', () => {
    expect(orphans(units, {})).toHaveLength(1);
    expect(resolvedCount(units, {})).toBe(0);
  });

  it('categoria resolve o grupo inteiro', () => {
    const assignment: Assignment = { g0: 7 };
    expect(resolvedCount(units, assignment)).toBe(3);
    expect(orphans(units, assignment)).toHaveLength(0);
  });

  it('adiar dá destino sem resolver: o lançamento fica de fora', () => {
    const assignment: Assignment = { g0: DEFER };

    expect(deferredCount(units, assignment)).toBe(3);
    expect(resolvedCount(units, assignment)).toBe(0);
    // adiado tem destino, então não trava o import
    expect(orphans(units, assignment)).toHaveLength(0);
  });

  it('entrada não pede categoria e já entra resolvida', () => {
    const salario = buildUnits([
      group({ items: [item({ type: 'income', amount: '8000.00', description: 'SALARIO' })] }),
    ]);

    expect(salario[0].needsCategory).toBe(false);
    expect(resolvedCount(salario, {})).toBe(1);
    expect(orphans(salario, {})).toHaveLength(0);
  });

  it('grupo misto pede categoria: basta uma despesa', () => {
    const misto = buildUnits([
      group({
        items: [item({ amount: '500.00' }), item({ type: 'income', amount: '300.00' })],
      }),
    ]);

    expect(misto[0].needsCategory).toBe(true);
    expect(orphans(misto, {})).toHaveLength(1);
  });
});

describe('invariante resolvidos + adiados + órfãos == total', () => {
  /** É o que a primeira versão do protótipo quebrava: tirar um item de um grupo
   *  adiado deixava a soma menor que o total, com o import liberado, e um
   *  lançamento evaporava em silêncio. */
  function checa(units: ReturnType<typeof buildUnits>, assignment: Assignment) {
    const orfaos = orphans(units, assignment).reduce((sum, unit) => sum + unit.count, 0);
    expect(resolvedCount(units, assignment) + deferredCount(units, assignment) + orfaos).toBe(
      totalCount(units),
    );
  }

  it('vale em cada passo, inclusive tirando item de grupo adiado', () => {
    let removed = {};
    let assignment: Assignment = {};

    checa(buildUnits([BOLETO], removed), assignment);

    assignment = assignMany(assignment, ['g0'], DEFER);
    checa(buildUnits([BOLETO], removed), assignment);

    // tira um item do grupo JÁ adiado — o caso que quebrava
    removed = removeItem(removed, 0, 1);
    checa(buildUnits([BOLETO], removed), assignment);
    expect(deferredCount(buildUnits([BOLETO], removed), assignment)).toBe(2);

    // o item solto exige a própria decisão
    expect(orphans(buildUnits([BOLETO], removed), assignment)).toHaveLength(1);

    assignment = assignMany(assignment, ['s0_1'], 5);
    checa(buildUnits([BOLETO], removed), assignment);
  });

  it('vale com tudo resolvido', () => {
    const removed = removeItem({}, 0, 0);
    const units = buildUnits([BOLETO], removed);
    const assignment = assignMany({}, ['g0', 's0_0'], 3);

    checa(units, assignment);
    expect(resolvedCount(units, assignment)).toBe(3);
  });
});

describe('restoreItem', () => {
  it('devolve o item ao grupo', () => {
    const removed = removeItem({}, 0, 1);
    const back = restoreItem(removed, {}, 0, 1);

    expect(buildUnits([BOLETO], back.removed)).toHaveLength(1);
  });

  it('limpa o destino da unidade solta que deixou de existir', () => {
    const removed = removeItem({}, 0, 1);
    const assignment = assignMany({}, ['s0_1'], 9);
    const back = restoreItem(removed, assignment, 0, 1);

    expect(back.assignment['s0_1']).toBeUndefined();
  });
});

describe('toConfirmRows', () => {
  it('não manda o adiado — é assim que a bandeja dispensa backend', () => {
    const units = buildUnits([BOLETO, group({ label: 'OUTRA' })]);
    const assignment = assignMany({ g0: DEFER }, ['g1'], 4);

    const rows = toConfirmRows(units, assignment);

    expect(rows).toHaveLength(1);
    expect(rows[0].category_id).toBe(4);
  });

  it('não manda órfão', () => {
    expect(toConfirmRows(buildUnits([BOLETO]), {})).toHaveLength(0);
  });

  it('em unidade mista, só a despesa leva categoria', () => {
    const units = buildUnits([
      group({ items: [item({ amount: '500.00' }), item({ type: 'income', amount: '300.00' })] }),
    ]);
    const rows = toConfirmRows(units, { g0: 6 });

    expect(rows.map((row) => row.category_id)).toEqual([6, null]);
  });

  it('manda entrada mesmo sem o usuário tocar nela', () => {
    const units = buildUnits([
      group({ items: [item({ type: 'income', amount: '8000.00', description: 'SALARIO' })] }),
    ]);

    expect(toConfirmRows(units, {})).toHaveLength(1);
  });

  it('descrição vazia vira null, não string vazia', () => {
    const units = buildUnits([group({ items: [item({ description: '' })] })]);

    expect(toConfirmRows(units, { g0: 1 })[0].description).toBeNull();
  });
});

describe('initialAssignment', () => {
  it('aproveita a sugestão do backend, seja regra aprendida ou palavra-chave', () => {
    const assignment = initialAssignment([
      group({ suggested_category_id: 2 }),
      group({ suggested_category_id: null }),
    ]);

    expect(assignment).toEqual({ g0: 2 });
  });

  it('ignora sugestão em grupo que não pede categoria', () => {
    const assignment = initialAssignment([
      group({
        suggested_category_id: 2,
        needs_category: false,
        items: [item({ type: 'income' })],
      }),
    ]);

    expect(assignment).toEqual({});
  });
});

describe('itemIndexes', () => {
  /** Casar o item por (data, valor, descrição) parecia suficiente, mas dois
   *  lançamentos idênticos no mesmo grupo são comuns — dois cafés de R$ 10 no
   *  mesmo dia — e a busca achava sempre o primeiro. */
  const IGUAIS = group({
    items: [
      item({ description: 'CAFE', amount: '10.00' }),
      item({ description: 'CAFE', amount: '10.00' }),
      item({ description: 'CAFE', amount: '10.00' }),
    ],
  });

  it('mapeia cada item exibido para o índice real no grupo', () => {
    expect(buildUnits([IGUAIS])[0].itemIndexes).toEqual([0, 1, 2]);
  });

  it('mantém o índice original depois de tirar um item do meio', () => {
    const units = buildUnits([IGUAIS], { 0: [1] });

    expect(units[0].itemIndexes).toEqual([0, 2]);
    expect(units[1].itemIndex).toBe(1);
  });

  it('permite tirar itens idênticos um a um, sem repetir índice', () => {
    let removed = removeItem({}, 0, 0);
    let units = buildUnits([IGUAIS], removed);

    // o segundo "✕" cai no índice 1, não de novo no 0
    removed = removeItem(removed, 0, units[0].itemIndexes[0]);
    units = buildUnits([IGUAIS], removed);

    expect(units.filter((u) => u.isLoose).map((u) => u.itemIndex)).toEqual([0, 1]);
    expect(totalCount(units)).toBe(3);
  });
});

describe('já importado (segunda passada)', () => {
  const ofxJaImportado = group({
    items: [item({ external_id: 'ofx:A1', likely_duplicate: true })],
  });

  it('não pede categoria: a transação já existe no banco', () => {
    const units = buildUnits([ofxJaImportado]);

    expect(units[0].alreadyImported).toBe(true);
    expect(units[0].needsCategory).toBe(false);
    // sem isto, reimportar o arquivo pelos adiados travaria o botão pedindo
    // categoria de lançamento que já entrou
    expect(orphans(units, {})).toHaveLength(0);
  });

  it('não é reenviado no confirm', () => {
    expect(toConfirmRows(buildUnits([ofxJaImportado]), {})).toHaveLength(0);
  });

  it('duplicata de CSV continua exigindo decisão', () => {
    // sem external_id, likely_duplicate é palpite por data+valor+descrição:
    // dois cafés iguais no mesmo dia são legítimos
    const csv = group({ items: [item({ external_id: null, likely_duplicate: true })] });
    const units = buildUnits([csv]);

    expect(units[0].alreadyImported).toBe(false);
    expect(orphans(units, {})).toHaveLength(1);
  });

  it('grupo com um item novo ainda pede categoria', () => {
    const misto = group({
      items: [
        item({ external_id: 'ofx:A1', likely_duplicate: true }),
        item({ external_id: 'ofx:A2', likely_duplicate: false }),
      ],
    });
    const units = buildUnits([misto]);

    expect(units[0].alreadyImported).toBe(false);
    expect(units[0].needsCategory).toBe(true);
  });

  it('item tirado de grupo já importado também não pede categoria', () => {
    const dois = group({
      items: [
        item({ external_id: 'ofx:A1', likely_duplicate: true }),
        item({ external_id: 'ofx:A2', likely_duplicate: true }),
      ],
    });
    const units = buildUnits([dois], { 0: [1] });

    expect(units.every((unit) => unit.alreadyImported)).toBe(true);
    expect(orphans(units, {})).toHaveLength(0);
  });
});
