/**
 * Formatação dos insights. Fica separada da tela e sem import de client de API
 * porque é onde os casos de borda do contrato aparecem — `delta_pct` null,
 * estouro de teto contra meta não atingida — e isso merece teste.
 */

import { formatApiAmount } from './money';
import type { Delta, HealthBreakdownEntry } from './insights';

/**
 * Variação em texto.
 *
 * `delta_pct` vem **null** quando o mês anterior foi zero: o backend não inventa
 * "aumento de 100%" a partir de nada, e renderizar "null%" seria o erro óbvio
 * aqui. Nesse caso mostra só o valor.
 */
export function deltaText(delta: Delta): string {
  if (delta.direction === 'flat') return '—';

  const sign = delta.direction === 'up' ? '+' : '';
  const value = `${sign}${formatApiAmount(delta.delta)}`;

  return delta.delta_pct === null ? value : `${value} · ${sign}${delta.delta_pct}%`;
}

/**
 * O que está fora do lugar neste bucket, ou null quando está tudo certo.
 *
 * Teto e meta se leem ao contrário: em necessidades/desejos ficar abaixo é bom,
 * em poupança é ficar devendo. Tratar os dois como "abaixo = economia" era o
 * jeito mais fácil de a tela elogiar quem não guardou nada.
 */
export function overshoot(entry: Pick<HealthBreakdownEntry, 'kind' | 'spent' | 'target'>) {
  const spent = Number(entry.spent);
  const target = Number(entry.target);

  if (!Number.isFinite(spent) || !Number.isFinite(target)) return null;
  if (entry.kind === 'ceiling' && spent > target) return 'acima do teto';
  if (entry.kind === 'goal' && spent < target) return 'faltando';
  return null;
}

/** 'jul · jun · mai' para o rodapé da média. */
export function shortMonths(months: string[], nameOf: (month: string) => string): string {
  return months.map((month) => nameOf(month).slice(0, 3).toLowerCase()).join(' · ');
}
