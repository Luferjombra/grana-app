-- categories: caso especial — categorias padrão do sistema (household_id
-- null) são visíveis por todo mundo; categorias próprias, só pelo household.

alter table categories enable row level security;

create policy "everyone can read default categories, members read their own"
on categories for select
using (
  household_id is null
  or household_id in (select household_id from household_members where user_id = auth.uid())
);

create policy "members can create their own categories"
on categories for insert
with check (
  household_id in (select household_id from household_members where user_id = auth.uid())
);

create policy "members can edit/delete only their own categories"
on categories for update
using (household_id in (select household_id from household_members where user_id = auth.uid()));

create policy "members can delete only their own categories"
on categories for delete
using (household_id in (select household_id from household_members where user_id = auth.uid()));
