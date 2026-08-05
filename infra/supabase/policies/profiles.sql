-- profiles: escopo individual (Família B).

alter table profiles enable row level security;

create policy "user owns profile" on profiles for all
using (auth.uid() = id) with check (auth.uid() = id);
