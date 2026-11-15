-- Immutable Sybil graph metadata and results. Large sparse artifacts stay on backend storage.

create table if not exists sybil_datasets (
  id         text primary key,
  manifest   jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists sybil_scenarios (
  id         text primary key,
  dataset_id text not null references sybil_datasets (id),
  revision   jsonb not null,
  created_at timestamptz not null default now()
);
create index if not exists sybil_scenarios_dataset on sybil_scenarios (dataset_id);

create table if not exists sybil_assessments (
  id          text primary key,
  revision_id text not null references sybil_scenarios (id),
  status      text not null,
  assessment  jsonb not null,
  updated_at  timestamptz not null default now()
);
create index if not exists sybil_assessments_revision on sybil_assessments (revision_id);

alter table sybil_datasets enable row level security;
alter table sybil_scenarios enable row level security;
alter table sybil_assessments enable row level security;
