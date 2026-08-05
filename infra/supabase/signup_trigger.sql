-- ============================================================================
-- Trigger de cadastro: cria household + membership + budget_rules default
-- automaticamente sempre que um novo usuário é criado no Supabase Auth.
-- Rodar depois de schema.sql, rls_policies.sql e do seed de categorias.
-- ============================================================================

begin;

create or replace function handle_new_user()
returns trigger as $$
declare
  new_household_id bigint;
begin
  insert into households (name) values (null) returning id into new_household_id;

  insert into profiles (id, household_id, full_name)
  values (new.id, new_household_id, new.raw_user_meta_data->>'full_name');

  insert into household_members (household_id, user_id, role)
  values (new_household_id, new.id, 'owner');

  insert into budget_rules (household_id)
  values (new_household_id); -- usa os defaults 50/30/20 da coluna

  return new;
end;
$$ language plpgsql security definer set search_path = public;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();

commit;
