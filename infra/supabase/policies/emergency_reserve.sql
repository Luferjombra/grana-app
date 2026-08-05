-- emergency_reserve: escopo household (Família A).

alter table emergency_reserve enable row level security;

create policy "household members can access emergency_reserve"
on emergency_reserve for all
using (household_id in (select household_id from household_members where user_id = auth.uid()))
with check (household_id in (select household_id from household_members where user_id = auth.uid()));
