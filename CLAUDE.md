# Grana — app de controle financeiro pessoal (50-30-20)

Handoff da sessão de planejamento no Cowork para continuidade no Claude Code.
Este arquivo resume tudo que já foi decidido e feito, pra você (Claude Code)
não repetir descoberta nem reabrir decisões já fechadas com o usuário.

## O que é o produto

App mobile de controle financeiro pessoal. O usuário informa o salário do mês,
o app mostra onde ele está gastando mais por categoria, aplica a regra
50-30-20 (necessidades/desejos/poupança) com gamificação pra ele bater as
metas, calcula uma reserva de emergência automática, e facilita o registro de
gastos por **duas** vias: lançamento manual e foto de recibo (OCR), com
importação de extrato (CSV/OFX) como a ponte com o banco.

> A terceira via planejada, conexão bancária via Open Finance, foi **adiada por
> barreira regulatória** — ver `docs/adr/0001-open-finance-adiado.md`. Não
> reintroduzir na descrição do produto sem revisitar aquela ADR.

## Stack decidida (não reabrir)

- **Frontend mobile**: React Native + Expo
- **Backend**: FastAPI (Python)
- **Banco/infra**: Supabase (Postgres + Auth + Storage)
- **OCR de recibo**: Mindee, atrás de uma interface `ReceiptOcrProvider`
- **Open Finance**: Pluggy, atrás de uma interface `BankAggregatorProvider` —
  **adiado**, ver `docs/adr/0001-open-finance-adiado.md`
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

Não existe `SUPABASE_JWT_SECRET`: este projeto assina JWT com chave
assimétrica (ECC P-256/ES256, em Settings -> JWT Keys), não com segredo
compartilhado HS256 — o backend valida via JWKS público
(`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`), que acompanha rotação de
chave sozinho. Não reintroduzir validação HS256 (o backend rejeita HS256 de
propósito, pra evitar algorithm confusion com a chave pública do JWKS).

Bucket `receipts` no Supabase Storage: **já criado** (privado) e migration
0002 (policies de leitura) já aplicada.

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
- **Reserva de emergência: `gasto em necessidades × 6 (clt) ou 12 (autônomo)`.**
  Revisitado e **mantido** em 08/08/2026, depois de o usuário levantar "deveria
  ser gasto mensal × 12". As duas partes foram decididas de novo, com os números
  na mesa:
  - **Multiplicador segue 6/12**, não 12 pra todos. Doze meses pra CLT fica bem
    acima da recomendação usual (3-6 meses pra renda estável), e alvo grande
    demais trava a barra perto de zero por anos — o marco de "1 mês de reserva"
    passaria a valer 8% da meta em vez de 17%.
  - **A base segue só necessidades**, não o gasto mensal total. Se a renda
    parar, Delivery/Streaming/Compras não continuam, então dimensionar o colchão
    pelo padrão de vida completo infla a meta com gasto que a própria emergência
    elimina. Num exemplo de renda R$ 8.000 (R$ 4.000 necessidades + R$ 2.400
    desejos), trocar pra total × 12 levaria o alvo de R$ 24.000 pra R$ 76.800.
  - É também o que faz a reserva conversar com o 50-30-20: o bucket
    necessidades já é, por definição, "o que eu não consigo cortar".
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
  /receipts/{id}/confirm` funcionando com auth JWT real via JWKS
  (`app/auth.py`, ES256) e Supabase Storage (bucket `receipts`, privado — já
  criado, migration `0002_storage_receipts_policies.sql` já aplicada).
  Processamento roda em
  FastAPI `BackgroundTasks` (sem fila/Redis nesta fase). `confirm_receipt` usa
  update condicional (`is_ matched_transaction_id null`) pra evitar duplicar
  transaction em double-tap. Todas as chamadas ao Supabase (síncrono) rodam
  via `asyncio.to_thread` pra não bloquear o event loop — seguir esse padrão
  em qualquer endpoint novo que use `get_db()`.
- 🟡 **Spec 09 (contrato da API) — transactions + dashboard prontos.**
  `GET/POST/PATCH/DELETE /transactions` (paginação keyset por `(occurred_at, id)`,
  filtros month/category_id/type) e `/dashboard/summary` + `/dashboard/budget-rule`
  implementados de verdade. Decisões tomadas nesta leva:
  - **Health score** (`app/budget/health.py`): média das notas por bucket
    ponderada pelos percentuais 50-30-20 vigentes do household. Necessidades/
    desejos são teto (dentro = 100; cada 1% de estouro tira 1 ponto, dobro do
    teto zera); poupança é meta (proporcional ao atingido). Faixas: ≥80
    `saudavel`, ≥60 `atencao`, senão `risco`. Retorna `null` sem renda no mês.
    O `78` do protótipo é número inventado de mockup, não bate com a fórmula.
  - **budget_targets** é gerado sob demanda e persistido a partir de
    renda × budget_rules (`app/budget/targets.py::ensure_month_targets`) —
    **a spec 07 deve reusar essa função**, não reimplementar. Não sobrescreve
    target existente (o schema prevê override manual).
  - `aggregate_month()` é pura e compartilhada dashboard ↔ motor da spec 07.
  - Despesa **exige** `category_id`: sem categoria ela não cai em bucket e
    escaparia da regra 50-30-20. Gasto de categoria apagada (`on delete set
    null`) aparece em `uncategorized_expense`, nunca sumindo em silêncio.
  - Valores monetários sempre string decimal; nunca float (specs/09).
  - **Parcelamento expande no backend**: o cliente manda o valor **cheio** da
    compra + `installment_total` (máx. 12, só despesa), e
    `_build_installment_rows` cria uma transação por mês, com
    `split_installments` garantindo que a soma fecha exatamente com a compra
    (o resto vai na 1ª parcela) e `add_months` limitando dia 31 ao último dia
    do mês curto. **Não aceitar `installment_number` do cliente** — a primeira
    versão fazia isso e perdia 11 de 12 parcelas, deixando os meses seguintes
    falsamente livres.
  - `GET /notifications` (com `unread_count` contado à parte, não sobre a
    página) e `PATCH /notifications/{id}/read` implementados. Marcar como lida
    libera a chave de idempotência do motor, de propósito.
  - `GET /categories` criado (a spec 09 não previu, mas a tela precisa):
    padrão do sistema + as do household, ordenadas na sequência 50-30-20.
  - Ainda **stubs** (`NotImplementedError`): insights, reserva de emergência,
    gamificação, `POST /push-tokens` (precisa de tabela que não existe).
- ✅ **Import de extrato CSV/OFX** (`app/imports/`, spec nova `specs/11`) —
  virou a única ponte com o banco depois que Open Finance foi adiado.
  - Duas etapas: `POST /transactions/import` (multipart) devolve preview **sem
    gravar nada**, e `POST /transactions/import/confirm` grava as linhas que o
    usuário confirmou, cada uma com categoria. Preview é **stateless** — o
    cliente devolve as linhas, e o backend revalida tudo.
  - `parse_amount` decide o separador decimal contando dígitos: `1.234` em
    extrato é mil duzentos e trinta e quatro, não 1,234 — errar isso multiplica
    o valor por mil. `parse_date` cobre dd/mm/aaaa, ISO e o aaaammdd do OFX.
  - Dedupe: OFX tem `FITID` → `external_transaction_id` (`ofx:<id>`), bloqueado
    pela migration 0004. CSV não tem id, então duplicata é **avisada** no
    preview, nunca bloqueada — dois cafés iguais no mesmo dia são legítimos.
  - **Não usar `upsert` com `on_conflict` aqui**: o índice de dedupe é parcial e
    o Postgres não infere índice parcial de lista de colunas — `ON CONFLICT
    (cols)` falha a requisição inteira. O service filtra o que já existe antes
    e faz insert simples. A dedupe também roda **dentro do arquivo**, porque
    extrato com período sobreposto repete FITID.
  - `imports_router` é registrado **antes** de `transactions_router` no
    `main.py`: `/transactions/import` é caminho literal e precisa ganhar de
    `/transactions/{transaction_id}`.
  - **Validado contra extrato real** (Banco C6, 1.059 lançamentos, 12 meses),
    que derrubou duas decisões da spec original:
    - Pedir categoria item a item era inviável (951 despesas). O que resolve é
      **agrupar por comerciante** (`suggest.merchant_key`): ~170 grupos, sendo
      que os 10 maiores cobrem 521 lançamentos e ~44 cobrem 80%. Sugestão por
      palavra-chave cobre só **16%** — vale pelo que é de graça, não como
      solução. **Não trocar agrupamento por mais palavras-chave.**
    - Confirmar import reavalia alertas **só do mês corrente**: avaliar meses
      encerrados criava dezenas de alertas de risco retroativos, e num mês
      fechado a "projeção" é só o gasto que já aconteceu.
    - Princípio nas regras de sugestão: **melhor vazio que palpite errado** —
      sugestão errada que passa batida distorce o 50-30-20 em silêncio. Termo
      ambíguo fica fora; PIX/boleto/fatura não têm regra.
- ✅ **Backend do funil de import (regras aprendidas + um mês por vez).**
  Migration `0005_import_rules.sql`, `app/imports/rules.py`, `month` no
  `preview_import`. Ver `specs/11` (revisada) e
  `prototipo/13-import-variantes.html`. **Validado rodando contra o extrato real
  do C6**: 1.059/1.059 gravados, 205 regras aprendidas, sugestões saltando de 7
  no 1º mês para 46–69 nos seguintes, e reimportar dezembro dá
  `imported=0 skipped=102`. Decisões desta leva:
  - **Valida um mês, aprende, replica.** Cada escolha vira regra
    `merchant_key -> category_id` do household. Medido: **27 decisões no 1º mês**
    (dezembro), 18 no 2º, 8 a 29 nos demais. **Total 217 em qualquer ordem —
    aprender não cobra a mais.** Sem memória, mês a mês custaria mais que o
    dobro: era esse o desperdício, não o import incremental. **Não reintroduzir
    import mês a mês sem as regras salvas.**
  - **Ordem recente → antigo.** O painel do mês corrente vive na hora, e é o mês
    mais barato. Qualquer mês isolado cobre 58–72% do ano, então o desenho não
    depende de escolher "o mês certo".
  - **Regra do usuário ganha da palavra-chave.** `suggest.RULES` passa a ser só
    o palpite de quem nunca importou nada.
  - **Comerciante ambíguo não gera regra**, e **receita nunca gera regra**: a
    regra é só (comerciante → categoria), sem tipo, e aplicá-la a um PIX
    *recebido* jogaria entrada numa categoria de gasto.
  - **Lançamento sem descrição NÃO agrupa.** No extrato real são 49 despesas sem
    descrição alguma somando **R$ 115.177** (de R$ 0,02 a R$ 23.395), todas com
    `merchant_key` vazia. Uma escolha só jogaria isso tudo numa categoria — pior
    caso da regra de ouro. Custa +48 decisões no ano (169 → 217) e é o preço de
    não chutar. Chave vazia também pega descrição só de ruído (uma data,
    "Osasco OSASCO BRA"). O confirm **não aprende regra de chave vazia**.
  - **`needs_category` por grupo**: só despesa exige categoria. Sem a flag a tela
    cobraria decisão de grupo de entrada (3 dos 28 de dezembro).
  - `on_conflict` **é** seguro em `import_rules` (unique simples), diferente do
    insert de `transactions` (índice parcial). O `FakeDb` dos testes agora modela
    `on_conflict` de verdade — antes só dava append e escondia upsert quebrado.
  - **Bandeja "decidir depois"**: 129 comerciantes aparecem uma única vez no
    extrato real (muito PIX pra pessoa). Exigir categoria em todos travaria o
    usuário no lançamento que ele não lembra. O adiado **não é importado**; o
    mês entra incompleto e o app **avisa quantos ficaram de fora** — gasto não
    desaparece em silêncio.
  - **Item tirado do grupo é decisão nova, não descarte.** `merchant_key` usa 3
    palavras e sobre-agrupa ("BOLETO" junta energia, escola e plano de saúde).
    Tirar item cria unidade solta que exige a própria decisão. Invariante a
    testar: `resolvidos + adiados == total do mês`. A 1ª versão do protótipo
    errava isso e um lançamento evaporava com o import liberado.
  - **Interação escolhida: bandeja por categoria** (variante C das três
    prototipadas). Escolhe a categoria, marca tudo que pertence a ela, atribui
    em lote: até 9 rodadas em vez de 23 decisões. Barra de progresso conta
    **lançamentos** (79), não grupos (23).
  - **A bandeja "decidir depois" não precisa de backend**: o app simplesmente não
    manda essas linhas no confirm. E a segunda passada é de graça no OFX —
    reimportar o arquivo traz só o que ficou de fora, porque o já importado é
    barrado pelo FITID. **No CSV isso não vale** (sem id, duplicata é só avisada):
    furo aceito e não resolvido, por decisão do usuário de focar em OFX.
- ✅ **Tela de import de extrato** (`app/(app)/importar.tsx`) — fecha a spec 11
  ponta a ponta. Bandeja por categoria: escolhe a categoria, marca tudo que
  pertence a ela, atribui em lote. Entrada pela tela de adicionar, ao lado de
  "Escanear recibo". Usa `expo-document-picker` (SDK 57).
  - **A contabilidade mora em `lib/import-tray.ts`**, puro e sem import de
    client de API, porque é onde a invariante pode quebrar. Teste garante
    `resolvidos + adiados + órfãos == total` a cada passo, inclusive tirando
    item de grupo já adiado. **Não mover essa lógica pra dentro da tela.**
  - Adiar dá destino sem resolver, então não trava; o que trava é unidade sem
    destino nenhum. O adiado não é enviado no confirm.
  - **Falha ao salvar volta pra bandeja com as escolhas intactas.** Refazer 27
    decisões por queda de rede seria o pior desfecho. Já falha no preview volta
    pra escolha do arquivo — ao contrário do recibo, nada foi gravado.
  - A unidade carrega o **índice real** de cada item no grupo. A 1ª versão
    casava por (data, valor, descrição), e com dois lançamentos idênticos no
    mesmo grupo o `✕` mexia sempre no primeiro e depois não fazia nada.
  - `sumApiAmounts` (`lib/money.ts`) soma **em centavos pela string**: o total
    do backend deixa de valer quando um item sai do grupo, e recalcular com
    `Number()`/`toFixed` reintroduziria float em dinheiro.
  - **Pendência sua: aplicar a migration 0005 no Supabase à mão** antes de o
    app funcionar.
- ✅ **Spec 07 (motor de projeção/notificação)** — `app/notifications/engine.py`
  é a regra única, chamada pelo gatilho de evento (BackgroundTasks após
  create/update/**delete** de transaction) e pelo cron
  (`etl/projection_recompute.py`). Decisões desta leva:
  - **Aporte em poupança não é gasto.** `MonthTotals.consumption` (necessidades
    + desejos + sem categoria) é o que entra na projeção, e o dashboard expõe
    `cash_flow.expense` = consumo e `cash_flow.saved` = aporte, batendo com o
    protótipo ("Saiu R$ 6.130" + "Investido no mês R$ 1.200"). Somar aporte ao
    gasto fazia quem cumpre 50-30-20 levar alerta de risco todo mês, porque a
    saída planejada é exatamente 100% da renda. **Não reunir esses conceitos.**
  - **Projeção só a partir do dia 7** (`MIN_DAYS_FOR_PROJECTION`): antes disso
    uma despesa fixa do dia 1 projetaria ~30× ela mesma. O alerta de teto (95%)
    continua valendo desde o dia 1, porque compara valor real.
  - **goal_hit exige gasto > 0** no bucket: não dá pra distinguir "não gastou"
    de "não registrou", e parabenizar quem não abriu o app seria enganoso.
    Roda no cron do dia 1, avaliando o mês anterior (`closed=True`).
  - **Alertas de risco são reconciliados**: se a regra deixou de valer (usuário
    corrigiu o valor, apagou o gasto), o alerta não lido é apagado — senão fica
    na tela uma informação falsa. `goal_hit` nunca é retirado.
  - **Idempotência** via migration 0003: `notifications.reference_month` +
    `subject`, com índice único parcial em `read = false`. O schema original não
    tinha como expressar "mesmo alerta, mesmo mês, mesmo bucket".
  - `reserve_progress` ficou de fora: depende de `emergency_reserve.current_balance`,
    que nada ainda escreve — entra junto com o endpoint da reserva.
  - O cron importa `app.notifications.engine`, então o job precisa do pacote
    `grana-backend` instalado junto (o workflow já faz).
- ✅ **Spec 10 (onboarding de dados) — nova, escrita nesta leva.** Fecha a
  lacuna que a spec 04 deixou. Era o que destravava tudo: nada escrevia em
  `incomes`, então metas, health score e alertas ficavam todos dormentes.
  - **Renda é declaração com vigência**, não valor por mês: uma linha de
    `incomes` significa "a partir deste mês, minha renda é X", e vale até uma
    declaração mais nova. `get_month_income` pega a vigente por
    `(user_id, source)` — **não filtrar por igualdade de mês**, senão o app
    zera as metas todo dia 1.
  - Ao declarar renda nova, `budget_targets` é apagado **do mês em diante**
    (não só o mês), porque a renda vale dali pra frente e
    `ensure_month_targets` não sobrescreve o que já existe.
  - Onboarding é **pulável**; a Home mostra card "informe sua renda" enquanto
    `onboarding_complete` for false (derivado de ter renda vigente > 0).
  - `complete_onboarding` grava a renda **por último** de propósito: como
    `onboarding_complete` deriva dela, falha em passo anterior mantém o
    usuário pendente e o traz de volta, em vez de deixá-lo "concluído" e sem
    reserva pra sempre.
  - Reserva criada com baseline estimado (renda × % de necessidades), não
    perguntado. Multiplicador 6 (clt) / 12 (autônomo).
  - Endpoints novos: `GET /profile`, `POST /onboarding`, `GET|POST /incomes`.
  - Mobile: `app/(onboarding)/perfil.tsx` e `renda.tsx`. Campo de moeda guarda
    **centavos como dígitos** (`lib/money.ts`), nunca float — enviar
    `"8.000,00"` pro backend viraria erro de conversão.
  - **Jest configurado** no mobile (`npm test`, preset `jest-expo`) — a spec 01
    previa e faltava. Já no CI. `jest.setup.js` injeta env fictícia porque o
    client do Supabase é criado no import e recusa URL vazia.
  - Helpers puros ficam em módulos sem import de client de API
    (`lib/dates.ts`, `lib/money.ts`) — senão o teste quebra na coleta por
    falta de configuração de ambiente.
- ✅ **Tela de adicionar lançamento** (`app/(app)/adicionar.tsx`), desenhada em
  `prototipo/11-adicionar-v2.html` (o `10-adicionar.html` era um esboço
  incompleto: sem `0`, sem apagar, sem salvar, e com um "ditar por voz" que não
  existe em spec nenhuma). Teclado de centavos, categorias por tipo, e
  data/comerciante/parcelas em pills. O seletor de data precisa de tratamento
  por plataforma: no iOS é inline e dispara `onChange` a cada giro, então só o
  Android fecha sozinho.
- ✅ **Home real + navegação por abas.** `app/(app)/(tabs)/` com Início
  (consome `/dashboard/summary`: fluxo de caixa, 50-30-20 com barras, health
  score, gasto por categoria) e Atividade (`/transactions` agrupado por dia,
  com "carregar mais" usando o cursor). `adicionar` e `notificacoes` são telas
  empilhadas, não abas. Insights e Metas **não** viraram abas ainda: sem os
  endpoints, seriam abas vazias prometendo o que o app não faz.
  - Cada chamada da Home é independente, **não** use `Promise.all` aqui: com
    ele, uma falha isolada (ex: `/notifications` sem a migration 0003) apagava
    saldo, buckets e health score junto.
  - Distribuição por categoria saiu como barras, não donut: o donut exigiria
    `react-native-svg` e matemática de arco. Trocar depois é local.
- ✅ **Tela de recibo** (`app/(app)/recibo.tsx`) — fecha a spec 05 ponta a
  ponta: foto/galeria → `POST /receipts` (multipart via `authorizedFetch`, que
  não impõe Content-Type pro fetch gerar o boundary) → poll de
  `GET /receipts/{id}` (1,5s, teto de 20 tentativas) → revisão dos campos →
  `POST /receipts/{id}/confirm`.
  - **Falha no poll não volta pra tela de foto**: a imagem já subiu e o OCR já
    rodou, então mandar refotografar duplicaria o recibo e gastaria outro
    crédito do Mindee (são 200 no plano). Cai na revisão manual.
  - Campos com confiança baixa vêm `null` (specs/05) e o usuário preenche —
    o app não chuta valor.
  - `ReceiptConfirm` **não tem** campos de parcelamento de propósito: parcelar
    exige gerar N transações (ver `transactions/service.py`), e aceitar o
    total sem expandir repetiria o bug de perder as parcelas seguintes.
  - Valor do OCR passa por `numberToCents`, que arredonda: `19.99 * 100` dá
    1998.9999… em ponto flutuante e truncar tiraria um centavo.
  - `jest.setup.js` mocka o AsyncStorage — sem módulo nativo ele derruba o
    processo de teste assim que o Supabase tenta restaurar a sessão.
  - App renomeado de "mobile" pra **Grana** (`app.json`), antes de o EAS
    existir e amarrar o slug.
- 🛑 **Spec 06 (Open Finance/Pluggy) — ADIADA por barreira regulatória.**
  Ver `docs/adr/0001-open-finance-adiado.md`. Resumo: só instituição autorizada
  pelo BCB pode receber dados no Open Finance, e em março/2026 o BCB propôs
  restringir justamente a rota de parceria que a Pluggy oferecia a empresas não
  autorizadas (figuras de "instituição integradora" e "entidade parceira",
  modelo 1x1x1, capital de ITP de R$ 1 mi → R$ 17 mi). **Não implementar
  `PluggyProvider` nem `/accounts`.** O código fica dormente de propósito
  (interface, `MockProvider`, `etl/pluggy_sync.py`, tabela `accounts`,
  variáveis no `.env.example`) — custo zero e destrava rápido se a regra mudar.
  - Consequência: **o produto tem duas vias de registro, não três**, e o
    **import CSV/OFX virou a única ponte com o banco** — deixou de ser extra.
- ✅ **Reserva de emergência** (`app/reserve/`) — `GET|PATCH /emergency-reserve`.
  Alvo = gasto essencial × meses de colchão (6 clt / 12 autônomo). Decisões:
  - **`current_balance` entrou no PATCH**, que a spec 09 não previa. Sem ele nada
    escrevia o saldo, a reserva teria meta e nenhuma forma de dizer quanto já
    existe. **Não derivar do bucket "poupança"**: misturaria investimento de
    longo prazo com colchão e diria ao usuário que ele está coberto com dinheiro
    preso em ativo ilíquido. Manual é a via honesta hoje (Open Finance adiado).
  - **Baseline sugerido, nunca sobrescrito** — média de necessidades dos 3 meses
    fechados, mesmo espírito de `ensure_month_targets` não sobrescrever target
    manual. Só sugere com diferença ≥ 10%, senão vira ruído e o usuário aprende
    a ignorar. Ignora mês sem gasto ("não registrei" ≠ "não gastei").
  - Perfil e multiplicador andam **juntos**: "autônomo com 6 meses" não é
    escolha que a tela oferece e seria estado inconsistente.
  - `complete` exige `target > 0`: com baseline zerado, `0 >= 0` diria "reserva
    completa" pra quem não tem nada.
  - `GET` custa 4 consultas (a reserva + 3 meses da sugestão). Sabido, não
    otimizado — volume é de 1 household por usuário.
- ✅ **Alerta `reserve_progress`** — o que a spec 07 tinha adiado por falta de
  quem escrevesse o saldo. Marcos em 1/3/6/12 meses cobertos + meta batida.
  - Avaliado **no evento** (PATCH da reserva), não no cron: a reserva só muda
    quando o usuário diz que mudou.
  - `_create_once` cria o marco **uma vez na vida**. `_upsert_unread` chaveia por
    mês, o que é certo pra teto, mas faria o app reparabenizar todo dia 1.
  - Marco é conquista, então **não é reconciliado**, igual ao `goal_hit`: baixar
    o saldo depois não retira o "3 meses" que o usuário já viu.
  - Falha no alerta **não derruba o PATCH** — o saldo já foi gravado.
- ✅ **Segunda passada do import** — lançamento já importado (OFX, confirmado
  pelo FITID) não pede categoria, não é reenviado no confirm, e a tela oferece
  esconder. Sem isso, reimportar o arquivo pelos adiados **travava o botão**
  pedindo categoria de coisa que já estava no banco.
  - **Exige `external_id`**: no CSV `likely_duplicate` é palpite por
    data+valor+descrição, e tratar palpite como fato descartaria gasto real em
    silêncio. Dois cafés iguais no mesmo dia são legítimos.
- ⏳ Spec 08 (push) — não iniciada.
- ✅ **Insights** (`app/insights/`) — os 5 endpoints da spec 09. O fio condutor
  é que **toda comparação com o mês corrente mente por omissão**, porque o mês
  está incompleto; cada função trata isso explicitamente.
  - `month-over-month` **corta os dois meses no mesmo dia** quando o mês de
    referência está em curso. Sem isso, dia 5 compararia 5 dias contra 31 e o
    app anunciaria "você gastou 80% menos" todo começo de mês. Responde
    `partial` e `comparable_days`. `delta_pct` é **null** quando o mês anterior
    foi zero — "aumento de 100%" a partir de nada seria invenção.
  - `by_category` ordena por **variação absoluta**, não percentual: 200% em algo
    de R$ 3 não é notícia, R$ 400 a mais no mercado é.
  - `recurring-subscriptions` **detecta das transações**, não da tabela
    `recurring_subscriptions` — nada escreve nela, e ler dela devolveria lista
    vazia pra sempre. Reusa `merchant_key` do import. Regra: ≥3 meses distintos
    + valor estável (tolerância 15%, porque assinatura reajusta). Cancelada é
    listada com `active: false` e **fora** do `monthly_total`.
    - **Falso positivo conhecido**: no extrato real, posto de gasolina com
      R$ 100,00 exatos em 3 meses virou "assinatura". Não corrigido de
      propósito — dia-do-mês como sinal extra cortaria assinatura de cobrança
      variável, e aqui o custo do erro é uma olhada, não um bucket errado.
  - `top-transactions` **exclui aporte** e informa quanto excluiu
    (`excluded_savings`), em vez de sumir com ele: um aporte grande seria o
    "maior gasto" do mês sem ser gasto. Devolve `merchant: null` em lançamento
    sem descrição — **a tela precisa de um rótulo**, não linha em branco.
  - `three-month-average` usa meses **fechados** e ignora mês sem gasto ("não
    registrei" ≠ "não gastei", igual ao `goal_hit` e ao baseline da reserva).
    Não devolve percentual do mês corrente contra a média: no dia 10 estar
    "40% abaixo" é sempre verdade e nunca útil — pra isso existe a projeção.
  - `health-score-breakdown` reusa `compute_health_score` (a nota não pode ser
    calculada de dois jeitos), marca cada bucket como `ceiling` ou `goal`, e sem
    renda devolve **200 com `reason: "sem_renda"`**, não 404 — a tela precisa
    explicar, não errar. Expõe `uncategorized_expense`, que não pontua nem pune.
  - **Aporte fora de todos os cinco.** Um investimento mensal de valor fixo
    passa em todo teste de recorrência e entraria no `monthly_total` que a tela
    chama de custo fixo. Foi achado do code-review, não do desenho.
- ⏳ Gamificação (spec 09) — **parada em decisão do usuário sobre a regra de XP**
  (quanto vale registrar vs quanto vale bater a meta).

## Próximos passos sugeridos (retomar por aqui)

1. **Endpoints de insights** (spec 09) — 5 endpoints, nenhum existe. Junto com
   a reserva, é o que faz as abas Insights e Metas deixarem de ser promessa.
2. **Endpoints da reserva de emergência** (spec 09) — destrava também o alerta
   `reserve_progress`, que ficou de fora da spec 07 porque nada escreve em
   `emergency_reserve.current_balance`.
3. **Gamificação e cofrinho** (spec 09) — precisa de decisão sobre a regra de XP
   antes de codar.
4. **Filtro de "já importado" no preview** (task #33, baixa) — na segunda
   passada o usuário reimporta o arquivo e rola 100 linhas pra achar 5. A linha
   já diz "já importado"; falta poder esconder o resto.
5. Push notifications — precisa de tabela `push_tokens`, que não existe, e do
   projeto Expo/EAS nascer (spec 08).
6. Open Finance/Pluggy — **bloqueado por regulação**, não retomar sem revisitar
   `docs/adr/0001-open-finance-adiado.md` e confirmar a norma final do BCB.

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
