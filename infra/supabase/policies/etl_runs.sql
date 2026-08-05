-- etl_runs: RLS habilitado, sem nenhuma policy — fica inacessível pro client,
-- só a service role (que ignora RLS por padrão) consegue ler/escrever.

alter table etl_runs enable row level security;
