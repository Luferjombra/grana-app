-- ============================================================================
-- Migration 0003: identidade de notificação pra idempotência (specs/07).
--
-- A spec 07 exige "não recriar a mesma notificação se já existe uma não lida
-- do mesmo tipo pro mesmo mês — atualizar a existente". O schema original de
-- `notifications` não tinha como expressar isso: só type/severity/title/
-- message/read/created_at. Derivar o mês de created_at não serve, porque o
-- cron do dia 1 avalia o mês anterior (goal_hit), e dois buckets distintos
-- estourando o teto são duas notificações diferentes, não uma.
-- ============================================================================

begin;

alter table notifications
  add column if not exists reference_month date,  -- mês a que o alerta se refere
  add column if not exists subject text;          -- bucket afetado (null p/ projeção)

-- Um alerta NÃO LIDO por (usuário, tipo, mês, assunto). Parcial de propósito:
-- depois que o usuário lê, um novo alerta do mesmo tipo pode ser gerado se a
-- situação persistir — é o comportamento pedido na spec.
create unique index if not exists notifications_unread_dedupe
  on notifications (
    user_id,
    type,
    coalesce(reference_month, '1970-01-01'::date),
    coalesce(subject, '')
  )
  where read = false;

commit;
