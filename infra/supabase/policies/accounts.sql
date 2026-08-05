-- accounts: escopo household (Família A).

alter table accounts enable row level security;

create policy "household members can access accounts"
on accounts for all
using (household_id in (select household_id from household_members where user_id = auth.uid()))
with check (household_id in (select household_id from household_members where user_id = auth.uid()));
