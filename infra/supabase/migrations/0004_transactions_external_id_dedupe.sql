-- ============================================================================
-- Migration 0004: dedupe de external_transaction_id por household (specs/11).
--
-- O schema já tinha `unique (account_id, external_transaction_id)`, desenhado
-- pro Pluggy, em que account_id sempre existe. No import de extrato não há
-- conta, então account_id fica null — e no Postgres nulos são distintos entre
-- si, o que anula a proteção: reimportar o mesmo OFX duplicaria tudo.
--
-- O índice abaixo é por household e ignora linhas sem id externo (lançamento
-- manual e CSV, que não têm id do banco).
-- ============================================================================

begin;

create unique index if not exists transactions_household_external_id
  on transactions (household_id, external_transaction_id)
  where external_transaction_id is not null;

commit;
