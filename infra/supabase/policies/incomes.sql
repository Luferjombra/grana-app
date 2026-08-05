-- incomes: escopo individual (Família B).

alter table incomes enable row level security;

create policy "user owns incomes" on incomes for all
using (auth.uid() = user_id) with check (auth.uid() = user_id);
