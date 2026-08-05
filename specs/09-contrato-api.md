# Spec: contrato da API (endpoints REST)

Base: `apps/backend`, FastAPI, autenticação via JWT do Supabase Auth (validado em middleware, `household_id` resolvido a partir do `user_id` do token).

## Transações
- `GET /transactions?month=2026-08&category_id=&type=` — lista paginada, filtros opcionais.
- `POST /transactions` — cria (manual). Body: `amount, category_id, type, occurred_at, merchant, note, installment_number?, installment_total?`.
- `PATCH /transactions/{id}` — edita.
- `DELETE /transactions/{id}`.
- `POST /transactions/import` — CSV/OFX (multipart), retorna preview antes de confirmar em lote.

## Recibos (OCR)
- `POST /receipts` — upload de imagem, retorna `receipt_id` com `status = pending`.
- `GET /receipts/{id}` — poll do status/`extracted_payload`.
- `POST /receipts/{id}/confirm` — confirma os campos extraídos (ou editados pelo usuário) e cria a `transaction` vinculada.

## Contas / Open Finance
- `POST /accounts/connect-token` — retorna o token do Pluggy Connect.
- `POST /accounts/callback` — recebe o `item_id` após o usuário concluir a conexão.
- `GET /accounts` — lista contas conectadas e status.
- `DELETE /accounts/{id}` — desconecta.

## Dashboard / Início
- `GET /dashboard/summary?month=2026-08` — fluxo de caixa, IN/OUT, distribuição por categoria (donut), health score.
- `GET /dashboard/budget-rule` — percentuais 50-30-20 vigentes do household.
- `PATCH /dashboard/budget-rule` — edita os percentuais.

## Insights
- `GET /insights/month-over-month?month=2026-08`
- `GET /insights/recurring-subscriptions`
- `GET /insights/top-transactions?month=2026-08&limit=5`
- `GET /insights/three-month-average`
- `GET /insights/health-score-breakdown`

## Reserva de emergência
- `GET /emergency-reserve`
- `PATCH /emergency-reserve` — muda `profile` (clt/autonomo) ou `essential_expenses_baseline`.

## Gamificação
- `GET /gamification/progress` — nível, XP, breakdown por fonte, dias ativos no mês.
- `GET /gamification/achievements` — desbloqueadas + bloqueadas.
- `GET /roundup` — saldo acumulado do cofrinho no mês.
- `POST /roundup/transfer` — transferência manual (fase 1, sem automação real ainda).

## Notificações
- `GET /notifications?unread=true`
- `PATCH /notifications/{id}/read`
- `POST /push-tokens` — registra token de push (spec 08).

## Convenções gerais
- Erros no formato `{ "detail": "mensagem" }`, status HTTP semântico (400/401/403/404/422).
- Toda resposta de valor monetário em `numeric`/string decimal, nunca float bruto (evita erro de arredondamento no client).
- Paginação por cursor (`?cursor=`) nas listagens que podem crescer (`/transactions`).
