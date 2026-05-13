-- Run this in the Supabase SQL Editor (project → SQL Editor → New query)
-- https://supabase.com/dashboard/project/<your-project>/sql

create table if not exists quotes (
    id              uuid        primary key default gen_random_uuid(),
    created_at      timestamptz default now(),

    -- Display / search fields
    quote_no        text        not null default '',
    customer        text        not null default '',
    project_ref     text        not null default '',
    timestamp       text        not null default '',   -- human-readable "12 May 2025 14:30"

    -- Status counters
    n_items         int         not null default 0,
    n_ready         int         not null default 0,
    n_check         int         not null default 0,
    n_missing       int         not null default 0,
    n_regret        int         not null default 0,

    -- Full data blobs
    items           jsonb       not null default '[]'::jsonb,
    quote_data      jsonb       not null default '{}'::jsonb,

    -- PDF (base64 encoded, typically < 200 KB)
    quote_pdf_b64   text        not null default '',
    quote_pdf_name  text        not null default '',

    -- Pipeline stage tracking
    -- Allowed values: initial, review, quote_prep, repricing, sent, po
    stage           text        not null default 'initial',
    -- Append-only audit log: [{stage, at}]
    stage_history   jsonb       not null default '[]'::jsonb,
    -- Free-form context entered when advancing to sent / po / repricing
    stage_meta      jsonb       not null default '{}'::jsonb
);

-- Migration for existing deployments: add columns if missing
alter table quotes add column if not exists stage         text  not null default 'initial';
alter table quotes add column if not exists stage_history jsonb not null default '[]'::jsonb;
alter table quotes add column if not exists stage_meta    jsonb not null default '{}'::jsonb;

-- Index for sidebar listing (newest first)
create index if not exists quotes_created_at_idx on quotes (created_at desc);

-- Index for searching by customer
create index if not exists quotes_customer_idx on quotes (customer);

-- Index for dashboard pipeline grouping
create index if not exists quotes_stage_idx on quotes (stage);

-- Row Level Security — open policy for now (no user auth yet)
-- When you add authentication, replace this with per-user policies
alter table quotes enable row level security;

create policy "Allow all operations"
    on quotes for all
    using (true)
    with check (true);
