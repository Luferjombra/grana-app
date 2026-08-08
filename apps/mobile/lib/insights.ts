import { api } from './api';
import type { Bucket, Category } from './transactions';

/** Variação entre dois períodos. `delta_pct` é **null** quando o período
 *  anterior foi zero: dividir por zero não tem resposta, e o backend não
 *  inventa "100%" a partir de nada. A tela precisa tratar. */
export type Delta = {
  current: string;
  previous: string;
  delta: string;
  delta_pct: string | null;
  direction: 'up' | 'down' | 'flat';
};

export type MonthOverMonth = {
  month: string;
  previous_month: string;
  /** Mês de referência ainda em curso. Quando true, os dois meses foram
   *  cortados em `comparable_days` — a tela **tem** que dizer isso, senão
   *  mostra economia que não existe. */
  partial: boolean;
  comparable_days: number | null;
  total: Delta;
  by_bucket: (Delta & { bucket: Bucket; label: string })[];
  /** Já vem ordenado por variação em reais. Não reordenar por percentual: 200%
   *  num gasto de R$ 3 não é notícia. */
  by_category: (Delta & { category_id: number | null; name: string })[];
};

export type Subscription = {
  merchant_key: string;
  label: string;
  amount: string;
  months_seen: number;
  last_seen: string;
  cadence: string;
  category: { id: number | null; name: string | null } | null;
  /** Falso quando parou de aparecer. Fica fora do `monthly_total`. */
  active: boolean;
};

export type Subscriptions = {
  months_analyzed: number;
  items: Subscription[];
  /** Só das ativas — incluir cancelada inflaria o custo fixo. */
  monthly_total: string;
};

export type TopTransaction = {
  id: number;
  occurred_at: string;
  /** Null quando o extrato veio sem descrição. A tela precisa de rótulo. */
  merchant: string | null;
  amount: string;
  category: Pick<Category, 'id' | 'name' | 'bucket' | 'icon'> | null;
};

export type TopTransactions = {
  month: string;
  items: TopTransaction[];
  /** Aporte em poupança que ficou fora da lista, dito em voz alta em vez de
   *  desaparecer: um aporte grande seria o "maior gasto" sem ser gasto. */
  excluded_savings: string;
};

export type ThreeMonthAverage = {
  months_used: string[];
  /** Null quando não há nenhum mês fechado com gasto. */
  average_total: string | null;
  by_bucket: { bucket: Bucket; label: string; average: string }[];
  current_month: { month: string; spent: string; partial: boolean } | null;
};

export type HealthBreakdownEntry = {
  bucket: Bucket;
  label: string;
  score: number;
  weight_pct: string;
  spent: string;
  target: string;
  /** `ceiling` em necessidades/desejos (estar abaixo é bom), `goal` em poupança
   *  (estar abaixo é ficar devendo). */
  kind: 'ceiling' | 'goal';
};

export type HealthBreakdown = {
  month: string;
  /** Null sem renda no mês — sem teto não há aderência a medir. */
  score: number | null;
  label: 'saudavel' | 'atencao' | 'risco' | null;
  reason: 'sem_renda' | null;
  breakdown: HealthBreakdownEntry[];
  /** Despesa sem categoria não pontua nem pune, então a nota ignora esse valor
   *  e o usuário precisa saber. */
  uncategorized_expense: string;
};

const monthQuery = (month?: string) => (month ? `?month=${month}` : '');

export const getMonthOverMonth = (month?: string) =>
  api.get<MonthOverMonth>(`/insights/month-over-month${monthQuery(month)}`);

export const getSubscriptions = () => api.get<Subscriptions>('/insights/recurring-subscriptions');

export const getTopTransactions = (month?: string, limit = 5) =>
  api.get<TopTransactions>(
    `/insights/top-transactions${monthQuery(month)}${month ? '&' : '?'}limit=${limit}`,
  );

export const getThreeMonthAverage = () =>
  api.get<ThreeMonthAverage>('/insights/three-month-average');

export const getHealthBreakdown = (month?: string) =>
  api.get<HealthBreakdown>(`/insights/health-score-breakdown${monthQuery(month)}`);
