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
`EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_ANON_KEY`,
`MINDEE_API_KEY`, `PLUGGY_CLIENT_ID`, `PLUGGY_CLIENT_SECRET`.

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

- `schema.sql` — schema completo já aplicado no Supabase.
- `rls_policies.sql` — políticas de RLS já aplicadas.
- `signup_trigger.sql` — trigger de criação de household já aplicado.
- `specs/01` a `specs/09` — specs técnicas detalhadas de cada frente
  (scaffold do monorepo, RLS, seed, cadastro/login, adaptador OCR, adaptador
  Open Finance, job de projeção/notificação, push, contrato da API REST).
- `prototipo/` — 10 telas HTML do protótipo visual (onboarding, cadastro,
  início, atividade, insights, metas, notificações, adicionar despesa) —
  usar como referência de UX/copy ao implementar as telas React Native.

## Próximos passos sugeridos (retomar por aqui)

1. Scaffold do monorepo seguindo `specs/01-scaffold-monorepo.md`.
2. Implementar os adaptadores `ReceiptOcrProvider`/`MindeeProvider` e
   `BankAggregatorProvider`/`PluggyProvider` com `MockProvider` de fallback
   (specs 05 e 06).
3. Implementar os endpoints do contrato da API (spec 09).
4. Implementar o app mobile, tela por tela, usando o protótipo HTML como
   referência visual — nessa etapa nasce o projeto Expo/EAS, resolvendo a
   pendência de push notifications (spec 08).
5. Job de projeção/notificação (spec 07).

## Como o usuário prefere trabalhar

Direto e aberto — questionar decisões antes de assumir default, não
implementar silenciosamente uma escolha ambígua. Prefere specs/decisões
resolvidas antes de código ser escrito quando o escopo é grande; pra ajustes
pontuais, pode ir direto ao código.
