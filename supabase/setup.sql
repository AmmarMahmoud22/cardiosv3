-- ============================================================
-- Cardios — consolidated Supabase setup (idempotent)
-- ============================================================
-- HOW TO USE: open your project on supabase.com → SQL Editor →
-- paste this whole file → Run. Safe to run more than once.
--
-- This is the single source of truth for the schema the APP CODE expects
-- (it supersedes the older, conflicting files in supabase/migrations/ —
-- notably the predictions table here uses the JSONB shape that
-- src/services/predictionService.ts actually reads/writes).
--
-- FIRST, to see what you already have, you can run:
--   select table_name from information_schema.tables where table_schema='public';
--   select column_name, data_type from information_schema.columns
--     where table_name='predictions';
-- If an existing `predictions` table has a boolean `prediction_result` or a
-- `prediction_date` column, it's the OLD shape — see the note at the bottom.
-- ============================================================

-- ---------- profiles ----------
create table if not exists public.profiles (
  id uuid primary key references auth.users on delete cascade,
  email text not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
alter table public.profiles enable row level security;

drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own" on public.profiles
  for select to authenticated using (auth.uid() = id);

drop policy if exists "profiles_insert_own" on public.profiles;
create policy "profiles_insert_own" on public.profiles
  for insert to authenticated with check (auth.uid() = id);

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own" on public.profiles
  for update to authenticated using (auth.uid() = id) with check (auth.uid() = id);

-- ---------- extended_profiles ----------
create table if not exists public.extended_profiles (
  id uuid primary key references auth.users on delete cascade,
  full_name text,
  date_of_birth date,
  gender text check (gender in ('Male', 'Female', 'Other')),
  phone_number text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
alter table public.extended_profiles enable row level security;

drop policy if exists "ext_select_own" on public.extended_profiles;
create policy "ext_select_own" on public.extended_profiles
  for select to authenticated using (auth.uid() = id);

drop policy if exists "ext_insert_own" on public.extended_profiles;
create policy "ext_insert_own" on public.extended_profiles
  for insert to authenticated with check (auth.uid() = id);

drop policy if exists "ext_update_own" on public.extended_profiles;
create policy "ext_update_own" on public.extended_profiles
  for update to authenticated using (auth.uid() = id) with check (auth.uid() = id);

-- ---------- user_roles ----------
create table if not exists public.user_roles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users on delete cascade not null,
  role text not null check (role in ('patient', 'doctor', 'admin')),
  is_banned boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
alter table public.user_roles enable row level security;

-- Migrate legacy rows from the old generic role name to the explicit patient role.
alter table public.user_roles drop constraint if exists user_roles_role_check;
update public.user_roles set role = 'patient' where role = 'user';
alter table public.user_roles add constraint user_roles_role_check
  check (role in ('patient', 'doctor', 'admin'));

drop policy if exists "roles_select_own" on public.user_roles;
create policy "roles_select_own" on public.user_roles
  for select to authenticated using (auth.uid() = user_id);

drop policy if exists "roles_insert_own" on public.user_roles;
create policy "roles_insert_own" on public.user_roles
  -- A user may only ever create their OWN, non-privileged ('patient') role row.
  -- This blocks self-promotion to 'admin' via a direct insert. (Roles are
  -- normally created by the handle_new_user trigger; admin is granted manually
  -- by a trusted operator.)
  for insert to authenticated with check (auth.uid() = user_id and role = 'patient');
-- NOTE: an "admins manage all roles" policy that does
--   EXISTS (select 1 from user_roles where user_id = auth.uid() and role='admin')
-- causes RLS *infinite recursion* (the policy queries the table it guards).
-- It is intentionally omitted here. For admin management use a SECURITY DEFINER
-- function or the service-role key from a trusted server — not a recursive policy.

-- ---------- predictions (JSONB shape — matches predictionService.ts) ----------
create table if not exists public.predictions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users on delete cascade not null,
  prediction_data jsonb not null,
  prediction_result text not null,
  created_at timestamptz default timezone('utc', now()) not null
);
alter table public.predictions enable row level security;

drop policy if exists "pred_select_own" on public.predictions;
create policy "pred_select_own" on public.predictions
  for select to authenticated using (auth.uid() = user_id);

drop policy if exists "pred_insert_own" on public.predictions;
create policy "pred_insert_own" on public.predictions
  for insert to authenticated with check (auth.uid() = user_id);

create index if not exists predictions_user_id_idx on public.predictions(user_id);
create index if not exists predictions_created_at_idx on public.predictions(created_at desc);

-- ---------- user_stats view ----------
drop view if exists public.user_stats;

create view public.user_stats as
select
  user_id,
  count(*) as total_predictions,
  sum(case when prediction_result like '%High%' then 1 else 0 end) as high_risk_predictions,
  sum(case when prediction_result like '%Low%' then 1 else 0 end) as low_risk_predictions,
  max(created_at) as last_prediction_date
from public.predictions
group by user_id;

grant select, insert on public.predictions to authenticated;
grant select on public.user_stats to authenticated;

-- ---------- admin authorization helper (avoids RLS recursion) ----------
-- SECURITY DEFINER: reads user_roles with owner rights (bypasses RLS), so it
-- can be referenced inside the user_roles policy itself without the infinite
-- recursion a self-referential policy would cause.
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

create or replace function public.is_doctor(uid uuid)
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
      and role = 'doctor'
      and coalesce(is_banned, false) = false
  );
$$;
revoke all on function public.is_doctor(uuid) from public;
grant execute on function public.is_doctor(uuid) to authenticated;

-- ---------- admin READ policies (additive; own-row policies above stay intact) ----------
-- Permissive policies are OR-combined, so the rule becomes "own row OR admin".
-- Non-admin users are unaffected; RLS is not weakened.
drop policy if exists "profiles_select_admin" on public.profiles;
create policy "profiles_select_admin" on public.profiles
  for select to authenticated using (public.is_admin(auth.uid()));

drop policy if exists "ext_select_admin" on public.extended_profiles;
create policy "ext_select_admin" on public.extended_profiles
  for select to authenticated using (public.is_admin(auth.uid()));

drop policy if exists "roles_select_admin" on public.user_roles;
create policy "roles_select_admin" on public.user_roles
  for select to authenticated using (public.is_admin(auth.uid()));

drop policy if exists "pred_select_admin" on public.predictions;
create policy "pred_select_admin" on public.predictions
  for select to authenticated using (public.is_admin(auth.uid()));

-- ---------- robust signup: create profile + default role server-side ----------
delete from public.user_roles
where id in (
  select id
  from (
    select
      id,
      row_number() over (
        partition by user_id
        order by updated_at desc nulls last, created_at desc nulls last, id desc
      ) as duplicate_rank
    from public.user_roles
  ) ranked_roles
  where duplicate_rank > 1
);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'user_roles_user_id_key'
      and conrelid = 'public.user_roles'::regclass
  ) and not exists (
    select 1
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where c.relname = 'user_roles_user_id_key'
      and n.nspname = 'public'
  ) then
    create unique index user_roles_user_id_key on public.user_roles(user_id);
  end if;
end $$;

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
    values (new.id, 'patient', false)
    on conflict (user_id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------- ecg_analyses (real table; replaces the localStorage mock) ----------
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

-- ---------- monitoring_checkins (real table; replaces the localStorage mock) ----------
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

-- ---------- care-team relationships ----------
create table if not exists public.doctor_patients (
  id uuid primary key default gen_random_uuid(),
  doctor_id uuid references auth.users on delete cascade not null,
  patient_id uuid references auth.users on delete cascade not null,
  status text not null default 'active' check (status in ('pending', 'active', 'archived')),
  created_at timestamptz default timezone('utc', now()) not null,
  updated_at timestamptz default timezone('utc', now()) not null,
  unique (doctor_id, patient_id)
);
alter table public.doctor_patients enable row level security;

create index if not exists doctor_patients_doctor_idx on public.doctor_patients(doctor_id, status);
create index if not exists doctor_patients_patient_idx on public.doctor_patients(patient_id, status);

create or replace function public.can_doctor_access_patient(doctor_uid uuid, patient_uid uuid)
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select public.is_admin(doctor_uid) or exists (
    select 1
    from public.doctor_patients
    where doctor_id = doctor_uid
      and patient_id = patient_uid
      and status = 'active'
  );
$$;
revoke all on function public.can_doctor_access_patient(uuid, uuid) from public;
grant execute on function public.can_doctor_access_patient(uuid, uuid) to authenticated;

create or replace function public.can_access_patient_record(patient_uid uuid)
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select auth.uid() = patient_uid
    or public.is_admin(auth.uid())
    or public.can_doctor_access_patient(auth.uid(), patient_uid);
$$;
revoke all on function public.can_access_patient_record(uuid) from public;
grant execute on function public.can_access_patient_record(uuid) to authenticated;

drop policy if exists "doctor_patients_select_care_team" on public.doctor_patients;
create policy "doctor_patients_select_care_team" on public.doctor_patients
  for select to authenticated
  using (doctor_id = auth.uid() or patient_id = auth.uid() or public.is_admin(auth.uid()));

drop policy if exists "doctor_patients_insert_doctor" on public.doctor_patients;
create policy "doctor_patients_insert_doctor" on public.doctor_patients
  for insert to authenticated
  with check (public.is_admin(auth.uid()) or (doctor_id = auth.uid() and public.is_doctor(auth.uid())));

drop policy if exists "doctor_patients_update_doctor" on public.doctor_patients;
create policy "doctor_patients_update_doctor" on public.doctor_patients
  for update to authenticated
  using (public.is_admin(auth.uid()) or (doctor_id = auth.uid() and public.is_doctor(auth.uid())))
  with check (public.is_admin(auth.uid()) or (doctor_id = auth.uid() and public.is_doctor(auth.uid())));

-- ---------- assigned ECG devices ----------
create table if not exists public.devices (
  id uuid primary key default gen_random_uuid(),
  device_id text not null unique,
  display_name text not null default 'Unassigned ECG device',
  patient_id uuid references auth.users on delete set null,
  assigned_by uuid references auth.users on delete set null,
  status text not null default 'active' check (status in ('active', 'inactive', 'retired')),
  last_seen_at timestamptz,
  created_at timestamptz default timezone('utc', now()) not null,
  updated_at timestamptz default timezone('utc', now()) not null
);
alter table public.devices enable row level security;

create index if not exists devices_patient_idx on public.devices(patient_id, status);
create index if not exists devices_last_seen_idx on public.devices(last_seen_at desc);

drop policy if exists "devices_select_care_team" on public.devices;
create policy "devices_select_care_team" on public.devices
  for select to authenticated
  using (
    public.is_admin(auth.uid())
    or patient_id = auth.uid()
    or assigned_by = auth.uid()
    or public.can_doctor_access_patient(auth.uid(), patient_id)
  );

drop policy if exists "devices_insert_doctor" on public.devices;
create policy "devices_insert_doctor" on public.devices
  for insert to authenticated
  with check (
    public.is_admin(auth.uid())
    or (
      public.is_doctor(auth.uid())
      and assigned_by = auth.uid()
      and (patient_id is null or public.can_doctor_access_patient(auth.uid(), patient_id))
    )
  );

drop policy if exists "devices_update_doctor" on public.devices;
create policy "devices_update_doctor" on public.devices
  for update to authenticated
  using (
    public.is_admin(auth.uid())
    or assigned_by = auth.uid()
    or public.can_doctor_access_patient(auth.uid(), patient_id)
  )
  with check (
    public.is_admin(auth.uid())
    or (
      public.is_doctor(auth.uid())
      and (assigned_by = auth.uid() or assigned_by is null)
      and (patient_id is null or public.can_doctor_access_patient(auth.uid(), patient_id))
    )
  );

-- ---------- clinical review alerts ----------
create table if not exists public.alerts (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid references auth.users on delete cascade not null,
  doctor_id uuid references auth.users on delete set null,
  source text not null check (source in ('ecg', 'risk_prediction', 'monitoring_checkin', 'device_offline', 'poor_signal')),
  severity text not null check (severity in ('low', 'medium', 'high', 'critical')),
  title text not null,
  message text not null,
  reason_codes text[] not null default '{}',
  status text not null default 'unread' check (status in ('unread', 'acknowledged', 'resolved', 'dismissed')),
  related_device_id text,
  related_record_id uuid,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz default timezone('utc', now()) not null,
  acknowledged_at timestamptz
);
alter table public.alerts enable row level security;

create index if not exists alerts_patient_idx on public.alerts(patient_id, status, created_at desc);
create index if not exists alerts_doctor_idx on public.alerts(doctor_id, status, created_at desc);
create index if not exists alerts_severity_idx on public.alerts(severity, created_at desc);

drop policy if exists "alerts_select_care_team" on public.alerts;
create policy "alerts_select_care_team" on public.alerts
  for select to authenticated
  using (
    public.is_admin(auth.uid())
    or patient_id = auth.uid()
    or doctor_id = auth.uid()
    or public.can_doctor_access_patient(auth.uid(), patient_id)
  );

drop policy if exists "alerts_insert_care_team" on public.alerts;
create policy "alerts_insert_care_team" on public.alerts
  for insert to authenticated
  with check (
    public.is_admin(auth.uid())
    or patient_id = auth.uid()
    or doctor_id = auth.uid()
    or public.can_doctor_access_patient(auth.uid(), patient_id)
  );

drop policy if exists "alerts_update_doctor" on public.alerts;
create policy "alerts_update_doctor" on public.alerts
  for update to authenticated
  using (
    public.is_admin(auth.uid())
    or doctor_id = auth.uid()
    or public.can_doctor_access_patient(auth.uid(), patient_id)
  )
  with check (
    public.is_admin(auth.uid())
    or doctor_id = auth.uid()
    or public.can_doctor_access_patient(auth.uid(), patient_id)
  );

-- ---------- doctor notes ----------
create table if not exists public.doctor_notes (
  id uuid primary key default gen_random_uuid(),
  doctor_id uuid references auth.users on delete cascade not null,
  patient_id uuid references auth.users on delete cascade not null,
  body text not null,
  visible_to_patient boolean not null default false,
  created_at timestamptz default timezone('utc', now()) not null,
  updated_at timestamptz default timezone('utc', now()) not null
);
alter table public.doctor_notes enable row level security;

create index if not exists doctor_notes_patient_idx on public.doctor_notes(patient_id, created_at desc);
create index if not exists doctor_notes_doctor_idx on public.doctor_notes(doctor_id, created_at desc);

drop policy if exists "doctor_notes_select_care_team" on public.doctor_notes;
create policy "doctor_notes_select_care_team" on public.doctor_notes
  for select to authenticated
  using (
    public.is_admin(auth.uid())
    or doctor_id = auth.uid()
    or public.can_doctor_access_patient(auth.uid(), patient_id)
    or (patient_id = auth.uid() and visible_to_patient = true)
  );

drop policy if exists "doctor_notes_insert_doctor" on public.doctor_notes;
create policy "doctor_notes_insert_doctor" on public.doctor_notes
  for insert to authenticated
  with check (
    public.is_admin(auth.uid())
    or (doctor_id = auth.uid() and public.can_doctor_access_patient(auth.uid(), patient_id))
  );

drop policy if exists "doctor_notes_update_author" on public.doctor_notes;
create policy "doctor_notes_update_author" on public.doctor_notes
  for update to authenticated
  using (public.is_admin(auth.uid()) or doctor_id = auth.uid())
  with check (
    public.is_admin(auth.uid())
    or (doctor_id = auth.uid() and public.can_doctor_access_patient(auth.uid(), patient_id))
  );

-- Let doctors read assigned patient clinical data without giving them global admin access.
drop policy if exists "profiles_select_assigned_doctor" on public.profiles;
create policy "profiles_select_assigned_doctor" on public.profiles
  for select to authenticated using (public.can_doctor_access_patient(auth.uid(), id));

drop policy if exists "ext_select_assigned_doctor" on public.extended_profiles;
create policy "ext_select_assigned_doctor" on public.extended_profiles
  for select to authenticated using (public.can_doctor_access_patient(auth.uid(), id));

drop policy if exists "pred_select_assigned_doctor" on public.predictions;
create policy "pred_select_assigned_doctor" on public.predictions
  for select to authenticated using (public.can_doctor_access_patient(auth.uid(), user_id));

drop policy if exists "ecg_select_assigned_doctor" on public.ecg_analyses;
create policy "ecg_select_assigned_doctor" on public.ecg_analyses
  for select to authenticated using (public.can_doctor_access_patient(auth.uid(), user_id));

drop policy if exists "mon_select_assigned_doctor" on public.monitoring_checkins;
create policy "mon_select_assigned_doctor" on public.monitoring_checkins
  for select to authenticated using (public.can_doctor_access_patient(auth.uid(), user_id));

grant select, insert, update on public.doctor_patients to authenticated;
grant select, insert, update on public.devices to authenticated;
grant select, insert, update on public.alerts to authenticated;
grant select, insert, update on public.doctor_notes to authenticated;

-- ============================================================
-- MIGRATING AN OLD predictions TABLE (only if needed)
-- If you already had the old shape (boolean prediction_result / prediction_date /
-- per-feature columns), the `create table if not exists` above did NOT change it.
-- The app needs `prediction_data jsonb`, `prediction_result text`, `created_at`.
-- Simplest fix if the old table has no data you need:
--   drop view if exists public.user_stats;
--   drop table if exists public.predictions cascade;
-- then re-run this whole file. (Back up first if it has real data.)
-- ============================================================
