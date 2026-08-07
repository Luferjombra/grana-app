import { api } from './api';

export type IncomeProfile = 'clt' | 'autonomo';

export type Profile = {
  full_name: string | null;
  income_profile: IncomeProfile | null;
  /** Renda vigente do mês, como string decimal — nunca float (specs/09). */
  current_income: string | null;
  onboarding_complete: boolean;
};

export function getProfile() {
  return api.get<Profile>('/profile');
}

export function completeOnboarding(incomeProfile: IncomeProfile, monthlyIncome: string) {
  return api.post<Profile>('/onboarding', {
    income_profile: incomeProfile,
    monthly_income: monthlyIncome,
  });
}
