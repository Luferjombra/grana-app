-- receipts: escopo individual (Família B).

alter table receipts enable row level security;

create policy "user owns receipts" on receipts for all
using (auth.uid() = user_id) with check (auth.uid() = user_id);
