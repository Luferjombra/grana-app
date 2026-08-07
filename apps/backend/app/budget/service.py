import asyncio
from decimal import Decimal

from app.auth import CurrentUser
from app.budget import targets as targets_module
from app.budget.health import compute_health_score
from app.budget.schemas import BudgetRuleUpdate
from app.common import BUCKETS, money, parse_month, to_decimal
from app.db import get_db


async def get_dashboard_summary(current_user: CurrentUser, month: str) -> dict:
    household_id = current_user.household_id
    month_start = parse_month(month)

    rows = await targets_module.fetch_month_transactions(household_id, month_start)
    totals = targets_module.aggregate_month(rows)

    month_targets = await targets_module.ensure_month_targets(household_id, month_start)
    rule = await targets_module.get_budget_rule(household_id)
    health = compute_health_score(rule, totals.by_bucket, month_targets)

    distribution = sorted(
        totals.by_category.values(), key=lambda item: item["amount"], reverse=True
    )
    for entry in distribution:
        share = (entry["amount"] / totals.expense * 100) if totals.expense > 0 else Decimal("0")
        entry["percentage"] = str(share.quantize(Decimal("0.1")))
        entry["amount"] = money(entry["amount"])

    return {
        "month": month,
        # "expense" é consumo (o "Saiu" do protótipo) e "saved" é o aporte
        # ("Investido no mês"), separados de propósito: somar aporte ao gasto
        # faria parecer que quem cumpre a meta 50-30-20 está no vermelho.
        "cash_flow": {
            "income": money(totals.income),
            "expense": money(totals.consumption),
            "saved": money(totals.saved),
            "net": money(totals.income - totals.expense),
        },
        "by_category": distribution,
        "uncategorized_expense": money(totals.uncategorized_expense),
        "buckets": [
            {
                "bucket": bucket,
                "spent": money(totals.by_bucket[bucket]),
                "target": money(month_targets[bucket]) if bucket in month_targets else None,
            }
            for bucket in BUCKETS
        ],
        "health_score": health,
    }


async def get_budget_rule(current_user: CurrentUser) -> dict:
    rule = await targets_module.get_budget_rule(current_user.household_id)
    return {
        "necessidades_pct": str(to_decimal(rule["necessidades_pct"])),
        "desejos_pct": str(to_decimal(rule["desejos_pct"])),
        "poupanca_pct": str(to_decimal(rule["poupanca_pct"])),
    }


async def update_budget_rule(current_user: CurrentUser, data: BudgetRuleUpdate) -> dict:
    query = (
        get_db()
        .table("budget_rules")
        .upsert(
            {
                "household_id": current_user.household_id,
                "necessidades_pct": str(data.necessidades_pct),
                "desejos_pct": str(data.desejos_pct),
                "poupanca_pct": str(data.poupanca_pct),
            },
            on_conflict="household_id",
        )
    )
    await asyncio.to_thread(query.execute)
    return await get_budget_rule(current_user)
