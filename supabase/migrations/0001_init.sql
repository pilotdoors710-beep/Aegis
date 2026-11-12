-- Aegis persistence (brief §3, E3). Applied by hand in the Supabase SQL editor.
-- The server connects as the database owner, which bypasses RLS; RLS with no policies keeps the
-- public anon/authenticated API roles out of every table. The web never holds Supabase keys.

create table if not exists runs (
  run_id     text primary key,
  created_at timestamptz not null,
  status     text not null,
  preset_id  text not null,
  summary    jsonb not null           -- RunSummary
);
create index if not exists runs_created_at on runs (created_at desc);

create table if not exists events (
  run_id text not null references runs (run_id) on delete cascade,
  seq    integer not null,            -- the SSE id within the run
  step   integer not null,
  mode   text not null,
  kind   text not null,
  ts     timestamptz not null,
  data   jsonb not null,              -- full Event; snapshots carry screenshot_url, never base64
  primary key (run_id, seq)
);

create table if not exists llm_cache (
  key        text primary key,        -- hash of provider:model + normalized messages
  text       text not null,
  provider   text not null,
  model      text not null,
  created_at timestamptz not null default now()
);

alter table runs enable row level security;
alter table events enable row level security;
alter table llm_cache enable row level security;

-- Screenshots: public read so replay <img> tags work without credentials; writes need the
-- service key (server only). Contents are synthetic arena pages.
insert into storage.buckets (id, name, public)
values ('shots', 'shots', true)
on conflict (id) do update set public = true;
