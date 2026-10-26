-- Agent 3T Global dashboard: profiles, per-user chat history, private settings.
-- No self-signup: users are created by an admin through the admin-users edge function.

create schema if not exists private;

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text not null,
  full_name text not null default '',
  role text not null default 'staff' check (role in ('admin', 'staff')),
  disabled boolean not null default false,
  created_at timestamptz not null default now()
);

create table public.conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  title text not null default 'Cuộc trò chuyện mới',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index conversations_user_idx on public.conversations (user_id, updated_at desc);

create table public.messages (
  id bigint generated always as identity primary key,
  conversation_id uuid not null references public.conversations (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null default '',
  media jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);
create index messages_conv_idx on public.messages (conversation_id, id);

-- Server-side config (VPS URL + API key). RLS on, no policies => only service role can read.
create table public.a3t_settings (
  key text primary key,
  value text not null
);

alter table public.profiles enable row level security;
alter table public.conversations enable row level security;
alter table public.messages enable row level security;
alter table public.a3t_settings enable row level security;

-- Each user only sees their own data (admins included: chats are private per user).
create policy "own profile" on public.profiles for select to authenticated
  using ((select auth.uid()) = id);

create policy "own conversations select" on public.conversations for select to authenticated
  using ((select auth.uid()) = user_id);
create policy "own conversations update" on public.conversations for update to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "own conversations delete" on public.conversations for delete to authenticated
  using ((select auth.uid()) = user_id);

create policy "own messages select" on public.messages for select to authenticated
  using ((select auth.uid()) = user_id);

-- Writes to profiles/messages happen only in edge functions (service role).
revoke all on public.profiles, public.conversations, public.messages, public.a3t_settings from anon, authenticated;
grant select on public.profiles to authenticated;
grant select, update (title), delete on public.conversations to authenticated;
grant select on public.messages to authenticated;
