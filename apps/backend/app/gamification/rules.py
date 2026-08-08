"""Regra de XP (specs/09, decidida em 08/08/2026 com Duolingo, Habitica e
Fortune City como balizadores).

O risco central de gamificar um app de finanças é **premiar o comportamento que o
app existe pra reduzir**. No Grana você registra um lançamento quando gasta
dinheiro, então XP por lançamento faria quem compra 30 cafés ganhar dez vezes
mais que quem compra 3 — o app celebrando quem gasta mais.

Não é hipótese: é o mecanismo pelo qual a Robinhood foi processada por
Massachusetts (acordo de ~US$ 7,5 mi e remoção das features), e a FCA mediu push
aumentando volume de negociação em 11% e sorteio em 12%.

Por isso, três regras que **não são negociáveis**:

1. XP de hábito por **dia ativo**, no máximo 1 por dia — nunca por lançamento.
   É o teto diário do Fortune City (máx. 5 prédios/dia) aplicado onde importa.
2. **Sem ranking entre pessoas.** Idioma dá pra comparar; gasto é vergonha.
3. **Sem punição.** O app pode deixar de premiar; nunca cobrar. Streak não zera
   (specs/10 já decidiu "dias ativos no mês", sem quebra).

"Dia ativo" usa `transactions.created_at`, não `occurred_at`: é o dia em que a
pessoa **usou o app**. Com `occurred_at`, importar um extrato de 12 meses daria
~30 dias ativos de uma vez; com `created_at`, o import inteiro conta como 1.
"""

from decimal import ROUND_CEILING, Decimal

from app.common import BUCKETS

# XP por dia em que o usuário registrou algo. Registrar 1 ou 30 lançamentos no
# mesmo dia rende igual — é isso que mata o incentivo perverso.
XP_PER_ACTIVE_DAY = 10

# Pool distribuído entre os buckets batidos no fechamento do mês, na proporção
# dos percentuais 50-30-20 **vigentes do household**: se o usuário editar os
# percentuais, o XP acompanha sem código novo.
#
# 300 é escolhido pra empatar com o teto do hábito (30 dias × 10), então o
# equilíbrio ~50/50 entre hábito e resultado é consequência dos tetos, não um
# percentual decidido a dedo que ninguém sabe defender depois.
RESULT_XP_POOL = 300

# Um nível por mês perfeito (300 de hábito + 300 de resultado). É a única curva
# que dá pra explicar ao usuário numa frase.
XP_PER_LEVEL = 600


def habit_xp(active_days: int) -> int:
    """XP de hábito. `active_days` já vem contado por dia distinto."""
    return max(active_days, 0) * XP_PER_ACTIVE_DAY


def buckets_met(spent: dict[str, Decimal], targets: dict[str, Decimal]) -> list[str]:
    """Buckets em ordem no fechamento do mês.

    necessidades/desejos são **teto**: cumprir é ficar dentro. poupança é
    **meta**: cumprir é chegar lá.

    Teto exige gasto > 0, mesma leitura do `goal_hit` da spec 07: não dá pra
    distinguir "não gastou" de "não registrou", e premiar quem passou o mês sem
    abrir o app seria enganoso.
    """
    met = []
    for bucket in BUCKETS:
        target = targets.get(bucket)
        if target is None or target <= 0:
            continue
        value = spent.get(bucket, Decimal("0"))

        if bucket == "poupanca":
            if value >= target:
                met.append(bucket)
        elif Decimal("0") < value <= target:
            met.append(bucket)
    return met


def result_xp(met: list[str], rule: dict) -> int:
    """Pool × peso de cada bucket batido, usando os percentuais do household."""
    if not met:
        return 0

    total = Decimal("0")
    for bucket in met:
        weight = Decimal(str(rule.get(f"{bucket}_pct", 0)))
        total += Decimal(RESULT_XP_POOL) * weight / Decimal("100")
    return int(total.to_integral_value())


def level_for(total_xp: int) -> int:
    """Nível 1 começa em zero: ninguém entra no app já em nível 0."""
    return max(total_xp, 0) // XP_PER_LEVEL + 1


def xp_into_level(total_xp: int) -> tuple[int, int]:
    """(XP dentro do nível atual, XP que o nível custa) — pra barra de progresso."""
    return max(total_xp, 0) % XP_PER_LEVEL, XP_PER_LEVEL


def roundup_of(amount: Decimal) -> Decimal:
    """Troco do arredondamento pra cima, até o real inteiro.

    Valor já inteiro rende **zero**, não um real: cobrar arredondamento de quem
    gastou R$ 20,00 exatos seria inventar uma despesa.
    """
    if amount <= 0:
        return Decimal("0.00")
    ceiling = amount.to_integral_value(rounding=ROUND_CEILING)
    return (ceiling - amount).quantize(Decimal("0.01"))


def active_days_from(created_ats: list[str]) -> int:
    """Dias distintos em que houve registro. Recebe timestamps ISO de
    `transactions.created_at` e olha só a parte da data."""
    return len({value[:10] for value in created_ats if value})
