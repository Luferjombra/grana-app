-- achievements: catálogo público — todo mundo lê, ninguém escreve pelo client.

alter table achievements enable row level security;

create policy "everyone can read achievements catalog"
on achievements for select
using (true);

-- sem policy de insert/update/delete: só a service role (backend) altera o catálogo.
