import { api } from './api';
import type { Bucket } from './transactions';

export type CashFlow = {
  income: string;
  /** Consumo (necessidades + desejos), o "Saiu" — não inclui aporte. */
  expense: string;
  /** Aporte em poupança/investimento, o "Investido no mês". */
  saved: string;
  net: string;
};

export type CategorySlice = {
  category_id: number | null;
  name: string | null;
  bucket: Bucket | null;
  icon: string | null;
  amount: string;
  percentage: string;
};

export type BucketProgress = {
  bucket: Bucket;
  spent: string;
  /** null quando não há renda cadastrada pro mês. */
  target: string | null;
};

export type HealthScore = {
  score: number;
  label: 'saudavel' | 'atencao' | 'risco';
  breakdown: {
    bucket: Bucket;
    score: number;
    weight_pct: string;
    spent: string;
    target: string;
  }[];
};

export type DashboardSummary = {
  month: string;
  cash_flow: CashFlow;
  by_category: CategorySlice[];
  uncategorized_expense: string;
  buckets: BucketProgress[];
  health_score: HealthScore | null;
};

export function getDashboardSummary(month: string) {
  return api.get<DashboardSummary>(`/dashboard/summary?month=${month}`);
}

export const BUCKET_LABELS: Record<Bucket, string> = {
  necessidades: 'Necessidades',
  desejos: 'Desejos',
  poupanca: 'Poupança/metas',
};

export const HEALTH_LABELS: Record<HealthScore['label'], string> = {
  saudavel: 'Saudável',
  atencao: 'Atenção',
  risco: 'Risco',
};

export const HEALTH_COLORS: Record<HealthScore['label'], string> = {
  saudavel: '#5dcaa5',
  atencao: '#e8a33d',
  risco: '#e85c4a',
};
