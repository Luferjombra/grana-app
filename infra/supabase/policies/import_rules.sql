-- import_rules: regra de categorização aprendida no import (specs/11).
--
-- Sempre do household — não existe regra "do sistema" como acontece com as 9
-- categorias padrão (household_id null em categories). O palpite inicial de
-- quem nunca importou nada vive em app/imports/suggest.py::RULES, no código.
--
-- As policies abaixo são as mesmas aplicadas pela migration 0005; este arquivo
-- é o estado alvo "do zero", igual ao resto de policies/.

alter table import_rules enable row level security;

create policy "members read their household rules"
on import_rules for select
using (household_id in (select household_id from household_members where user_id = auth.uid()));

create policy "members create rules for their household"
on import_rules for insert
with check (household_id in (select household_id from household_members where user_id = auth.uid()));

create policy "members update their household rules"
on import_rules for update
using (household_id in (select household_id from household_members where user_id = auth.uid()));

create policy "members delete their household rules"
on import_rules for delete
using (household_id in (select household_id from household_members where user_id = auth.uid()));
