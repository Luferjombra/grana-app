-- ============================================================================
-- Migration 0005: regras de categorização aprendidas no import (specs/11).
--
-- É o que transforma o import de histórico em algo viável. Medido no extrato
-- real usado pra validar a spec (Banco C6, 1.059 lançamentos, 12 meses):
-- agrupar por comerciante já derruba 951 despesas para 169 decisões, mas 169
-- numa sentada só é inviável no celular. Guardando a decisão, o 1º mês custa
-- 23 escolhas e os seguintes chegam com 70-92% já resolvido.
--
-- A chave é `merchant_key` (app/imports/suggest.py::merchant_key): a descrição
-- normalizada, sem número nem ruído de descritor de cartão, cortada nas 3
-- primeiras palavras. Ela é derivada em Python, não no banco, porque a regra de
-- normalização muda junto com o parser e não vale espalhar essa lógica em duas
-- linguagens.
--
-- Consequência disso: se `merchant_key` mudar de fórmula, as regras existentes
-- deixam de casar. Elas não corrompem nada — só param de valer, e o usuário
-- reescolhe. Preferível a um índice funcional no banco que travaria a evolução
-- do parser.
-- ============================================================================

begin;

create table if not exists import_rules (
  id            bigserial primary key,
  household_id  bigint not null references households (id) on delete cascade,
  merchant_key  text not null check (length(trim(merchant_key)) > 0),

  -- on delete cascade, e não set null: regra sem categoria não é regra. Se o
  -- usuário apagar a categoria, a sugestão simplesmente deixa de existir e ele
  -- escolhe de novo — melhor que uma regra órfã apontando pro nada.
  category_id   bigint not null references categories (id) on delete cascade,

  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- Uma regra por comerciante por household. O upsert do confirm depende deste
-- índice: reescolher a categoria do mesmo comerciante sobrescreve a regra em
-- vez de acumular duas contraditórias.
create unique index if not exists import_rules_household_merchant
  on import_rules (household_id, merchant_key);

alter table import_rules enable row level security;

-- Regra é sempre do household; não existe regra "do sistema" como acontece com
-- as 9 categorias padrão (household_id null). O palpite inicial de quem nunca
-- importou nada vive em suggest.RULES, no código, não aqui.
create policy "members read their household rules"
on import_rules for select
using (household_id in (select household_id from household_members where user_id = auth.uid()));

create policy "members create rules for their household"
on import_rules for insert
with check (household_id in (select household_id from household_members where user_id = auth.uid()));

create policy "members update their household rules"
on import_rules for update
using (household_id in (select household_id from household_members where user_id = auth.uid()));

create policy "members delete their household rules"
on import_rules for delete
using (household_id in (select household_id from household_members where user_id = auth.uid()));

commit;
