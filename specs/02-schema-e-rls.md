# Spec: aplicação do schema e políticas de RLS

Base: `schema.sql` (já produzido e aprovado, com households já modelados).

## Ordem de aplicação (migrations)
Numerar como migrations sequenciais, não rodar `schema.sql` como um único script para sempre — a partir daqui, toda mudança de schema é uma migration nova:

1. `0001_households.sql` — households, household_members
2. `0002_profiles_income.sql` — profiles, incomes, budget_rules
3. `0003_categories_budget.sql` — categories, budget_targets
4. `0004_accounts_transactions.sql` — accounts, transactions
5. `0005_receipts.sql` — receipts + FK de transactions
6. `0006_recurring_reserve.sql` — recurring_subscriptions, emergency_reserve
7. `0007_roundup.sql` — roundup_savings
8. `0008_gamification.sql` — user_progress, xp_events, achievements, user_achievements
9. `0009_notifications_etl.sql` — notifications, etl_runs

Ferramenta sugerida: `supabase migration new <nome>` via Supabase CLI, que já versiona e aplica em `infra/supabase/migrations/`.

## Políticas de RLS

Habilitar RLS em toda tabela (`alter table X enable row level security;`). Duas famílias de policy:

### Família A — escopo household
Tabelas: `budget_rules`, `categories`, `budget_targets`, `accounts`, `transactions`, `emergency_reserve`.

```sql
create policy "household members can access"
on <tabela>
for all
using (
  household_id in (
    select household_id from household_members where user_id = auth.uid()
  )
)
with check (
  household_id in (
    select household_id from household_members where user_id = auth.uid()
  )
);
```

### Família B — escopo individual
Tabelas: `profiles`, `incomes`, `receipts`, `recurring_subscriptions`, `roundup_savings`, `user_progress`, `xp_events`, `user_achievements`, `notifications`.

```sql
create policy "user owns row"
on <tabela>
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);
```

`profiles` usa `id` no lugar de `user_id` — ajustar a policy para `auth.uid() = id`.

### Tabelas sem RLS de usuário
- `categories` com `household_id is null` (categorias padrão do sistema) — policy adicional de leitura pública: `using (household_id is null or household_id in (...))`.
- `achievements` (catálogo global) — leitura pública, escrita bloqueada para todos os roles exceto service role.
- `etl_runs` — sem RLS de usuário; só acessível pela service role (jobs de backend), nunca pelo client mobile.

## Validação
Escrever um teste de RLS por família (A e B): criar dois usuários de households diferentes, confirmar que um não lê/edita dado do outro. Rodar via `pgTAP` ou via chamadas autenticadas de teste no Supabase local (`supabase start`).

## Dependência
Requer o projeto Supabase já criado (task #1) antes de poder aplicar de fato — a spec e as migrations podem ser escritas antes disso, só não executadas.
