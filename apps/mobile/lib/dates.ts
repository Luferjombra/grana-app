/** Helpers puros de data — sem import de client de API, pra poderem ser
 *  usados e testados sem depender de configuração de ambiente. */

/**
 * 'YYYY-MM-DD' no fuso local. Usar toISOString() converteria pra UTC e
 * jogaria o gasto da noite pro dia seguinte, sujando o fechamento do mês.
 */
export function toIsoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

export function isToday(date: Date): boolean {
  return toIsoDate(date) === toIsoDate(new Date());
}

/** '05/08', para a pill de data quando não é hoje. */
export function formatShortDate(date: Date): string {
  const [, month, day] = toIsoDate(date).split('-');
  return `${day}/${month}`;
}
