/**
 * Lógica da bandeja de import (specs/11, variante C do
 * `prototipo/13-import-variantes.html`).
 *
 * Fica separada da tela e sem import de client de API porque é aqui que a
 * contabilidade mora, e ela é fácil de quebrar: a primeira versão do protótipo
 * deixava `resolvidos + adiados < total` com o import liberado, e um lançamento
 * evaporava em silêncio. A invariante está coberta por teste.
 *
 * O modelo é de **unidades**, não de grupos: tirar um item de um grupo mal
 * agrupado ("BOLETO" junta energia, escola e plano de saúde) não descarta o
 * lançamento — ele vira uma unidade solta que exige a própria decisão.
 */

import type { ImportGroup, ImportItem, ImportConfirmRow } from './imports';

/** Bandeja "decidir depois": destino, não categoria. O lançamento fica de fora
 *  do import e volta numa segunda passada, em vez de travar o mês inteiro. */
export const DEFER = '__defer__';

export type Destination = number | typeof DEFER;

/** id da unidade -> destino escolhido. Unidade sem entrada aqui está órfã. */
export type Assignment = Record<string, Destination>;

/** Itens tirados de cada grupo, por índice do grupo no preview. */
export type Removed = Record<number, number[]>;

export type Unit = {
  id: string;
  label: string;
  /** Quantos lançamentos esta unidade representa. */
  count: number;
  items: ImportItem[];
  /** Índice de cada item de `items` no grupo **original**, na mesma ordem.
   *
   *  O "✕" precisa disto: casar o item por (data, valor, descrição) parecia
   *  suficiente, mas num grupo com dois lançamentos idênticos — dois cafés de
   *  R$ 10 no mesmo dia, coisa comum — a busca acha sempre o primeiro, e o
   *  segundo "✕" não fazia nada em silêncio. */
  itemIndexes: number[];
  /** Falso em unidade só de entrada: só despesa exige categoria. */
  needsCategory: boolean;
  /** Verdadeiro quando veio de um "✕" — item tirado do grupo. */
  isLoose: boolean;
  groupIndex: number;
  /** Índice do item dentro do grupo original; só em unidade solta. */
  itemIndex?: number;
  /** Grupo cuja chave é vazia já vem com um item só: o backend não agrupa
   *  lançamento sem descrição, então não faz sentido oferecer "✕" nele. */
  canSplit: boolean;
  /** Todos os itens já estão no banco (OFX, confirmado pelo FITID). A tela pode
   *  esconder, e nada disso é reenviado no confirm. */
  alreadyImported: boolean;
};

/**
 * Já está no banco, com certeza.
 *
 * Exige `external_id`: no OFX o FITID é id do banco, então duplicata é fato e o
 * backend bloqueia por índice único. No CSV não há id, e `likely_duplicate` é um
 * palpite por data+valor+descrição — dois cafés iguais no mesmo dia são
 * legítimos, e tratar palpite como fato descartaria um gasto real em silêncio
 * (specs/11).
 */
function alreadyImported(items: ImportItem[]): boolean {
  return items.length > 0 && items.every((item) => !!item.external_id && item.likely_duplicate);
}

function needsCategory(items: ImportItem[]): boolean {
  // Já importado não pede nada: a transação existe e tem categoria no banco.
  // Sem isto, a segunda passada (reimportar o arquivo pelos adiados) travaria o
  // botão exigindo categoria de lançamento que já entrou.
  if (alreadyImported(items)) return false;
  return items.some((item) => item.type === 'expense');
}

export function buildUnits(groups: ImportGroup[], removed: Removed = {}): Unit[] {
  const units: Unit[] = [];

  groups.forEach((group, groupIndex) => {
    const out = removed[groupIndex] ?? [];
    const keptIndexes = group.items
      .map((_, index) => index)
      .filter((index) => !out.includes(index));
    const kept = keptIndexes.map((index) => group.items[index]);

    if (kept.length > 0) {
      units.push({
        id: `g${groupIndex}`,
        label: group.label,
        count: kept.length,
        items: kept,
        itemIndexes: keptIndexes,
        needsCategory: needsCategory(kept),
        isLoose: false,
        groupIndex,
        canSplit: kept.length > 1,
        alreadyImported: alreadyImported(kept),
      });
    }

    // Ordem numérica explícita: `sort()` sem comparador ordenaria [1, 10, 2].
    [...out]
      .sort((a, b) => a - b)
      .forEach((itemIndex) => {
        const item = group.items[itemIndex];
        if (!item) return;
        units.push({
          id: `s${groupIndex}_${itemIndex}`,
          label: item.description || 'Lançamento sem descrição',
          count: 1,
          items: [item],
          itemIndexes: [itemIndex],
          needsCategory: needsCategory([item]),
          isLoose: true,
          groupIndex,
          itemIndex,
          canSplit: false,
          alreadyImported: alreadyImported([item]),
        });
      });
  });

  return units;
}

/** Unidade resolvida: entrada não pede categoria e já entra; despesa precisa de
 *  uma categoria de verdade. */
export function isSettled(unit: Unit, assignment: Assignment): boolean {
  if (!unit.needsCategory) return true;
  const destination = assignment[unit.id];
  return typeof destination === 'number';
}

export function isDeferred(unit: Unit, assignment: Assignment): boolean {
  return unit.needsCategory && assignment[unit.id] === DEFER;
}

/** Unidade sem destino algum. É o que trava o import. */
export function orphans(units: Unit[], assignment: Assignment): Unit[] {
  return units.filter((unit) => unit.needsCategory && assignment[unit.id] === undefined);
}

function sumWhere(units: Unit[], test: (unit: Unit) => boolean): number {
  return units.reduce((sum, unit) => sum + (test(unit) ? unit.count : 0), 0);
}

export function resolvedCount(units: Unit[], assignment: Assignment): number {
  return sumWhere(units, (unit) => isSettled(unit, assignment));
}

export function deferredCount(units: Unit[], assignment: Assignment): number {
  return sumWhere(units, (unit) => isDeferred(unit, assignment));
}

export function totalCount(units: Unit[]): number {
  return sumWhere(units, () => true);
}

/** Atribui um destino a várias unidades de uma vez — o gesto da bandeja. */
export function assignMany(
  assignment: Assignment,
  ids: string[],
  destination: Destination,
): Assignment {
  const next = { ...assignment };
  ids.forEach((id) => {
    next[id] = destination;
  });
  return next;
}

/** Tira um item do grupo: ele passa a exigir decisão própria. */
export function removeItem(removed: Removed, groupIndex: number, itemIndex: number): Removed {
  const current = removed[groupIndex] ?? [];
  if (current.includes(itemIndex)) return removed;
  return { ...removed, [groupIndex]: [...current, itemIndex] };
}

/**
 * Devolve o item ao grupo. Sem isto o "✕" seria irreversível e um toque errado
 * só se desfaria reiniciando o import.
 *
 * Limpa também o destino da unidade solta, senão ele ficaria pendurado numa
 * unidade que deixou de existir e voltaria a valer se o item saísse de novo.
 */
export function restoreItem(
  removed: Removed,
  assignment: Assignment,
  groupIndex: number,
  itemIndex: number,
): { removed: Removed; assignment: Assignment } {
  const current = removed[groupIndex] ?? [];
  const nextRemoved = { ...removed, [groupIndex]: current.filter((i) => i !== itemIndex) };

  const nextAssignment = { ...assignment };
  delete nextAssignment[`s${groupIndex}_${itemIndex}`];

  return { removed: nextRemoved, assignment: nextAssignment };
}

/**
 * Linhas a enviar no confirm.
 *
 * O adiado simplesmente **não entra** — é assim que a bandeja funciona sem
 * precisar de backend: o servidor só recebe o que foi confirmado (specs/11).
 *
 * Dentro de uma unidade mista, só a despesa leva categoria; entrada vai com
 * null, porque categoria de receita é opcional e a regra 50-30-20 não a usa.
 */
export function toConfirmRows(units: Unit[], assignment: Assignment): ImportConfirmRow[] {
  const rows: ImportConfirmRow[] = [];

  units.forEach((unit) => {
    if (isDeferred(unit, assignment)) return;
    if (!isSettled(unit, assignment)) return;
    // Já está no banco: o backend descartaria pelo FITID, mas mandar de volta
    // gastaria payload e faria `skipped` contar coisa que nunca foi escolhida.
    if (unit.alreadyImported) return;

    const destination = assignment[unit.id];
    const categoryId = typeof destination === 'number' ? destination : null;

    unit.items.forEach((item) => {
      rows.push({
        amount: item.amount,
        type: item.type,
        occurred_at: item.occurred_at,
        description: item.description || null,
        category_id: item.type === 'expense' ? categoryId : null,
        external_id: item.external_id,
      });
    });
  });

  return rows;
}

/** Destinos iniciais vindos da sugestão do backend (regra aprendida ou
 *  palavra-chave). O usuário só toca no que sobrou. */
export function initialAssignment(groups: ImportGroup[]): Assignment {
  const assignment: Assignment = {};
  groups.forEach((group, index) => {
    if (group.suggested_category_id !== null && group.needs_category) {
      assignment[`g${index}`] = group.suggested_category_id;
    }
  });
  return assignment;
}
