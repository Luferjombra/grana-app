const MAX_DIGITS = 12;

/**
 * Campo de moeda no padrão dos apps de banco: o usuário digita só dígitos e o
 * valor preenche da direita pra esquerda (centavos primeiro). O estado guarda
 * os centavos como string de dígitos, nunca um float — o contrato da API pede
 * decimal em string justamente pra não acumular erro de arredondamento.
 */
export function extractDigits(input: string): string {
  const digits = input.replace(/\D/g, '').slice(0, MAX_DIGITS);
  // Zeros à esquerda não mudam o valor e fariam o campo crescer sem parar.
  return digits.replace(/^0+(?=\d)/, '');
}

/** '800000' -> '8.000,00' (vazio -> ''), para exibir no campo. */
export function formatCents(digits: string): string {
  if (!digits) return '';

  const padded = digits.padStart(3, '0');
  const cents = padded.slice(-2);
  const whole = padded.slice(0, -2);
  const withThousands = whole.replace(/\B(?=(\d{3})+(?!\d))/g, '.');

  return `${withThousands},${cents}`;
}

/** '800000' -> '8000.00', formato que a API espera. */
export function centsToApiAmount(digits: string): string {
  if (!digits) return '0.00';

  const padded = digits.padStart(3, '0');
  return `${padded.slice(0, -2)}.${padded.slice(-2)}`;
}

export function isPositiveAmount(digits: string): boolean {
  return /[1-9]/.test(digits);
}

/**
 * 42.5 -> '4250', para preencher o campo de moeda com o valor lido pelo OCR.
 *
 * Arredonda de propósito: `19.99 * 100` dá 1998.9999999999998 em ponto
 * flutuante, e truncar viraria R$ 19,98 — um centavo a menos que o recibo.
 */
export function numberToCents(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return '';
  return String(Math.round(value * 100));
}

/**
 * Soma valores decimais da API e devolve outro decimal: ['10.50','0.02'] ->
 * '10.52'.
 *
 * Converte para centavos **pela string**, sem passar por float em momento
 * nenhum. `Number('0.1') + Number('0.2')` dá 0.30000000000000004, e a regra do
 * projeto é que dinheiro nunca vira float (specs/09).
 *
 * Existe porque o total que o backend manda por grupo deixa de valer quando o
 * usuário tira um item do grupo, e aí a tela precisa recalcular.
 */
export function sumApiAmounts(amounts: string[]): string {
  const cents = amounts.reduce((total, amount) => {
    const negative = amount.trimStart().startsWith('-');
    const [whole = '0', decimals = ''] = amount.replace('-', '').split('.');
    const value = Number(`${whole || '0'}${decimals.padEnd(2, '0').slice(0, 2)}`);
    if (!Number.isFinite(value)) return total;
    return total + (negative ? -value : value);
  }, 0);

  const sign = cents < 0 ? '-' : '';
  const absolute = String(Math.abs(cents)).padStart(3, '0');
  return `${sign}${absolute.slice(0, -2)}.${absolute.slice(-2)}`;
}

/** '8000.00' -> 'R$ 8.000,00', para exibir valores vindos da API. */
export function formatApiAmount(amount: string): string {
  const [whole = '0', cents = '00'] = amount.split('.');
  const withThousands = whole.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return `R$ ${withThousands},${cents.padEnd(2, '0').slice(0, 2)}`;
}
