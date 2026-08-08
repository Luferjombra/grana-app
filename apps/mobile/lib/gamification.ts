import { api } from './api';

export type XpSource = {
  source: 'habito' | 'resultado';
  label: string;
  xp: number;
  detail: string;
};

export type Progress = {
  month: string;
  level: number;
  total_xp: number;
  xp_into_level: number;
  xp_per_level: number;
  /** Dias em que o app foi usado, não streak: sem quebra e sem punição.
   *  Registrar 30 lançamentos num dia conta como 1 — é o que impede o app de
   *  premiar quem gasta mais. */
  active_days: number;
  breakdown: XpSource[];
  result_xp_available: number;
  month_in_progress: boolean;
};

export type Achievement = {
  code: string;
  name: string;
  description: string;
  unlocked: boolean;
};

export type Achievements = {
  items: Achievement[];
  unlocked_count: number;
  total: number;
};

export type Roundup = {
  month: string;
  /** Troco guardado que ainda não foi transferido. */
  accumulated: string;
  transferred: string;
  eligible_transactions: number;
  /** Sempre false nesta fase: transferência é manual, porque automação real
   *  dependeria de ITP via Open Finance, que está adiado. */
  automatic: boolean;
};

export const getProgress = () => api.get<Progress>('/gamification/progress');
export const getAchievements = () => api.get<Achievements>('/gamification/achievements');
export const getRoundup = () => api.get<Roundup>('/roundup');
export const transferRoundup = () =>
  api.post<{ transferred: string; count: number }>('/roundup/transfer', {});
