"""Regras de categorização aprendidas no import (specs/11).

Agrupar por comerciante derruba 951 despesas para 169 decisões, mas 169 numa
sentada só é inviável no celular. O que resolve é **guardar a decisão**: cada
categoria escolhida vira uma regra `merchant_key -> category_id` do household,
aplicada aos outros meses do mesmo arquivo e aos próximos extratos.

Medido no extrato real de 12 meses: o 1º mês custa 23 escolhas e os seguintes
chegam com 70-92% já resolvido. O total é o mesmo (169) em qualquer ordem —
aprender não cobra a mais, só antecipa o valor.

A regra do usuário **ganha** de `suggest.RULES`, que passa a ser só o palpite
inicial de quem nunca importou nada.
"""

import asyncio
from collections import defaultdict
from datetime import UTC, datetime

from app.auth import CurrentUser
from app.db import get_db
from app.imports.suggest import merchant_key

# Regra só vale pra despesa. Uma regra é só (comerciante -> categoria), sem
# guardar tipo, e aplicar "PIX ANA BEATRIZ -> Moradia" a um PIX *recebido* da
# mesma pessoa jogaria uma receita numa categoria de gasto. Receita no extrato é
# pouca e quase sempre salário, então não vale a complexidade de versionar a
# regra por tipo.
RULE_TYPE = "expense"


async def load_rules(current_user: CurrentUser) -> dict[str, int]:
    """Regras do household, como {merchant_key: category_id}."""
    query = (
        get_db()
        .table("import_rules")
        .select("merchant_key, category_id")
        .eq("household_id", current_user.household_id)
    )
    result = await asyncio.to_thread(query.execute)
    return {row["merchant_key"]: row["category_id"] for row in (result.data or [])}


def rules_from_rows(rows) -> dict[str, int]:
    """Deriva as regras a aprender a partir das linhas confirmadas.

    **Comerciante com mais de uma categoria não gera regra.** O usuário pode
    tirar um item de um grupo e dar outra categoria a ele — é o caso do "BOLETO",
    que junta energia, escola e plano de saúde porque `merchant_key` usa só as 3
    primeiras palavras. As duas linhas têm a mesma chave, e gravar a última
    escolhida criaria uma regra que erra em silêncio nos próximos meses.

    Mesmo princípio do resto do módulo de import: melhor não sugerir do que
    sugerir errado (specs/11).
    """
    by_key: dict[str, set[int]] = defaultdict(set)

    for row in rows:
        if row.type != RULE_TYPE or row.category_id is None:
            continue
        key = merchant_key(row.description or "")
        if key:
            by_key[key].add(row.category_id)

    return {key: cats.pop() for key, cats in by_key.items() if len(cats) == 1}


async def save_rules(current_user: CurrentUser, mapping: dict[str, int]) -> int:
    """Grava as regras, sobrescrevendo a do mesmo comerciante.

    Aqui o `on_conflict` **é** seguro, diferente do insert de transactions: o
    índice `import_rules_household_merchant` é unique simples, então o Postgres
    infere o alvo a partir da lista de colunas. O de transactions é parcial (só
    onde `external_transaction_id` não é nulo) e não pode ser inferido assim —
    ver o comentário em `service.py`.
    """
    if not mapping:
        return 0

    # updated_at explícito: o default `now()` da coluna só roda no INSERT, então
    # numa regra sobrescrita ele ficaria congelado na data da primeira escolha.
    now = datetime.now(UTC).isoformat()
    payload = [
        {
            "household_id": current_user.household_id,
            "merchant_key": key,
            "category_id": category_id,
            "updated_at": now,
        }
        for key, category_id in sorted(mapping.items())
    ]

    query = get_db().table("import_rules").upsert(payload, on_conflict="household_id,merchant_key")
    result = await asyncio.to_thread(query.execute)
    return len(result.data or [])
