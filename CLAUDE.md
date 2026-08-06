# Grana — app de controle financeiro pessoal (50-30-20)

Handoff da sessão de planejamento no Cowork para continuidade no Claude Code.
Este arquivo resume tudo que já foi decidido e feito, pra você (Claude Code)
não repetir descoberta nem reabrir decisões já fechadas com o usuário.

## O que é o produto

App mobile de controle financeiro pessoal. O usuário informa o salário do mês,
o app mostra onde ele está gastando mais por categoria, aplica a regra
50-30-20 (necessidades/desejos/poupança) com gamificação pra ele bater as
metas, calcula uma reserva de emergência automática, e facilita o registro de
gastos por três vias: importação de extrato (CSV/OFX), foto de recibo (OCR) e
conexão bancária via Open Finance.

## Stack decidida (não reabrir)

- **Frontend mobile**: React Native + Expo
- **Backend**: FastAPI (Python)
- **Banco/infra**: Supabase (Postgres + Auth + Storage)
- **OCR de recibo**: Mindee, atrás de uma interface `ReceiptOcrProvider`
- **Open Finance**: Pluggy, atrás de uma interface `BankAggregatorProvider`
- **Repositório**: monorepo (`apps/mobile`, `apps/backend`, `etl/`)
- **Jobs agendados**: híbrido evento + cron diário (GitHub Actions ou Supabase Edge Functions)

Motivo do FastAPI/Python: existe uma outra plataforma do mesmo usuário
(dados de investimento — CVM/BCB/B3 via um MCP chamado mcp-brasil) que já usa
esse padrão. Alinhar facilita reaproveitar ETL entre os dois projetos no futuro
— mas são projetos separados, não confundir escopo.

## Infra já provisionada — NÃO recriar

- Projeto Supabase criado: **"Plataforma Controle Financeiro"**, região `sa-east-1` (São Paulo).
  URL: `https://qsyvghfttqcfirftudwg.supabase.co`
- `schema.sql` já aplicado no banco (18 tabelas — ver arquivo anexo).
- Políticas de RLS já aplicadas (`rls_policies.sql`).
- Seed das 9 categorias padrão já rodado.
- Trigger `on_auth_user_created` já criado e testado com usuário real
  (cria household + membership + budget_rules automaticamente no cadastro).
- Conta Mindee criada, API key gerada (nome "Controle Financeiro", 200 créditos free trial).
- Conta Pluggy criada, aplicação "Controle Financeiro" com Client ID/Secret gerados (ambiente Development/Sandbox).
- Google OAuth configurado e ativo no Supabase Auth (Sign in with Google funcionando).
- Apple Sign-In: **adiado**, fica em backlog (exige Apple Developer Program, US$ 99/ano, ainda não contratado). Cadastro sai só com e-mail/senha + Google por enquanto.
- Push notifications (Expo): **ainda não configurado** — depende do projeto Expo/EAS nascer junto com o scaffold do mobile.

As credenciais reais (chaves, secrets) NÃO estão neste arquivo por segurança —
pedir pro usuário colar num `.env` local quando for configurar cada serviço.
Variáveis esperadas: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`,
`SUPABASE_JWT_SECRET` (Supabase -> Settings -> API -> JWT Settings),
`EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_ANON_KEY`,
`MINDEE_API_KEY`, `PLUGGY_CLIENT_ID`, `PLUGGY_CLIENT_SECRET`.

Bucket `receipts` no Supabase Storage: **ainda não criado** — precisa ser
criado manualmente (privado) antes de rodar a migration 0002 (ver README).

## Decisões de produto já fechadas (não reabrir sem justificativa nova)

- Regra 50-30-20 com percentuais **editáveis** por household (não fixos no código).
- Transações suportam parcelamento (`installment_number`/`installment_total`).
- Modelagem de **household** (orçamento compartilhado) já existe no schema,
  mas a feature de convite de membro está em backlog — hoje é sempre 1
  household = 1 usuário, criado automaticamente no cadastro.
- Gamificação: XP misto (parte por hábito de registrar, parte por bater meta
  real), streak reformulado como "dias ativos no mês" sem quebra/punição,
  cofrinho de arredondamento em modo manual (usuário confirma a transferência
  — automação real via Pluggy ITP é fase futura).
- Alertas: 95% do teto de categoria/bucket dispara aviso; projeção de
  fechamento do mês usa ritmo linear de gasto diário e dispara alerta de
  risco negativo acima de 97% da renda. Recalculado por evento (toda
  transação salva) + cron diário à meia-noite.
- Notificações: dentro do app **e** push.
- Categorias padrão do sistema (lista fechada, ver seed): Moradia, Mercado,
  Contas, Transporte (necessidades); Lazer, Compras, Delivery, Streaming
  (desejos); Investimentos (poupança).

## Arquivos desta pasta

- `infra/supabase/schema.sql` — schema completo já aplicado no Supabase.
- `infra/supabase/policies/*.sql` — políticas de RLS já aplicadas (uma por tabela).
- `infra/supabase/seed/categorias.sql` — seed das 9 categorias padrão, já rodado.
- `infra/supabase/signup_trigger.sql` — trigger de criação de household já aplicado.
- `infra/supabase/migrations/` — migrations incrementais pro Supabase já
  provisionado (schema.sql/signup_trigger.sql refletem o estado alvo "do
  zero"; o que já está em produção precisa rodar cada migration em ordem).
- `specs/01` a `specs/09` — specs técnicas detalhadas de cada frente
  (scaffold do monorepo, RLS, seed, cadastro/login, adaptador OCR, adaptador
  Open Finance, job de projeção/notificação, push, contrato da API REST).
- `prototipo/` — 10 telas HTML do protótipo visual (onboarding, cadastro,
  início, atividade, insights, metas, notificações, adicionar despesa) —
  usar como referência de UX/copy ao implementar as telas React Native.

## Status atual (atualizado a cada commit — ver regra no fluxo de trabalho)

- ✅ **Spec 01 (scaffold do monorepo)** — `apps/mobile` (Expo Router + TS),
  `apps/backend` (FastAPI por domínio, providers mock), `etl/` (stubs +
  convenção `etl_runs`), tooling (ruff/black/eslint/prettier/pre-commit/CI).
  Repo no GitHub: `Luferjombra/grana-app`.
- ✅ **Spec 04 (cadastro/login)** — telas de cadastro (e-mail/senha + Google,
  consentimento LGPD com `terms_accepted_at`/`terms_version`), login, esqueci
  minha senha (fluxo PKCE), e gate de sessão pra profile ausente. Fluxo OAuth
  e recovery usam `flowType: 'pkce'` no client Supabase — exige que o
  Redirect URL `grana://` (sem path) esteja na allow-list do Supabase Auth
  (já configurado).
- ⏳ Specs 02/03 (schema/RLS/seed) — aplicadas manualmente, sem script de
  aplicação automatizado ainda.
- 🟡 **Spec 05 (OCR de recibo) — Mindee pronto, Pluggy (spec 06) ainda não
  iniciado.** `MindeeProvider` real implementado (SDK v5, `client.v1.Client` +
  `product.ReceiptV5`, campos abaixo de 0.5 de confiança viram `null`),
  endpoints `POST /receipts`, `GET /receipts/{id}`, `POST
  /receipts/{id}/confirm` funcionando com auth JWT real (`app/auth.py`,
  `SUPABASE_JWT_SECRET`) e Supabase Storage (bucket `receipts`, privado —
  **pré-requisito manual**: criar o bucket no painel antes de rodar a
  migration `0002_storage_receipts_policies.sql`). Processamento roda em
  FastAPI `BackgroundTasks` (sem fila/Redis nesta fase). `confirm_receipt` usa
  update condicional (`is_ matched_transaction_id null`) pra evitar duplicar
  transaction em double-tap. Todas as chamadas ao Supabase (síncrono) rodam
  via `asyncio.to_thread` pra não bloquear o event loop — seguir esse padrão
  em qualquer endpoint novo que use `get_db()`.
- ⏳ Spec 06 (Pluggy/Open Finance) — não iniciada.
- ⏳ Specs 07, 08, 09 (fora do que já existe pra recibos) — não iniciadas.

## Próximos passos sugeridos (retomar por aqui)

1. Implementar `BankAggregatorProvider`/`PluggyProvider` de verdade + rotas
   de contas (`/accounts/connect-token`, `/accounts/callback`, etc.) — hoje só
   existe `MockProvider` (spec 06). Decidir como o Pluggy Connect (widget web)
   vai rodar dentro do app Expo (WebView vs SDK nativo) antes de codar.
2. Implementar o resto dos endpoints do contrato da API — hoje só
   `receipts/*` é real, o restante (`transactions`, `budget`, `gamification`,
   `notifications`) ainda são stubs com `NotImplementedError` (spec 09).
3. Telas de onboarding de dados (perfil CLT/autônomo, salário do mês) — hoje
   o pós-cadastro cai direto no dashboard vazio, essas telas ainda não têm spec.
4. Job de projeção/notificação (spec 07).
5. Push notifications — nasce o projeto Expo/EAS (spec 08).
6. Tela mobile do fluxo de recibo (upload de foto, confirmação dos campos
   extraídos) — o backend já está pronto, falta a UI que consome
   `POST /receipts` → poll `GET /receipts/{id}` → `POST /receipts/{id}/confirm`.

## Como o usuário prefere trabalhar

Direto e aberto — questionar decisões antes de assumir default, não
implementar silenciosamente uma escolha ambígua. Prefere specs/decisões
resolvidas antes de código ser escrito quando o escopo é grande; pra ajustes
pontuais, pode ir direto ao código.

## Fluxo de trabalho obrigatório (não pular, mesmo sem o usuário pedir de novo)

1. **Sempre rodar `/code-review` (pair programming) antes de qualquer commit**,
   corrigindo os achados relevantes antes de commitar — não só na primeira vez
   que for pedido, em **todo** commit deste projeto daqui pra frente.
2. **Ao commitar, atualizar a seção "Status atual" deste CLAUDE.md** pra
   refletir o que mudou (specs concluídas, pendências novas) — este arquivo é
   o handoff entre sessões, não pode ficar desatualizado.
