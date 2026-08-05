# Spec: scaffold do monorepo

## Objetivo
Estrutura inicial de repositório único contendo o app mobile, o backend e o ETL, com ferramentas compartilhadas configuradas — sem lógica de negócio ainda.

## Estrutura de pastas

```
grana/
├── apps/
│   ├── mobile/          # React Native + Expo
│   └── backend/         # FastAPI
├── etl/                 # jobs Python: sync Pluggy, indicadores BACEN, recomputo de projeção
├── infra/
│   └── supabase/
│       ├── schema.sql
│       ├── seed/
│       └── policies/    # RLS, um arquivo .sql por tabela
├── docs/
│   └── adr/              # decisões de arquitetura registradas ao longo do projeto
├── .github/workflows/    # CI (lint/test) e cron do ETL
├── .env.example
└── README.md
```

## `apps/mobile` (React Native + Expo)
- `npx create-expo-app` como base, TypeScript.
- Estrutura interna: `app/` (rotas Expo Router), `components/`, `lib/api.ts` (client do backend), `lib/supabase.ts` (client de auth).
- Variáveis de ambiente: `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_ANON_KEY`.

## `apps/backend` (FastAPI)
- Estrutura por domínio, não por camada técnica: `app/transactions/`, `app/budget/`, `app/gamification/`, `app/notifications/`, cada um com `router.py`, `schemas.py`, `service.py`.
- `app/providers/` para os adaptadores modulares (`receipt_ocr/`, `bank_aggregator/`), conforme specs 05 e 06.
- Variáveis de ambiente: `DATABASE_URL`, `SUPABASE_SERVICE_KEY`, `MINDEE_API_KEY`, `PLUGGY_CLIENT_ID`, `PLUGGY_CLIENT_SECRET`.

## `etl/`
- Scripts Python independentes, cada um registrando execução em `etl_runs` (ver spec 07 e schema.sql).
- Reaproveita o padrão já usado na plataforma de investimentos (mesma convenção de `etl_runs`).

## Ferramentas compartilhadas
- Lint/format: `ruff` + `black` no Python, `eslint` + `prettier` no TypeScript — configuração na raiz, cada app herda.
- Testes: `pytest` no backend/etl, `jest` no mobile.
- Pre-commit: lint + type-check antes de cada commit.

## `.github/workflows/`
- `ci.yml`: lint + testes em cada PR.
- `etl.yml`: cron do ETL (spec 07), conforme padrão da skill arquiteto.

## README.md
Deve cobrir: como rodar o mobile (`npx expo start`), como rodar o backend localmente (`uvicorn app.main:app --reload`), como aplicar o schema no Supabase, e onde ficam as variáveis de ambiente de cada app.

## Fora de escopo desta spec
Deploy (Expo EAS Build, hospedagem do backend) — vira spec própria quando o app estiver funcional localmente.
