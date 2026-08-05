-- household_members: fonte de verdade de quem pertence a qual household.

alter table household_members enable row level security;

create policy "members can view household membership"
on household_members for select
using (
  household_id in (select household_id from household_members where user_id = auth.uid())
);

-- insert/update/delete em household_members fica só pra service role
-- (trigger de cadastro e, futuramente, fluxo de convite) — nenhuma policy
-- de escrita pro client aqui de propósito.
