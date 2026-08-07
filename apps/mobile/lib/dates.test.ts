import {
  currentMonth,
  dayGroupLabel,
  formatShortDate,
  isToday,
  monthName,
  toIsoDate,
} from './dates';

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

describe('currentMonth', () => {
  it('devolve YYYY-MM, o formato do filtro da API', () => {
    expect(currentMonth(new Date(2026, 7, 15))).toBe('2026-08');
  });

  it('usa o mês local mesmo no último dia à noite', () => {
    expect(currentMonth(new Date(2026, 7, 31, 23, 30))).toBe('2026-08');
  });
});

describe('monthName', () => {
  it('traduz o mês pro cabeçalho', () => {
    expect(monthName('2026-08')).toBe('Agosto');
    expect(monthName('2026-01')).toBe('Janeiro');
    expect(monthName('2026-12')).toBe('Dezembro');
  });

  it('devolve a entrada quando o mês não faz sentido, sem quebrar a tela', () => {
    expect(monthName('2026-13')).toBe('2026-13');
    expect(monthName('lixo')).toBe('lixo');
  });
});

describe('dayGroupLabel', () => {
  const today = new Date(2026, 7, 5);

  it('reconhece hoje e ontem', () => {
    expect(dayGroupLabel('2026-08-05', today)).toBe('Hoje');
    expect(dayGroupLabel('2026-08-04', today)).toBe('Ontem');
  });

  it('mostra dia/mês nos demais', () => {
    expect(dayGroupLabel('2026-07-28', today)).toBe('28/07');
  });

  it('acha o ontem certo virando o mês', () => {
    expect(dayGroupLabel('2026-07-31', new Date(2026, 7, 1))).toBe('Ontem');
  });

  it('acha o ontem certo virando o ano', () => {
    expect(dayGroupLabel('2025-12-31', new Date(2026, 0, 1))).toBe('Ontem');
  });
});
