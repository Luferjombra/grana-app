from decimal import Decimal

from pydantic import BaseModel, model_validator


class BudgetRuleUpdate(BaseModel):
    necessidades_pct: Decimal
    desejos_pct: Decimal
    poupanca_pct: Decimal

    @model_validator(mode="after")
    def percentages_must_sum_to_100(self):
        # O banco tem a mesma constraint (pct_sum_100); validar aqui devolve
        # 422 com mensagem legível em vez de estourar erro do Postgres.
        total = self.necessidades_pct + self.desejos_pct + self.poupanca_pct
        if total != Decimal("100"):
            raise ValueError("Os percentuais precisam somar 100.")
        if min(self.necessidades_pct, self.desejos_pct, self.poupanca_pct) < 0:
            raise ValueError("Percentuais não podem ser negativos.")
        return self
