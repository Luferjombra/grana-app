-- roundup_savings: escopo individual (Família B).

alter table roundup_savings enable row level security;

create policy "user owns roundup_savings" on roundup_savings for all
using (auth.uid() = user_id) with check (auth.uid() = user_id);
