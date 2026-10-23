-- ============================================================
-- Cardios care team layer: roles, doctor-patient links, devices,
-- clinical review alerts, and doctor notes.
-- ============================================================
-- Additive and idempotent. Safe to run after the consolidated setup.
-- It upgrades the old generic "user" role into the explicit "patient" role.
-- ============================================================

-- ---------- explicit roles ----------
alter table public.user_roles drop constraint if exists user_roles_role_check;
update public.user_roles set role = 'patient' where role = 'user';
alter table public.user_roles add constraint user_roles_role_check
  check (role in ('patient', 'doctor', 'admin'));

drop policy if exists "roles_insert_own" on public.user_roles;
create policy "roles_insert_own" on public.user_roles
  for insert to authenticated with check (auth.uid() = user_id and role = 'patient');

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

-- ---------- assigned-doctor read access to existing patient data ----------
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
