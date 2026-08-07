from decimal import Decimal

from pydantic import BaseModel, field_validator

INCOME_PROFILES = ("clt", "autonomo")

# Multiplicador da reserva de emergência (specs/10): autônomo precisa de mais
# meses de colchão porque a renda é instável.
RESERVE_MONTHS = {"clt": 6, "autonomo": 12}


class OnboardingPayload(BaseModel):
    income_profile: str
    monthly_income: Decimal

    @field_validator("income_profile")
    @classmethod
    def profile_must_be_known(cls, value: str) -> str:
        if value not in INCOME_PROFILES:
            raise ValueError(f"Perfil inválido. Use um de: {', '.join(INCOME_PROFILES)}.")
        return value

    @field_validator("monthly_income")
    @classmethod
    def income_must_be_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("A renda precisa ser maior que zero.")
        return value


class IncomeCreate(BaseModel):
    amount: Decimal
    # Default = mês corrente, resolvido no service (precisa do fuso do app).
    effective_month: str | None = None
    source: str = "salario"

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("A renda precisa ser maior que zero.")
        return value
