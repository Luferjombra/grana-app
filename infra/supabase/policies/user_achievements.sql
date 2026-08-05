-- user_achievements: escopo individual (Família B).

alter table user_achievements enable row level security;

create policy "user owns achievements" on user_achievements for all
using (auth.uid() = user_id) with check (auth.uid() = user_id);
