-- Video tab keeps its own history: conversations are tagged 'chat' (default) or 'video'.
alter table public.conversations
  add column if not exists kind text not null default 'chat' check (kind in ('chat', 'video'));
create index if not exists conversations_kind_idx on public.conversations (user_id, kind, updated_at desc);
