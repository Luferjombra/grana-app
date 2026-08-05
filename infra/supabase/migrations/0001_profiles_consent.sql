-- ============================================================================
-- Migration 0001: consentimento LGPD em profiles (specs/04-cadastro-login.md)
-- Rodar no Supabase já provisionado (schema.sql/signup_trigger.sql originais
-- já aplicados). Um ambiente novo já nasce com essas colunas via schema.sql.
-- ============================================================================

begin;

alter table profiles
  add column if not exists terms_accepted_at timestamptz,
  add column if not exists terms_version text;

-- Recria o trigger de cadastro pra também gravar o consentimento quando
-- disponível no metadata do signUp (fluxo e-mail/senha). No fluxo Google,
-- o app grava terms_accepted_at/terms_version direto em profiles logo após
-- a sessão OAuth ser estabelecida (Supabase não permite anexar metadata
-- própria na criação do auth.users via OAuth).
create or replace function handle_new_user()
returns trigger as $$
declare
  new_household_id bigint;
begin
  insert into households (name) values (null) returning id into new_household_id;

  insert into profiles (id, household_id, full_name, terms_accepted_at, terms_version)
  values (
    new.id,
    new_household_id,
    new.raw_user_meta_data->>'full_name',
    case when new.raw_user_meta_data->>'terms_version' is not null then now() end,
    new.raw_user_meta_data->>'terms_version'
  );

  insert into household_members (household_id, user_id, role)
  values (new_household_id, new.id, 'owner');

  insert into budget_rules (household_id)
  values (new_household_id);

  return new;
end;
$$ language plpgsql security definer set search_path = public;

commit;
