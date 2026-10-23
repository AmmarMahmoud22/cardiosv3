-- ============================================================
-- Cardios demo seed template
-- ============================================================
-- Run this AFTER:
--   1. supabase/setup.sql has completed successfully.
--   2. You created/sign-up the demo doctor account in Authentication.
--   3. You created/sign-up the demo patient account in Authentication.
--
-- Edit ONLY the values in cardios_demo_params, then paste/run this whole file
-- in Supabase SQL Editor. It is safe to run more than once; existing demo
-- device/link/roles are updated and duplicate demo rows are avoided where
-- practical.
-- ============================================================

drop table if exists pg_temp.cardios_demo_params;
create temp table cardios_demo_params as
select
  'doctor@cardios.demo'::text as doctor_email,
  'patient@cardios.demo'::text as patient_email,
  'Dr. Cardios Demo'::text as doctor_name,
  'Mohamed Ali'::text as patient_name,
  'esp32-ad8232-demo'::text as device_id,
  'Mohamed Ali ECG device'::text as device_display_name;

do $$
declare
  demo_doctor_id uuid;
  demo_patient_id uuid;
  demo_doctor_email text;
  demo_patient_email text;
  demo_doctor_name text;
  demo_patient_name text;
  demo_device_id text;
  demo_device_display_name text;
begin
  select
    doctor_email,
    patient_email,
    doctor_name,
    patient_name,
    device_id,
    device_display_name
  into
    demo_doctor_email,
    demo_patient_email,
    demo_doctor_name,
    demo_patient_name,
    demo_device_id,
    demo_device_display_name
  from pg_temp.cardios_demo_params
  limit 1;

  select id into demo_doctor_id
  from auth.users
  where lower(email) = lower(demo_doctor_email)
  limit 1;

  select id into demo_patient_id
  from auth.users
  where lower(email) = lower(demo_patient_email)
  limit 1;

  if demo_doctor_id is null then
    raise exception 'Doctor email % was not found in Authentication > Users', demo_doctor_email;
  end if;

  if demo_patient_id is null then
    raise exception 'Patient email % was not found in Authentication > Users', demo_patient_email;
  end if;

  insert into public.profiles (id, email)
  values
    (demo_doctor_id, demo_doctor_email),
    (demo_patient_id, demo_patient_email)
  on conflict (id) do update
    set email = excluded.email,
        updated_at = now();

  insert into public.extended_profiles (id, full_name, gender)
  values
    (demo_doctor_id, demo_doctor_name, 'Other'),
    (demo_patient_id, demo_patient_name, 'Male')
  on conflict (id) do update
    set full_name = excluded.full_name,
        gender = excluded.gender,
        updated_at = now();

  insert into public.user_roles (user_id, role, is_banned)
  values
    (demo_doctor_id, 'doctor', false),
    (demo_patient_id, 'patient', false)
  on conflict (user_id) do update
    set role = excluded.role,
        is_banned = false,
        updated_at = now();

  insert into public.doctor_patients (doctor_id, patient_id, status)
  values (demo_doctor_id, demo_patient_id, 'active')
  on conflict (doctor_id, patient_id) do update
    set status = 'active',
        updated_at = now();

  insert into public.devices (
    device_id,
    display_name,
    patient_id,
    assigned_by,
    status,
    last_seen_at,
    updated_at
  )
  values (
    demo_device_id,
    demo_device_display_name,
    demo_patient_id,
    demo_doctor_id,
    'active',
    now(),
    now()
  )
  on conflict (device_id) do update
    set display_name = excluded.display_name,
        patient_id = excluded.patient_id,
        assigned_by = excluded.assigned_by,
        status = 'active',
        last_seen_at = now(),
        updated_at = now();

  insert into public.predictions (user_id, prediction_data, prediction_result)
  select
    demo_patient_id,
    jsonb_build_object(
      'BMI', 31.2,
      'Smoking', 'Yes',
      'AlcoholDrinking', 'No',
      'Stroke', 'No',
      'PhysicalHealth', 12,
      'MentalHealth', 4,
      'DiffWalking', 'Yes',
      'Sex', 'Male',
      'AgeCategory', '60-64',
      'Race', 'Other',
      'Diabetic', 'Yes',
      'PhysicalActivity', 'No',
      'GenHealth', 'Fair',
      'SleepTime', 5,
      'Asthma', 'No',
      'KidneyDisease', 'No',
      'SkinCancer', 'No'
    ),
    'High risk of heart disease'
  where not exists (
    select 1
    from public.predictions
    where user_id = demo_patient_id
      and prediction_result = 'High risk of heart disease'
  );

  insert into public.ecg_analyses (user_id, file_name, prediction, confidence, signal_preview)
  select
    demo_patient_id,
    'demo_patient_ecg.csv',
    'Possible arrhythmia',
    88.4,
    '[0.02, 0.08, 0.24, 0.92, 0.18, -0.16, -0.04, 0.03]'::jsonb
  where not exists (
    select 1
    from public.ecg_analyses
    where user_id = demo_patient_id
      and file_name = 'demo_patient_ecg.csv'
  );

  insert into public.monitoring_checkins (
    user_id,
    resting_heart_rate,
    breathlessness,
    fatigue,
    stress_level,
    activity_minutes,
    sleep_hours,
    note
  )
  select
    demo_patient_id,
    96,
    7,
    8,
    6,
    8,
    5.5,
    'Demo check-in: patient reports fatigue and breathlessness after light activity.'
  where not exists (
    select 1
    from public.monitoring_checkins
    where user_id = demo_patient_id
      and note = 'Demo check-in: patient reports fatigue and breathlessness after light activity.'
  );

  insert into public.alerts (
    patient_id,
    doctor_id,
    source,
    severity,
    title,
    message,
    reason_codes,
    status,
    related_device_id,
    metadata
  )
  select
    demo_patient_id,
    demo_doctor_id,
    'monitoring_checkin',
    'high',
    'High-priority patient review',
    'Cardios detected elevated risk inputs with fatigue, breathlessness, and a recent abnormal ECG screening label.',
    array['high_risk_prediction', 'symptom_checkin', 'abnormal_ecg'],
    'unread',
    demo_device_id,
    jsonb_build_object('demo', true)
  where not exists (
    select 1
    from public.alerts
    where patient_id = demo_patient_id
      and title = 'High-priority patient review'
  );

  insert into public.doctor_notes (doctor_id, patient_id, body, visible_to_patient)
  select
    demo_doctor_id,
    demo_patient_id,
    'Demo note: review ECG quality, repeat measurement if symptoms continue, and consider clinician follow-up.',
    true
  where not exists (
    select 1
    from public.doctor_notes
    where doctor_id = demo_doctor_id
      and patient_id = demo_patient_id
      and body = 'Demo note: review ECG quality, repeat measurement if symptoms continue, and consider clinician follow-up.'
  );
end $$;

select
  p.doctor_email,
  p.patient_email,
  doctor.id as doctor_id,
  patient.id as patient_id,
  'Demo seed complete. Sign in as the doctor and open /doctor.' as result
from pg_temp.cardios_demo_params p
join auth.users doctor on lower(doctor.email) = lower(p.doctor_email)
join auth.users patient on lower(patient.email) = lower(p.patient_email);
