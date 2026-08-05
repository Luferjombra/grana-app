-- recurring_subscriptions: escopo individual (Família B).

alter table recurring_subscriptions enable row level security;

create policy "user owns recurring_subscriptions" on recurring_subscriptions for all
using (auth.uid() = user_id) with check (auth.uid() = user_id);
