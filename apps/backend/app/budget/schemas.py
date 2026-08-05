from pydantic import BaseModel


class BudgetRuleUpdate(BaseModel):
    necessidades_pct: str
    desejos_pct: str
    poupanca_pct: str
