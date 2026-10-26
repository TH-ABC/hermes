-- Agent 3T UI saves each user's chats directly (RLS: only their own rows).
create policy "own conversations insert" on public.conversations for insert to authenticated
  with check ((select auth.uid()) = user_id);
create policy "own messages insert" on public.messages for insert to authenticated
  with check (
    (select auth.uid()) = user_id
    and conversation_id in (select id from public.conversations where user_id = (select auth.uid()))
  );
grant insert on public.conversations, public.messages to authenticated;
