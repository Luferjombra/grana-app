import { deltaText, overshoot, shortMonths } from './insights-format';
import { monthName } from './dates';
import type { Delta } from './insights';

function delta(over: Partial<Delta> = {}): Delta {
  return {
    current: '500.00',
    previous: '400.00',
    delta: '100.00',
    delta_pct: '25.0',
    direction: 'up',
    ...over,
  };
}

describe('deltaText', () => {
  it('mostra valor e percentual quando há os dois', () => {
    expect(deltaText(delta())).toBe('+R$ 100,00 · +25.0%');
  });

  it('não renderiza "null%" quando o mês anterior foi zero', () => {
    // O backend devolve delta_pct null de propósito: não inventa "aumento de
    // 100%" a partir de nada. Interpolar direto era o erro óbvio aqui.
    const text = deltaText(delta({ previous: '0.00', delta_pct: null }));

    expect(text).toBe('+R$ 100,00');
    expect(text).not.toContain('null');
  });

  it('não põe sinal em queda, porque o valor já vem negativo', () => {
    expect(deltaText(delta({ delta: '-80.00', delta_pct: '-20.0', direction: 'down' }))).toBe(
      '-R$ 80,00 · -20.0%',
    );
  });

  it('sem variação mostra um traço, não "R$ 0,00 · 0%"', () => {
    expect(deltaText(delta({ delta: '0.00', delta_pct: '0.0', direction: 'flat' }))).toBe('—');
  });
});

describe('overshoot', () => {
  it('acusa estouro de teto', () => {
    expect(overshoot({ kind: 'ceiling', spent: '2870.00', target: '2400.00' })).toBe(
      'acima do teto',
    );
  });

  it('não acusa nada quando o gasto está dentro do teto', () => {
    expect(overshoot({ kind: 'ceiling', spent: '3180.00', target: '4000.00' })).toBeNull();
  });

  it('acusa meta de poupança não atingida', () => {
    // Teto e meta se leem ao contrário. Tratar "abaixo" como economia nos dois
    // faria a tela elogiar quem não guardou nada.
    expect(overshoot({ kind: 'goal', spent: '320.00', target: '1600.00' })).toBe('faltando');
  });

  it('não acusa nada quando a meta de poupança foi batida', () => {
    expect(overshoot({ kind: 'goal', spent: '1700.00', target: '1600.00' })).toBeNull();
  });

  it('trata teto e meta exatamente no alvo como em ordem', () => {
    expect(overshoot({ kind: 'ceiling', spent: '100.00', target: '100.00' })).toBeNull();
    expect(overshoot({ kind: 'goal', spent: '100.00', target: '100.00' })).toBeNull();
  });

  it('não quebra com valor ilegível', () => {
    expect(overshoot({ kind: 'ceiling', spent: 'x', target: '100.00' })).toBeNull();
  });
});

describe('shortMonths', () => {
  it('abrevia os meses usados na média', () => {
    expect(shortMonths(['2026-07', '2026-06', '2026-05'], monthName)).toBe('jul · jun · mai');
  });

  it('devolve string vazia sem meses', () => {
    expect(shortMonths([], monthName)).toBe('');
  });
});
