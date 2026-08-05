-- households: household_members é a própria fonte de verdade de quem pertence
-- a qual household, então a policy dela não pode depender de si mesma de forma
-- circular — usamos EXISTS/IN direto em vez de referenciar a policy de households.

alter table households enable row level security;

create policy "members can view their household"
on households for select
using (
  id in (select household_id from household_members where user_id = auth.uid())
);

-- insert/update/delete em households fica só pra service role (trigger de
-- cadastro) — nenhuma policy de escrita pro client aqui de propósito.
