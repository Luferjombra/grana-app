import {
  centsToApiAmount,
  extractDigits,
  formatApiAmount,
  formatCents,
  isPositiveAmount,
} from './money';

describe('extractDigits', () => {
  it('descarta tudo que não é dígito', () => {
    expect(extractDigits('R$ 1.234,56')).toBe('123456');
  });

  it('remove zeros à esquerda pra o campo não crescer sem parar', () => {
    expect(extractDigits('000123')).toBe('123');
  });

  it('mantém um zero sozinho', () => {
    expect(extractDigits('0')).toBe('0');
    expect(extractDigits('000')).toBe('0');
  });

  it('trata entrada vazia', () => {
    expect(extractDigits('')).toBe('');
    expect(extractDigits('abc')).toBe('');
  });

  it('limita o tamanho pra não estourar numeric(12,2)', () => {
    expect(extractDigits('9'.repeat(30))).toHaveLength(12);
  });
});

describe('formatCents', () => {
  it('preenche da direita pra esquerda, centavos primeiro', () => {
    expect(formatCents('8')).toBe('0,08');
    expect(formatCents('80')).toBe('0,80');
    expect(formatCents('800')).toBe('8,00');
  });

  it('separa milhar com ponto', () => {
    expect(formatCents('800000')).toBe('8.000,00');
    expect(formatCents('123456789')).toBe('1.234.567,89');
  });

  it('não separa milhar quando não precisa', () => {
    expect(formatCents('99999')).toBe('999,99');
  });

  it('vazio continua vazio, pra o placeholder aparecer', () => {
    expect(formatCents('')).toBe('');
  });
});

describe('centsToApiAmount', () => {
  it('converte pro decimal que a API espera', () => {
    expect(centsToApiAmount('800000')).toBe('8000.00');
    expect(centsToApiAmount('8')).toBe('0.08');
    expect(centsToApiAmount('800')).toBe('8.00');
  });

  it('vazio vira zero explícito', () => {
    expect(centsToApiAmount('')).toBe('0.00');
  });

  it('nunca usa ponto como separador de milhar', () => {
    // Mandar "8.000,00" pro backend viraria erro de conversão.
    expect(centsToApiAmount('123456789')).toBe('1234567.89');
  });
});

describe('isPositiveAmount', () => {
  it('reconhece valor maior que zero', () => {
    expect(isPositiveAmount('1')).toBe(true);
    expect(isPositiveAmount('000100')).toBe(true);
  });

  it('rejeita vazio e zero', () => {
    expect(isPositiveAmount('')).toBe(false);
    expect(isPositiveAmount('0')).toBe(false);
    expect(isPositiveAmount('000')).toBe(false);
  });
});

describe('formatApiAmount', () => {
  it('formata valor vindo da API', () => {
    expect(formatApiAmount('8000.00')).toBe('R$ 8.000,00');
    expect(formatApiAmount('1234567.89')).toBe('R$ 1.234.567,89');
  });

  it('tolera valor sem casas decimais', () => {
    expect(formatApiAmount('8000')).toBe('R$ 8.000,00');
  });
});
