import { api } from './api';

/** Sugestão de novo baseline, vinda da média real de necessidades. Vem null
 *  quando não há histórico ou quando a diferença é menor que 10% — abaixo disso
 *  seria ruído e o usuário aprenderia a ignorar o aviso. */
export type BaselineSuggestion = {
  amount: string;
  months_used: number;
  direction: 'up' | 'down';
};

export type Reserve = {
  profile: 'clt' | 'autonomo';
  /** Gasto essencial mensal — a base do alvo. */
  essential_expenses_baseline: string;
  /** 6 (clt) ou 12 (autônomo). Anda junto com o perfil. */
  months_multiplier: number;
  /** Informado pelo usuário: nada mais escreve este valor. */
  current_balance: string;
  target: string;
  missing: string;
  /** Trava em 100: passar da meta é ótimo, barra de 140% confunde. */
  progress_pct: number;
  /** Quantos meses de vida a reserva paga hoje, ex '3.5'. É o número que o
   *  usuário entende sem tradução. Null com baseline zerado. */
  months_covered: string | null;
  complete: boolean;
  suggested_baseline: BaselineSuggestion | null;
};

export type ReserveUpdate = {
  profile?: 'clt' | 'autonomo';
  essential_expenses_baseline?: string;
  current_balance?: string;
};

/** 404 quando o onboarding não foi concluído — a reserva nasce lá. A tela leva
 *  o usuário de volta em vez de mostrar erro. */
export function getReserve() {
  return api.get<Reserve>('/emergency-reserve');
}

export function updateReserve(data: ReserveUpdate) {
  return api.patch<Reserve>('/emergency-reserve', data);
}

export const PROFILE_LABELS: Record<Reserve['profile'], string> = {
  clt: 'CLT',
  autonomo: 'Autônomo',
};
