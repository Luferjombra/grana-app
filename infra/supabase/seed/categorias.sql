-- ============================================================================
-- Seed: categorias padrão do sistema (household_id null, is_default true)
-- Rodar depois de schema.sql. Ver specs/03-seed-categorias.md.
-- ============================================================================

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
