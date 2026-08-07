# Spec: import de extrato (CSV/OFX)

Com Open Finance adiado (`docs/adr/0001-open-finance-adiado.md`), este import
deixou de ser conveniência e passou a ser **a única ponte com o banco**.

## Fluxo em duas etapas

O import nunca grava direto: o usuário revisa antes.

1. `POST /transactions/import` — multipart com o arquivo. **Não persiste nada.**
   Devolve o preview: linhas lidas, tipo inferido, e marcação do que parece
   duplicado.
2. `POST /transactions/import/confirm` — recebe as linhas que o usuário
   confirmou, cada uma **com categoria**, e cria as transactions em lote.

Preview é **stateless**: o cliente devolve as linhas na confirmação, em vez de
o servidor guardar o lote numa tabela temporária. Evita uma migration e um
job de limpeza de lotes abandonados; o backend revalida tudo na confirmação,
então não há risco em confiar no que volta.

## Formatos

### OFX
Padrão bancário com estrutura fixa. Cada transação tem `FITID`, único por
instituição — vai pra `transactions.external_transaction_id` prefixado
(`ofx:<FITID>`) e é **bloqueado** por índice único: reimportar o mesmo extrato
não duplica nada.

### CSV
Cada banco usa colunas e separador diferentes, então o parser detecta:
- separador `,` ou `;`
- coluna de data, valor e descrição por nome normalizado do cabeçalho
- número em formato brasileiro (`1.234,56`) ou americano (`1234.56`)

CSV **não** recebe `external_transaction_id`: sem id do banco, a única chave
seria data+valor+descrição, e dois cafés iguais no mesmo dia são legítimos.
Duplicata em CSV é **avisada no preview**, não bloqueada — o usuário decide.

## Sinal e tipo

Extrato usa negativo para débito. O schema guarda `amount` sempre positivo com
o sinal em `type`:

```
valor < 0  -> type = 'expense', amount = abs(valor)
valor > 0  -> type = 'income',  amount = valor
valor = 0  -> linha descartada
```

## Categoria é obrigatória na confirmação

O extrato traz a descrição do banco ("PIX ENVIADO JOAO"), não categoria. Como
despesa sem categoria escapa da regra 50-30-20 (ver `specs/09` e o histórico do
`CLAUDE.md`), a confirmação **exige** `category_id` em cada despesa. O preview
é onde o usuário escolhe.

Não há adivinhação por palavra-chave nesta versão: erraria e exigiria manter
uma lista de regras.

## Detalhe de schema corrigido junto

O schema tinha `unique (account_id, external_transaction_id)`, desenhado para o
Pluggy, em que `account_id` existe. No import não há conta, então `account_id`
fica null — e no Postgres nulos são distintos, o que **anula** essa proteção.

A migration `0004` acrescenta índice único parcial por household:

```sql
create unique index transactions_household_external_id
  on transactions (household_id, external_transaction_id)
  where external_transaction_id is not null;
```

## Limites

- Arquivo até 5 MB e 2.000 linhas por import: acima disso o preview fica
  impraticável de revisar na mão, que é o ponto do fluxo.
- `entry_method = 'csv_import'` em tudo que vem daqui (valor já previsto no
  check do schema).

## Fora de escopo

- Categorização automática por palavra-chave.
- Import incremental por conta (depende de `accounts`, que só faz sentido com
  Open Finance).
- PDF de extrato.
