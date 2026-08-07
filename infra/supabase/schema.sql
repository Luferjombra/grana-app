-- ============================================================================
-- Schema do app de orçamento pessoal (Supabase / Postgres)
-- Convenção: nomes em inglês (padrão de projeto), enums via CHECK constraint
-- para ficar simples de alterar sem migração de tipo. RLS deve ser habilitado
-- em todas as tabelas: nas que têm household_id, a policy checa se
-- auth.uid() está em household_members para aquele household_id; nas que só
-- têm user_id (gamificação, recibos, notificações — dados individuais que
-- não fazem sentido compartilhar), a policy é auth.uid() = user_id.
-- ============================================================================

begin;

-- ----------------------------------------------------------------------------
-- 0. HOUSEHOLD (orçamento compartilhado)
-- BACKLOG: hoje o produto é single-user (1 pessoa = 1 household criado
-- automaticamente no cadastro, com ela como único membro). A modelagem já
-- existe pra quando o convite de membro / orçamento em casal virar feature —
-- não é preciso migrar tabela nenhuma quando isso acontecer, só passar a
-- popular household_members com mais de uma linha por household.
-- ----------------------------------------------------------------------------

create table households (
  id                bigserial primary key,
  name              text,               -- ex: "Casa" — opcional, útil quando tiver 2+ membros
  created_at        timestamptz not null default now()
);

-- ----------------------------------------------------------------------------
-- 1. PERFIL DO USUÁRIO
-- ----------------------------------------------------------------------------

create table profiles (
  id                uuid primary key references auth.users(id) on delete cascade,
  household_id      bigint references households(id), -- criado 1:1 no cadastro (backlog: convite de membro)
  full_name         text,
  income_profile    text check (income_profile in ('clt','autonomo')) default 'clt',
  terms_accepted_at timestamptz, -- consentimento LGPD aceito no cadastro (specs/04)
  terms_version     text,        -- versão do texto de consentimento aceito
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

-- household_members depende de households e profiles já existirem, por isso
-- vem só aqui (não logo após households) — ordem importa no Postgres por
-- causa das foreign keys.
create table household_members (
  household_id      bigint not null references households(id) on delete cascade,
  user_id           uuid not null references profiles(id) on delete cascade,
  role              text not null default 'owner' check (role in ('owner','member')),
  joined_at         timestamptz not null default now(),
  primary key (household_id, user_id)
);

-- Histórico de renda mensal (permite salário variar mês a mês, e projeções
-- futuras usarem o valor vigente do mês em vez de um único campo fixo)
create table incomes (
  id                bigserial primary key,
  user_id           uuid not null references profiles(id) on delete cascade,
  amount            numeric(12,2) not null,
  effective_month   date not null,          -- primeiro dia do mês de referência
  source            text default 'salario', -- salario, freelance, outro
  created_at        timestamptz not null default now(),
  unique (user_id, effective_month, source)
);

-- Percentuais da regra 50-30-20, com default mas editável por usuário.
-- Escopada por household (não por user_id) pois é o orçamento como um todo
-- que deve ser compartilhado quando o household tiver mais de um membro.
create table budget_rules (
  household_id      bigint primary key references households(id) on delete cascade,
  necessidades_pct  numeric(5,2) not null default 50,
  desejos_pct       numeric(5,2) not null default 30,
  poupanca_pct      numeric(5,2) not null default 20,
  updated_at        timestamptz not null default now(),
  constraint pct_sum_100 check (necessidades_pct + desejos_pct + poupanca_pct = 100)
);

-- ----------------------------------------------------------------------------
-- 2. CATEGORIAS E METAS
-- ----------------------------------------------------------------------------

create table categories (
  id                bigserial primary key,
  household_id      bigint references households(id) on delete cascade, -- null = categoria padrão do sistema
  name              text not null,
  bucket            text not null check (bucket in ('necessidades','desejos','poupanca')),
  icon              text,
  is_default        boolean not null default false,
  created_at        timestamptz not null default now()
);

-- Teto calculado por mês/bucket (pode ser derivado de income * budget_rules,
-- mas materializado aqui pra facilitar consulta e permitir override manual)
create table budget_targets (
  id                bigserial primary key,
  household_id      bigint not null references households(id) on delete cascade,
  month             date not null,
  bucket            text not null check (bucket in ('necessidades','desejos','poupanca')),
  target_amount     numeric(12,2) not null,
  created_at        timestamptz not null default now(),
  unique (household_id, month, bucket)
);

-- ----------------------------------------------------------------------------
-- 3. CONTAS E TRANSAÇÕES
-- ----------------------------------------------------------------------------

-- Contas conectadas manualmente ou via Open Finance (Pluggy).
-- user_id = quem conectou a conta; household_id = pra quem ela fica visível.
create table accounts (
  id                bigserial primary key,
  user_id           uuid not null references profiles(id) on delete cascade,
  household_id      bigint not null references households(id) on delete cascade,
  provider          text not null check (provider in ('manual','pluggy')),
  external_item_id  text,               -- id do "item" no Pluggy
  institution_name  text,
  status            text not null default 'active' check (status in ('active','error','disconnected')),
  last_synced_at    timestamptz,
  created_at        timestamptz not null default now()
);

-- user_id = quem lançou a despesa (auditoria); household_id = orçamento
-- ao qual ela pertence (o que a tela de Início/Insights consulta).
create table transactions (
  id                    bigserial primary key,
  user_id               uuid not null references profiles(id) on delete cascade,
  household_id          bigint not null references households(id) on delete cascade,
  account_id            bigint references accounts(id) on delete set null,
  category_id           bigint references categories(id) on delete set null,
  type                  text not null check (type in ('expense','income','transfer')),
  amount                numeric(12,2) not null,
  occurred_at           date not null,
  merchant              text,
  note                  text,
  entry_method          text not null check (entry_method in ('manual','csv_import','receipt_ocr','open_finance')),
  receipt_id            bigint,          -- fk adicionada depois (receipts referencia transactions também)
  external_transaction_id text,          -- id da transação no Pluggy, pra dedupe no upsert
  installment_number    int,             -- parcela atual (compra parcelada no cartão)
  installment_total     int,             -- total de parcelas
  raw_payload           jsonb,           -- resposta bruta do provedor de origem (Pluggy/Mindee/import)
  created_at            timestamptz not null default now(),
  unique (account_id, external_transaction_id)
);

create index idx_transactions_household_month on transactions (household_id, occurred_at);
create index idx_transactions_category on transactions (category_id);

-- ----------------------------------------------------------------------------
-- 4. RECIBOS (OCR)
-- ----------------------------------------------------------------------------

create table receipts (
  id                    bigserial primary key,
  user_id               uuid not null references profiles(id) on delete cascade,
  image_url             text not null,   -- caminho no Supabase Storage
  status                text not null default 'pending' check (status in ('pending','processed','failed')),
  ocr_provider          text not null default 'mindee',
  extracted_payload     jsonb,           -- json normalizado: comerciante, valor, data, itens
  matched_transaction_id bigint references transactions(id) on delete set null,
  created_at            timestamptz not null default now(),
  processed_at          timestamptz
);

alter table transactions
  add constraint fk_transactions_receipt foreign key (receipt_id) references receipts(id) on delete set null;

-- ----------------------------------------------------------------------------
-- 5. ASSINATURAS RECORRENTES (detecção automática)
-- ----------------------------------------------------------------------------

create table recurring_subscriptions (
  id                bigserial primary key,
  user_id           uuid not null references profiles(id) on delete cascade,
  merchant          text not null,
  category_id       bigint references categories(id),
  amount            numeric(12,2) not null,
  cadence           text not null default 'monthly',
  last_detected_at  date,
  active            boolean not null default true,
  created_at        timestamptz not null default now()
);

-- ----------------------------------------------------------------------------
-- 6. RESERVA DE EMERGÊNCIA
-- ----------------------------------------------------------------------------

create table emergency_reserve (
  household_id                bigint primary key references households(id) on delete cascade,
  profile                     text not null check (profile in ('clt','autonomo')),
  essential_expenses_baseline numeric(12,2) not null, -- média de gasto em "necessidades"
  months_multiplier           int not null default 6, -- 6 (clt) ou 12 (autônomo)
  current_balance             numeric(12,2) not null default 0,
  updated_at                  timestamptz not null default now()
);

-- ----------------------------------------------------------------------------
-- 7. COFRINHO DE ARREDONDAMENTO
-- ----------------------------------------------------------------------------

create table roundup_savings (
  id                bigserial primary key,
  user_id           uuid not null references profiles(id) on delete cascade,
  transaction_id    bigint not null references transactions(id) on delete cascade,
  rounded_amount    numeric(12,2) not null,
  status            text not null default 'accumulated' check (status in ('accumulated','transferred')),
  transferred_at    timestamptz,
  created_at        timestamptz not null default now()
);

-- ----------------------------------------------------------------------------
-- 8. GAMIFICAÇÃO
-- ----------------------------------------------------------------------------

create table user_progress (
  user_id           uuid primary key references profiles(id) on delete cascade,
  level             int not null default 1,
  total_xp          int not null default 0,
  active_days_month int not null default 0,
  updated_at        timestamptz not null default now()
);

create table xp_events (
  id                bigserial primary key,
  user_id           uuid not null references profiles(id) on delete cascade,
  source            text not null check (source in ('logging','budget_ceiling','savings_goal','reserve_progress','roundup_active')),
  xp_amount         int not null,
  month             date not null,
  created_at        timestamptz not null default now()
);

create table achievements (
  id                bigserial primary key,
  code              text unique not null,
  name              text not null,
  description       text,
  icon              text
);

create table user_achievements (
  user_id           uuid references profiles(id) on delete cascade,
  achievement_id    bigint references achievements(id) on delete cascade,
  unlocked_at       timestamptz not null default now(),
  primary key (user_id, achievement_id)
);

-- ----------------------------------------------------------------------------
-- 9. NOTIFICAÇÕES / ALERTAS
-- ----------------------------------------------------------------------------

create table notifications (
  id                bigserial primary key,
  user_id           uuid not null references profiles(id) on delete cascade,
  type              text not null check (type in ('budget_ceiling','negative_projection','goal_hit','reserve_progress')),
  severity          text not null check (severity in ('info','warning','danger','success')),
  title             text not null,
  message           text not null,
  read              boolean not null default false,
  reference_month   date,            -- mês a que o alerta se refere (specs/07)
  subject           text,            -- bucket afetado (null p/ projeção)
  created_at        timestamptz not null default now()
);

-- Um alerta não lido por (usuário, tipo, mês, assunto) — idempotência do
-- motor de notificação (specs/07). Parcial: depois de lido, pode gerar de novo.
create unique index notifications_unread_dedupe
  on notifications (
    user_id,
    type,
    coalesce(reference_month, '1970-01-01'::date),
    coalesce(subject, '')
  )
  where read = false;

create index idx_notifications_user_unread on notifications (user_id, read);

-- ----------------------------------------------------------------------------
-- 10. OBSERVABILIDADE DE JOBS (padrão da skill arquiteto, reaproveitado aqui
--     pra sync de Open Finance, processamento de OCR e recomputo de projeção)
-- ----------------------------------------------------------------------------

create table etl_runs (
  id                bigserial primary key,
  job               text not null,       -- ex: 'pluggy_sync', 'projection_recompute', 'ocr_process'
  started_at        timestamptz not null default now(),
  finished_at       timestamptz,
  status            text check (status in ('running','success','error')),
  rows_upserted     int,
  error_msg         text
);

commit;
