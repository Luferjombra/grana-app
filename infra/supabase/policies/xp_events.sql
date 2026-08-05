-- xp_events: escopo individual (Família B).

alter table xp_events enable row level security;

create policy "user owns xp_events" on xp_events for all
using (auth.uid() = user_id) with check (auth.uid() = user_id);
