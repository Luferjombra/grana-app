-- transactions: escopo household (Família A).

alter table transactions enable row level security;

create policy "household members can access transactions"
on transactions for all
using (household_id in (select household_id from household_members where user_id = auth.uid()))
with check (household_id in (select household_id from household_members where user_id = auth.uid()));
