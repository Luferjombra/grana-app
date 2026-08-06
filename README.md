# Grana

App de controle financeiro pessoal (regra 50-30-20), com gamificação,
importação de extrato, OCR de recibo (Mindee) e conexão bancária via Open
Finance (Pluggy).

## Estrutura

```
apps/
├── mobile/     # React Native + Expo (Expo Router)
└── backend/    # FastAPI
etl/            # jobs Python: sync Pluggy, indicadores BACEN, recomputo de projeção
infra/
└── supabase/
    ├── schema.sql
    ├── signup_trigger.sql
    ├── seed/       # seed de categorias padrão
    └── policies/   # RLS, um arquivo .sql por tabela
docs/
└── adr/        # decisões de arquitetura
specs/          # specs técnicas de cada frente
prototipo/      # protótipo visual (HTML) — referência de UX/copy
```

## Pré-requisitos

- Node.js 20+
- Python 3.11+
- Conta Supabase (projeto já provisionado — ver `CLAUDE.md`)

## Rodando o mobile

```bash
cd apps/mobile
npm install
cp .env.example .env   # preencher EXPO_PUBLIC_SUPABASE_URL / ANON_KEY
npx expo start
```

## Rodando o backend

```bash
cd apps/backend
python -m venv .venv
.venv/Scripts/activate       # .venv/bin/activate no Linux/Mac
pip install -e ".[dev]"
cp .env.example .env         # preencher DATABASE_URL, SUPABASE_SERVICE_KEY etc.
uvicorn app.main:app --reload
```

Sem `MINDEE_API_KEY`/`PLUGGY_CLIENT_ID` configurados, os providers caem
automaticamente no `MockProvider` (ver `app/providers/`).

## Rodando o ETL

```bash
cd etl
python -m venv .venv
.venv/Scripts/activate
pip install -e ".[dev]"
cp .env.example .env
python -m etl.projection_recompute   # ou pluggy_sync / bacen_indicadores
```

## Aplicando o schema no Supabase

Rodar, nesta ordem, no SQL editor do projeto Supabase (`Plataforma Controle
Financeiro`, `sa-east-1`):

1. `infra/supabase/schema.sql`
2. Cada arquivo em `infra/supabase/policies/*.sql` (RLS)
3. `infra/supabase/seed/categorias.sql`
4. `infra/supabase/signup_trigger.sql`

> Isso já foi aplicado no projeto atual — rodar de novo só é necessário ao
> recriar o ambiente (ex: novo projeto Supabase de staging).

No projeto já provisionado, aplicar também as migrations incrementais em
`infra/supabase/migrations/`, em ordem numérica, cada uma exatamente uma vez:

1. `0001_profiles_consent.sql` — adiciona `terms_accepted_at`/`terms_version`
   em `profiles` e atualiza o trigger de cadastro (specs/04).
2. `0002_storage_receipts_policies.sql` — políticas de Storage pro bucket
   `receipts` (specs/05). **Pré-requisito manual**: criar o bucket `receipts`
   no painel do Supabase (Storage -> New bucket) marcado como **privado**
   antes de rodar esta migration.

## Variáveis de ambiente por app

| App | Arquivo | Variáveis |
|---|---|---|
| `apps/mobile` | `.env.example` | `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_ANON_KEY` |
| `apps/backend` | `.env.example` | `DATABASE_URL`, `SUPABASE_SERVICE_KEY`, `MINDEE_API_KEY`, `RECEIPT_OCR_PROVIDER`, `PLUGGY_CLIENT_ID`, `PLUGGY_CLIENT_SECRET`, `BANK_AGGREGATOR_PROVIDER` |
| `etl` | `.env.example` | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `PLUGGY_CLIENT_ID`, `PLUGGY_CLIENT_SECRET` |

## Lint / testes / pre-commit

```bash
pip install pre-commit
pre-commit install
```

- Backend/ETL: `ruff check .` + `black --check .` + `pytest -q` (backend).
- Mobile: `npm run lint` (eslint) + `npm run format:check` (prettier) + `npx tsc --noEmit`.
- CI roda os três em cada PR (`.github/workflows/ci.yml`); cron do ETL em
  `.github/workflows/etl.yml`.

## Fora de escopo deste scaffold

Deploy (Expo EAS Build, hospedagem do backend) e implementação de lógica de
negócio — ver `specs/` para cada frente.
