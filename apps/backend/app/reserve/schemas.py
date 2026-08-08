from decimal import Decimal

from pydantic import BaseModel, field_validator, model_validator

from app.profile.schemas import INCOME_PROFILES


class ReserveUpdate(BaseModel):
    """Todos os campos são opcionais: a tela edita um de cada vez.

    `current_balance` não estava no contrato original da spec 09, que previa só
    `profile` e `essential_expenses_baseline`. Ele entrou porque sem ele nada
    escreve `emergency_reserve.current_balance` — a reserva teria meta e nenhuma
    forma de dizer quanto já existe, e o alerta `reserve_progress` da spec 07
    ficaria dormente pra sempre.

    Informar à mão é a única via honesta hoje: derivar do bucket "poupança"
    misturaria investimento de longo prazo com colchão de emergência, e diria ao
    usuário que ele está coberto com dinheiro preso em ativo ilíquido. Mesma
    razão de o cofrinho ser manual (Open Finance adiado, ver a ADR 0001).
    """

    profile: str | None = None
    essential_expenses_baseline: Decimal | None = None
    current_balance: Decimal | None = None

    @field_validator("profile")
    @classmethod
    def profile_must_be_known(cls, value: str | None) -> str | None:
        if value is not None and value not in INCOME_PROFILES:
            raise ValueError(f"Perfil inválido. Use um de: {', '.join(INCOME_PROFILES)}.")
        return value

    @field_validator("essential_expenses_baseline")
    @classmethod
    def baseline_must_be_positive(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= 0:
            raise ValueError("O gasto essencial precisa ser maior que zero.")
        return value

    @field_validator("current_balance")
    @classmethod
    def balance_cannot_be_negative(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("O saldo da reserva não pode ser negativo.")
        return value

    @model_validator(mode="after")
    def at_least_one_field(self):
        if (
            self.profile is None
            and self.essential_expenses_baseline is None
            and self.current_balance is None
        ):
            raise ValueError("Informe pelo menos um campo para alterar.")
        return self
