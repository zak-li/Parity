-- Supabase security fix: enable Row Level Security on all public tables.
--
-- These tables are owned by `postgres` and accessed server-side by the Parity
-- API (and sibling services) using that owner role, which BYPASSES RLS, so the
-- application is unaffected. Enabling RLS with no permissive policy denies the
-- PostgREST `anon` / `authenticated` roles, closing the Data-API exposure the
-- Supabase Advisor flags ("RLS disabled in public").
--
-- If a feature reads/writes any of these tables through the Supabase client
-- (anon key), add explicit policies for it instead of leaving RLS off.
--
-- Reverse a table with:  ALTER TABLE public.<t> DISABLE ROW LEVEL SECURITY;

alter table public.alembic_version   enable row level security;
alter table public.api_audit_logs    enable row level security;
alter table public.api_keys          enable row level security;
alter table public.audit_logs        enable row level security;
alter table public.devices           enable row level security;
alter table public.identity_twins    enable row level security;
alter table public.job_runs          enable row level security;
alter table public.login_sessions    enable row level security;
alter table public.refresh_tokens    enable row level security;
alter table public.risk_assessments  enable row level security;
alter table public.signals           enable row level security;
alter table public.simulation_runs   enable row level security;
alter table public.users             enable row level security;
