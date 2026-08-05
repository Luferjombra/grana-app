# Spec: fluxo de cadastro e login

Referência visual: `prototipo/01-onboarding-1.html` a `04-cadastro.html`.

## Métodos suportados
E-mail/senha, Google, Apple — todos via Supabase Auth.

## Fluxo de cadastro
1. Onboarding (3 telas de proposta de valor, puláveis) → tela de Cadastro.
2. Usuário escolhe Google, Apple, ou preenche nome/e-mail/senha.
3. Checkbox de consentimento obrigatório (não deixa habilitar "Criar minha conta" sem marcar) com o texto: "Aceito os termos de uso e a política de privacidade, e autorizo o processamento dos meus dados financeiros pra gerar os insights do app." — texto final precisa passar por revisão jurídica antes de produção (é o texto de consentimento LGPD para dados financeiros).
4. Supabase Auth cria o usuário (`auth.users`).
5. Trigger de banco (`on_auth_user_created`, `after insert on auth.users`) roda automaticamente e:
   - insere em `profiles` (id = auth.users.id, full_name do metadata)
   - cria um novo `household` (name = null)
   - insere em `household_members` (household_id, user_id, role = 'owner')
   - insere um `budget_rules` default (50/30/20) para o household criado
6. App redireciona pro fluxo de onboarding de dados (perfil CLT/autônomo, salário do mês — telas ainda não especificadas, ficam pra depois).

## Trigger SQL (esqueleto)

```sql
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
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();
```

## Login (usuário existente)
Tela simples: e-mail/senha ou os mesmos botões sociais. "Esqueci minha senha" via fluxo padrão do Supabase Auth (magic link ou reset por e-mail).

## Configuração externa necessária (ver tasks #1 e #4)
- Projeto Supabase criado, com Auth habilitado.
- OAuth client Google (Google Cloud Console) registrado no Supabase Auth.
- Sign in with Apple configurado (Apple Developer) e registrado no Supabase Auth.

## Fora de escopo
Autenticação por telefone/SMS, 2FA — não discutidos ainda, não incluir nesta versão.
