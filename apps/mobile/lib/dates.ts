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

/**
 * '2026-08-05' -> Date local, ou null se a string não for uma data.
 * `new Date('2026-08-05')` interpretaria como UTC e, em fuso negativo,
 * voltaria o dia 4 — por isso monta a data pelos componentes.
 */
export function parseIsoDate(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;

  const [, year, month, day] = match.map(Number);
  const parsed = new Date(year, month - 1, day);

  // Rejeita data que "existe" só por overflow, tipo 2026-02-31 virando março.
  if (parsed.getMonth() !== month - 1 || parsed.getDate() !== day) return null;
  return parsed;
}

/** '05/08', para a pill de data quando não é hoje. */
export function formatShortDate(date: Date): string {
  const [, month, day] = toIsoDate(date).split('-');
  return `${day}/${month}`;
}

/** 'YYYY-MM' do mês corrente, formato que a API usa nos filtros. */
export function currentMonth(today: Date = new Date()): string {
  return toIsoDate(today).slice(0, 7);
}

const MONTH_NAMES = [
  'janeiro',
  'fevereiro',
  'março',
  'abril',
  'maio',
  'junho',
  'julho',
  'agosto',
  'setembro',
  'outubro',
  'novembro',
  'dezembro',
];

/** '2026-08' -> 'Agosto', para o cabeçalho. */
export function monthName(month: string): string {
  const index = Number(month.split('-')[1]) - 1;
  const name = MONTH_NAMES[index];
  return name ? name.charAt(0).toUpperCase() + name.slice(1) : month;
}

/**
 * Cabeçalho de grupo na lista de atividade: 'Hoje', 'Ontem' ou '05/08'.
 * Compara strings ISO em vez de objetos Date pra não escorregar no fuso —
 * o backend devolve a data como 'YYYY-MM-DD', sem hora.
 */
export function dayGroupLabel(isoDate: string, today: Date = new Date()): string {
  if (isoDate === toIsoDate(today)) return 'Hoje';

  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  if (isoDate === toIsoDate(yesterday)) return 'Ontem';

  const [, month, day] = isoDate.split('-');
  return `${day}/${month}`;
}
