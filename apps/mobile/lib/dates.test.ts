import { formatShortDate, isToday, toIsoDate } from './dates';

describe('toIsoDate', () => {
  it('formata no padrão que a API espera', () => {
    expect(toIsoDate(new Date(2026, 7, 5))).toBe('2026-08-05');
  });

  it('preenche mês e dia com zero à esquerda', () => {
    expect(toIsoDate(new Date(2026, 0, 9))).toBe('2026-01-09');
  });

  it('usa o dia local, não o UTC', () => {
    // 23h do dia 5 em fuso negativo vira dia 6 em UTC. Usar toISOString()
    // jogaria o gasto da noite pro dia seguinte e sujaria o fechamento do mês.
    const lateNight = new Date(2026, 7, 5, 23, 30);
    expect(toIsoDate(lateNight)).toBe('2026-08-05');
  });

  it('vira o ano corretamente no último dia de dezembro', () => {
    expect(toIsoDate(new Date(2026, 11, 31))).toBe('2026-12-31');
  });
});

describe('isToday', () => {
  it('reconhece hoje independente da hora', () => {
    const now = new Date();
    const sameDayLate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59);
    expect(isToday(sameDayLate)).toBe(true);
  });

  it('rejeita outro dia', () => {
    expect(isToday(new Date(2020, 0, 1))).toBe(false);
  });
});

describe('formatShortDate', () => {
  it('mostra dia e mês na ordem brasileira', () => {
    expect(formatShortDate(new Date(2026, 7, 5))).toBe('05/08');
  });
});
