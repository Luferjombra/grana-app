# Spec: seed de categorias padrão

## Objetivo
Popular `categories` com `household_id = null` e `is_default = true` (visíveis para todo household, conforme policy da spec 02).

## Lista final (do protótipo, sem alterações)

| Categoria | Bucket | Ícone (Tabler) |
|---|---|---|
| Moradia | necessidades | `ti-home` |
| Mercado | necessidades | `ti-shopping-cart` |
| Contas | necessidades | `ti-file-invoice` |
| Transporte | necessidades | `ti-bus` |
| Lazer | desejos | `ti-ticket` |
| Compras | desejos | `ti-shopping-bag` |
| Delivery | desejos | `ti-package` |
| Streaming | desejos | `ti-device-tv` |
| Investimentos | poupanca | `ti-trending-up` |

## Script de seed

```sql
insert into categories (household_id, name, bucket, icon, is_default) values
  (null, 'Moradia',       'necessidades', 'ti-home',          true),
  (null, 'Mercado',       'necessidades', 'ti-shopping-cart', true),
  (null, 'Contas',        'necessidades', 'ti-file-invoice',  true),
  (null, 'Transporte',    'necessidades', 'ti-bus',           true),
  (null, 'Lazer',         'desejos',      'ti-ticket',        true),
  (null, 'Compras',       'desejos',      'ti-shopping-bag',  true),
  (null, 'Delivery',      'desejos',      'ti-package',       true),
  (null, 'Streaming',     'desejos',      'ti-device-tv',     true),
  (null, 'Investimentos', 'poupanca',     'ti-trending-up',   true);
```

## Comportamento esperado no app
- Todo household enxerga essas 9 categorias por padrão (via policy `household_id is null or household_id in (...)`).
- Usuário pode criar categoria própria (`household_id` preenchido, `is_default = false`) — não pode editar/apagar as categorias padrão, só as próprias.
- Categoria usada em pelo menos uma `transaction` não pode ser apagada (regra de aplicação, não de banco — validar no service layer do backend antes do delete).

## Fora de escopo
Reclassificação em massa se o usuário mudar o bucket de uma categoria própria depois de já ter transações históricas — decisão de produto pendente, registrar como ADR quando surgir.
