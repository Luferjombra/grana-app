-- user_progress: escopo individual (Família B).

alter table user_progress enable row level security;

create policy "user owns progress" on user_progress for all
using (auth.uid() = user_id) with check (auth.uid() = user_id);
