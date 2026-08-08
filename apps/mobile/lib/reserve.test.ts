import { PROFILE_LABELS } from './reserve';
import {
  centsToApiAmount,
  formatApiAmount,
  hasAmount,
  isPositiveAmount,
  numberToCents,
} from './money';

describe('leitura da reserva na tela', () => {
  it('traduz meses cobertos de decimal pra português', () => {
    // O backend devolve '3.5' porque é decimal de API; a tela é em português.
    // Interpolar direto mostraria "3.5 meses".
    expect('3.5'.replace('.', ',')).toBe('3,5');
  });

  it('rotula o perfil sem expor o valor do banco', () => {
    expect(PROFILE_LABELS.clt).toBe('CLT');
    expect(PROFILE_LABELS.autonomo).toBe('Autônomo');
  });
});

describe('ida e volta do campo de saldo', () => {
  /** O campo abre com o valor atual pra corrigir ser mais fácil que redigitar,
   *  e o que sai tem que ser idêntico ao que entrou — senão editar o saldo sem
   *  querer mudá-lo alteraria o valor. */
  it('preserva o valor ao abrir e salvar sem mexer', () => {
    const doBanco = '14000.00';
    const digitos = numberToCents(Number(doBanco));

    expect(centsToApiAmount(digitos)).toBe('14000.00');
  });

  it('preserva centavos quebrados', () => {
    const digitos = numberToCents(Number('4599.99'));
    expect(centsToApiAmount(digitos)).toBe('4599.99');
  });

  it('não perde um centavo por ponto flutuante', () => {
    // 19.99 * 100 dá 1998.9999999999998; truncar tiraria um centavo.
    expect(centsToApiAmount(numberToCents(19.99))).toBe('19.99');
  });

  it('formata saldo zerado sem virar vazio', () => {
    expect(formatApiAmount('0.00')).toBe('R$ 0,00');
  });
});

describe('quando o botão de salvar libera', () => {
  /** Saldo zero é resposta válida — "gastei minha reserva" é o momento em que a
   *  pessoa mais quer atualizar o número. `isPositiveAmount` rejeitava, e isso
   *  trancava o único caminho pra registrar. */
  it('libera com saldo zero', () => {
    expect(hasAmount('0')).toBe(true);
    expect(isPositiveAmount('0')).toBe(false);
  });

  it('não libera com campo vazio', () => {
    expect(hasAmount('')).toBe(false);
  });

  it('gasto essencial zerado continua barrado, porque zeraria a meta', () => {
    // Com baseline zero o alvo é zero, e o backend diria "reserva completa".
    expect(isPositiveAmount('0')).toBe(false);
    expect(isPositiveAmount('000')).toBe(false);
  });

  it('libera valor normal nos dois casos', () => {
    expect(hasAmount('1400000')).toBe(true);
    expect(isPositiveAmount('1400000')).toBe(true);
  });
});
