-- ============================================================================
-- Migration 0002: policies do Storage pro bucket "receipts" (specs/05).
--
-- Pré-requisito manual (não dá pra criar bucket via SQL puro): no painel do
-- Supabase, Storage -> New bucket -> nome "receipts", marcar como privado
-- (Public bucket OFF). Rodar esta migration só depois do bucket existir.
--
-- O upload em si é feito pelo backend com a service role key (specs/05: "App
-- envia foto -> backend salva em Supabase Storage"), que ignora RLS — essas
-- policies existem pra quando o app precisar ler a imagem direto via sessão
-- do usuário (ex: preview na tela de confirmação), sem abrir acesso a
-- recibos de outros usuários. Convenção de path: receipts/{user_id}/{arquivo}.
-- ============================================================================

begin;

create policy "users can read their own receipt images"
on storage.objects for select
using (
  bucket_id = 'receipts'
  and (storage.foldername(name))[1] = auth.uid()::text
);

-- Sem policy de insert/update/delete pro client: só a service role (backend)
-- escreve nesse bucket.

commit;
