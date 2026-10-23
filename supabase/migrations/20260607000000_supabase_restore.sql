-- ============================================================
-- Cardios — restore real Supabase auth/database behavior (idempotent)
-- ============================================================
-- Additive migration. It does NOT weaken existing row-level security:
--   * regular users keep "own-row only" access on every table
--   * admins gain READ access via an additional permissive policy that is
--     gated by a SECURITY DEFINER is_admin() helper (no RLS recursion)
--   * signup is made robust with an auth.users trigger that creates the
--     profile + default role server-side
--   * ECG analyses and monitoring check-ins move from the browser localStorage
--     mock into real, RLS-protected tables
--
-- Run on supabase.com → SQL Editor. Safe to run more than once.
-- (The same objects are also included in supabase/setup.sql, the single
--  source of truth.)
-- ============================================================

-- ---------- admin authorization helper (avoids RLS recursion) ----------
-- SECURITY DEFINER: the function reads user_roles with the owner's rights, so
-- it bypasses RLS internally. That lets us reference it inside the user_roles
-- policy itself WITHOUT the infinite recursion a self-referential policy causes.
create or replace function public.is_admin(uid uuid)
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select exists (
    select 1
    from public.user_roles
    where user_id = uid
      and role = 'admin'
      and coalesce(is_banned, false) = false
  );
$$;

revoke all on function public.is_admin(uuid) from public;
grant execute on function public.is_admin(uuid) to authenticated;

-- ---------- admin READ policies (additive; own-row policies stay intact) ----------
-- Postgres OR-combines multiple permissive policies, so the effective rule is
-- "own row OR caller is admin". Non-admins are unaffected.
drop policy if exists "profiles_select_admin" on public.profiles;
create policy "profiles_select_admin" on public.profiles
  for select to authenticated using (public.is_admin(auth.uid()));

drop policy if exists "ext_select_admin" on public.extended_profiles;
create policy "ext_select_admin" on public.extended_profiles
  for select to authenticated using (public.is_admin(auth.uid()));

drop policy if exists "roles_select_admin" on public.user_roles;
create policy "roles_select_admin" on public.user_roles
  for select to authenticated using (public.is_admin(auth.uid()));

-- Harden the existing self-insert policy: a user may only create their own
-- NON-privileged ('user') role row, never an 'admin' row (blocks self-promotion).
drop policy if exists "roles_insert_own" on public.user_roles;
create policy "roles_insert_own" on public.user_roles
  for insert to authenticated with check (auth.uid() = user_id and role = 'user');

drop policy if exists "pred_select_admin" on public.predictions;
create policy "pred_select_admin" on public.predictions
  for select to authenticated using (public.is_admin(auth.uid()));

-- ---------- robust signup: create profile + default role server-side ----------
-- One role row per user (also required for the upsert below).
create unique index if not exists user_roles_user_id_key on public.user_roles(user_id);

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email)
    values (new.id, coalesce(new.email, ''))
    on conflict (id) do nothing;

  insert into public.user_roles (user_id, role, is_banned)
    values (new.id, 'user', false)
    on conflict (user_id) do nothing;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------- ecg_analyses (was localStorage: cardios-ecg-history) ----------
create table if not exists public.ecg_analyses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users on delete cascade not null,
  file_name text,
  prediction text not null,
  confidence double precision not null default 0,
  signal_preview jsonb not null default '[]'::jsonb,
  created_at timestamptz default timezone('utc', now()) not null
);
alter table public.ecg_analyses enable row level security;

drop policy if exists "ecg_select_own" on public.ecg_analyses;
create policy "ecg_select_own" on public.ecg_analyses
  for select to authenticated using (auth.uid() = user_id);

drop policy if exists "ecg_insert_own" on public.ecg_analyses;
create policy "ecg_insert_own" on public.ecg_analyses
  for insert to authenticated with check (auth.uid() = user_id);

drop policy if exists "ecg_select_admin" on public.ecg_analyses;
create policy "ecg_select_admin" on public.ecg_analyses
  for select to authenticated using (public.is_admin(auth.uid()));

create index if not exists ecg_analyses_user_id_idx on public.ecg_analyses(user_id);
create index if not exists ecg_analyses_created_at_idx on public.ecg_analyses(created_at desc);

-- ---------- monitoring_checkins (was localStorage: cardios-monitoring-checkins) ----------
create table if not exists public.monitoring_checkins (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users on delete cascade not null,
  resting_heart_rate integer not null default 0,
  breathlessness integer not null default 0,
  fatigue integer not null default 0,
  stress_level integer not null default 0,
  activity_minutes integer not null default 0,
  sleep_hours numeric not null default 0,
  note text not null default '',
  recorded_at timestamptz default timezone('utc', now()) not null
);
alter table public.monitoring_checkins enable row level security;

drop policy if exists "mon_select_own" on public.monitoring_checkins;
create policy "mon_select_own" on public.monitoring_checkins
  for select to authenticated using (auth.uid() = user_id);

drop policy if exists "mon_insert_own" on public.monitoring_checkins;
create policy "mon_insert_own" on public.monitoring_checkins
  for insert to authenticated with check (auth.uid() = user_id);

drop policy if exists "mon_select_admin" on public.monitoring_checkins;
create policy "mon_select_admin" on public.monitoring_checkins
  for select to authenticated using (public.is_admin(auth.uid()));

create index if not exists monitoring_checkins_user_id_idx on public.monitoring_checkins(user_id);
create index if not exists monitoring_checkins_recorded_at_idx on public.monitoring_checkins(recorded_at desc);

grant select, insert on public.ecg_analyses to authenticated;
grant select, insert on public.monitoring_checkins to authenticated;
