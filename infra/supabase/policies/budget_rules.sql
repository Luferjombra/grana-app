-- budget_rules: escopo household (Família A).

alter table budget_rules enable row level security;

create policy "household members can access budget_rules"
on budget_rules for all
using (household_id in (select household_id from household_members where user_id = auth.uid()))
with check (household_id in (select household_id from household_members where user_id = auth.uid()));
