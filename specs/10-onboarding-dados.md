# Spec: onboarding de dados (renda + perfil)

Fecha a lacuna deixada pela spec 04 ("telas ainda não especificadas, ficam pra
depois"). É o que destrava a regra 50-30-20: sem renda cadastrada,
`ensure_month_targets` não deriva teto nenhum, o health score fica `null` e o
motor de alertas (spec 07) sai sem fazer nada.

## O que é coletado

| Campo | Onde grava | Observação |
|---|---|---|
| Renda mensal | `incomes` (amount, effective_month, source='salario') | Ver "renda vigente" abaixo |
| Perfil | `profiles.income_profile` (`clt`/`autonomo`) | Define o multiplicador da reserva |
| — | `emergency_reserve` | Criado junto, derivado (ver abaixo) |

Os percentuais 50-30-20 **não** entram aqui: o household já nasce com o
default via trigger de cadastro, e editar isso é tela de configuração.

## Renda vigente (decisão fechada)

Uma linha de `incomes` é uma **declaração**: "a partir do mês X, minha renda é
Y". A renda de um mês é a declaração mais recente com
`effective_month <= mês consultado`, por `(user_id, source)`.

- Informou R$ 8.000 em janeiro → fevereiro, março... continuam R$ 8.000.
- Declarou R$ 9.000 em março → janeiro e fevereiro seguem 8.000; março em diante, 9.000.

Motivo: salário CLT não muda todo mês. Sem isso, o app zeraria as metas todo
dia 1 até o usuário lembrar de preencher de novo.

Consequência: `get_month_income` não pode filtrar por igualdade de mês — pega a
declaração vigente. Autônomo que quiser variar mês a mês é só declarar cada mês.

## Reserva de emergência

Criada no onboarding, derivada em vez de perguntada (o usuário raramente sabe
responder "quanto você gasta com o essencial?"):

```
months_multiplier = 6 (clt) | 12 (autonomo)
essential_expenses_baseline = renda * (necessidades_pct / 100)   # 50% por padrão
alvo = essential_expenses_baseline * months_multiplier
```

O baseline passa a usar a média real de gastos em `necessidades` quando houver
histórico — fora do escopo desta spec, entra com o endpoint da reserva.

`current_balance` continua 0: nada ainda o alimenta (por isso o alerta
`reserve_progress` segue adiado, ver spec 07).

## Pode pular

O onboarding é **pulável**. Quem pula entra no app normalmente; a Home mostra
um card "informe sua renda pra ver suas metas" enquanto não houver renda
vigente. O backend já trata renda ausente sem quebrar.

## Endpoints

- `GET /profile` — estado atual: `full_name`, `income_profile`,
  `current_income` (renda vigente do mês corrente, ou `null`),
  `onboarding_complete`.
- `POST /onboarding` — completa o fluxo numa chamada:
  `{ income_profile, monthly_income }`. Grava `profiles.income_profile`,
  cria a declaração de renda do mês corrente e cria/atualiza
  `emergency_reserve`.
- `POST /incomes` — declara nova renda depois (mudou de salário):
  `{ amount, effective_month?, source? }`. `effective_month` default = mês
  corrente; `source` default = `salario`.
- `GET /incomes` — histórico de declarações, pra tela de edição.

## Recalcular metas quando a renda muda

`budget_targets` é materializado (spec 07). Ao declarar renda nova para o mês
M, os targets de M são **apagados** para que `ensure_month_targets` os gere de
novo com o valor certo — senão o dashboard continuaria mostrando o teto do
salário antigo.

> Pendência conhecida: hoje não dá pra distinguir target gerado
> automaticamente de target sobrescrito à mão, então a regeneração apagaria um
> override manual. Quando o override manual virar feature de verdade, vai
> precisar de uma flag (`is_manual`) em `budget_targets`.

## Telas (mobile)

1. **Perfil** — "Você é CLT ou autônomo?" (duas opções grandes). Explica em uma
   linha que isso define o tamanho da reserva de emergência (6 ou 12 meses).
2. **Renda** — "Quanto você recebe por mês?" com campo de moeda. Texto de apoio:
   "Pode mudar depois, e não precisa ser exato."
3. Botão "Pular por enquanto" nas duas, indo direto pra Home.

Referência visual: mesmo estilo do `prototipo/04-cadastro.html` (fundo escuro,
botão âmbar, texto de apoio em cinza).

## Fora de escopo

- Múltiplas fontes de renda na mesma tela (o schema suporta via `source`, mas o
  onboarding só cadastra `salario`).
- Edição/remoção de declarações antigas.
- Baseline da reserva por média histórica real.
