# Spec: adaptador de OCR de recibo (Mindee)

## Interface (`apps/backend/app/providers/receipt_ocr/base.py`)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ExtractedReceipt:
    merchant: str | None
    amount: float | None
    occurred_at: str | None  # ISO date
    category_hint: str | None
    raw_payload: dict

class ReceiptOcrProvider(ABC):
    @abstractmethod
    async def extract(self, image_bytes: bytes) -> ExtractedReceipt:
        ...
```

Nenhum outro módulo do backend importa o SDK do Mindee diretamente — todos dependem de `ReceiptOcrProvider`.

## `MindeeProvider`
- Usa o endpoint de recibo do Mindee (`client.parse(mindee.product.ReceiptV5, ...)`).
- Mapeia o response do Mindee pros campos de `ExtractedReceipt`. Guarda o JSON bruto do Mindee inteiro em `raw_payload` (vira `receipts.extracted_payload` no banco).
- Erros tratados: chave inválida (401), limite de cota excedido (402/429), imagem ilegível (Mindee retorna confidence baixo em vez de erro — nesse caso, os campos vêm `null` e o app deve pedir confirmação manual em vez de rejeitar).

## `MockProvider`
- Retorna um `ExtractedReceipt` fixo/determinístico (ex: baseado num hash da imagem, pra simular variação em teste), sem chamar rede.
- Usado quando `MINDEE_API_KEY` não está configurada (task #2 ainda pendente) — o backend deve logar um aviso claro ("usando mock de OCR, configure MINDEE_API_KEY") em vez de falhar silenciosamente.

## Fluxo completo (ver também spec 07 — job de projeção)
1. App envia foto → backend salva em Supabase Storage → cria `receipts` com `status = 'pending'`.
2. Backend chama `provider.extract()` de forma assíncrona (fila ou background task do FastAPI).
3. Ao terminar: atualiza `receipts.status = 'processed'`, grava `extracted_payload`.
4. App mostra os campos extraídos pro usuário confirmar (nunca cria a `transaction` direto sem confirmação — mitiga erro de OCR).
5. Ao confirmar, cria a `transaction` com `entry_method = 'receipt_ocr'` e `receipt_id` apontando pro recibo. Só **neste momento** — não antes — o valor entra no cálculo de projeção (ver spec 07).

## Seleção de provider
Variável de ambiente `RECEIPT_OCR_PROVIDER=mindee|mock`, resolvida por uma factory simples em `providers/receipt_ocr/__init__.py`. Trocar de fornecedor no futuro (Textract, Veryfi) = escrever um novo adaptador + trocar essa variável, sem tocar em service/router.
