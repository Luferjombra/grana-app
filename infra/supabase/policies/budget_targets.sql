-- budget_targets: escopo household (Família A).

alter table budget_targets enable row level security;

create policy "household members can access budget_targets"
on budget_targets for all
using (household_id in (select household_id from household_members where user_id = auth.uid()))
with check (household_id in (select household_id from household_members where user_id = auth.uid()));
