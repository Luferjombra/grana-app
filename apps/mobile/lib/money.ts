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

/** '8000.00' -> 'R$ 8.000,00', para exibir valores vindos da API. */
export function formatApiAmount(amount: string): string {
  const [whole = '0', cents = '00'] = amount.split('.');
  const withThousands = whole.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return `R$ ${withThousands},${cents.padEnd(2, '0').slice(0, 2)}`;
}
