# Spec: adaptador de Open Finance (Pluggy)

## Interface (`apps/backend/app/providers/bank_aggregator/base.py`)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ExternalTransaction:
    external_id: str
    amount: float
    occurred_at: str
    merchant: str | None
    installment_number: int | None
    installment_total: int | None
    raw_payload: dict

class BankAggregatorProvider(ABC):
    @abstractmethod
    async def create_connect_token(self, user_id: str) -> str:
        """Token de uso único pro widget de conexão do banco no app."""

    @abstractmethod
    async def sync_transactions(self, item_id: str, since: str) -> list[ExternalTransaction]:
        ...

    @abstractmethod
    async def get_connection_status(self, item_id: str) -> str:
        """'active' | 'error' | 'disconnected'"""
```

## `PluggyProvider`
- `create_connect_token`: chama a API do Pluggy pra gerar o token do Pluggy Connect (widget de login bancário que roda no app).
- Fluxo de consentimento: usuário conecta pelo widget → Pluggy retorna um `item_id` → backend salva em `accounts.external_item_id`, `provider = 'pluggy'`.
- `sync_transactions`: busca transações do item desde a última sincronização (`accounts.last_synced_at`), mapeia pro formato `ExternalTransaction`.
- Dedupe: `transactions.external_transaction_id` + `unique(account_id, external_transaction_id)` no schema já impede duplicata em upsert — o service layer deve usar `ON CONFLICT DO NOTHING` (ou `DO UPDATE` se o Pluggy corrigir um valor retroativamente).
- Erros tratados: item com erro de credencial (usuário precisa reconectar — marca `accounts.status = 'error'`, gera notification pro usuário), rate limit da API.

## `MockProvider`
- `create_connect_token` retorna um token fake; `sync_transactions` retorna uma lista fixa de transações de exemplo.
- Ativo quando `PLUGGY_CLIENT_ID`/`PLUGGY_CLIENT_SECRET` não configurados (task #3 pendente).

## Sync — evento vs cron
Reaproveita o padrão híbrido já decidido pra projeção (spec 07):
- Evento: sync imediato disparado quando o usuário conecta a conta pela primeira vez.
- Cron: sync diário (via `etl/pluggy_sync.py`, registrado em `etl_runs`) pra todas as contas ativas, pegando transações novas desde `last_synced_at`.

## Preparo pro cofrinho de arredondamento automático (backlog, não desta spec)
Quando a automação completa de transferência entrar em escopo, ela precisa do Pluggy atuando como iniciador de pagamento (ITP), não só leitura — é uma interface adicional (`PaymentInitiatorProvider`), fora do escopo desta spec.

## Seleção de provider
Variável de ambiente `BANK_AGGREGATOR_PROVIDER=pluggy|mock`, mesma factory pattern da spec 05.
