-- Tabela pentru starea pipeline-ului de generare video.
-- Ruleaza acest script in Supabase: Project -> SQL Editor -> New query -> Run.

create table if not exists runs (
    run_id text primary key,
    status text not null,
    data jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists runs_status_idx on runs (status);
