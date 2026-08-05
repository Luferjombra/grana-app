-- notifications: escopo individual (Família B).

alter table notifications enable row level security;

create policy "user owns notifications" on notifications for all
using (auth.uid() = user_id) with check (auth.uid() = user_id);
