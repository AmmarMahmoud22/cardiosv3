-- =====================================================================
--  CARDIOS — demo seed
-- =====================================================================
--  Populates the doctor and admin views with realistic clinical history so
--  they are not empty during a demo.
--
--  BEFORE running this:
--    1. Run supabase/bootstrap.sql
--    2. Create the two accounts by SIGNING UP through the app (or via
--       Authentication -> Users -> Add user). Passwords are hashed by
--       Supabase Auth, so accounts cannot be created from SQL — this script
--       finds existing users by email and wires everything around them.
--
--  Then edit the two emails below and run the whole file in the SQL Editor.
--  Safe to run repeatedly: roles are upserted, links are upserted, and the
--  clinical rows are cleared and rewritten so you never get duplicates.
-- =====================================================================

do $$
declare
  -- ---------------- EDIT THESE TWO ----------------
  doctor_email  text := 'doctor@cardios.demo';
  patient_email text := 'patient@cardios.demo';
  -- ------------------------------------------------

  v_doctor_id  uuid;
  v_patient_id uuid;
begin
  select id into v_doctor_id  from auth.users where lower(email) = lower(doctor_email);
  select id into v_patient_id from auth.users where lower(email) = lower(patient_email);

  -- Fail with something actionable rather than a null-constraint error later.
  if v_doctor_id is null then
    raise exception
      'No account found for %. Sign that user up in the app first, then re-run this script.',
      doctor_email;
  end if;
  if v_patient_id is null then
    raise exception
      'No account found for %. Sign that user up in the app first, then re-run this script.',
      patient_email;
  end if;

  -- ---------- roles ----------
  -- The signup trigger already created a 'patient' role for both; promote one.
  update public.user_roles set role = 'doctor', updated_at = now() where user_id = v_doctor_id;
  if not found then
    insert into public.user_roles (user_id, role) values (v_doctor_id, 'doctor');
  end if;

  update public.user_roles set role = 'patient', updated_at = now() where user_id = v_patient_id;
  if not found then
    insert into public.user_roles (user_id, role) values (v_patient_id, 'patient');
  end if;

  -- ---------- care-team link ----------
  if not exists (select 1 from public.doctor_patients
                  where doctor_id = v_doctor_id and patient_id = v_patient_id) then
    insert into public.doctor_patients (doctor_id, patient_id, status)
    values (v_doctor_id, v_patient_id, 'active');
  else
    update public.doctor_patients set status = 'active', updated_at = now()
     where doctor_id = v_doctor_id and patient_id = v_patient_id;
  end if;

  -- ---------- clinical history (rewritten each run) ----------
  delete from public.predictions          where user_id = v_patient_id;
  delete from public.ecg_analyses         where user_id = v_patient_id;
  delete from public.monitoring_checkins  where user_id = v_patient_id;
  delete from public.doctor_notes         where patient_id = v_patient_id;

  -- Heart-risk assessments over three months, showing a downward risk trend
  -- after treatment — so the timeline chart has a story to tell.
  insert into public.predictions (user_id, prediction_data, prediction_result, created_at) values
    (v_patient_id, jsonb_build_object('BMI',32.4,'Smoking','Yes','AlcoholDrinking','No','Stroke','No',
       'PhysicalHealth',12,'MentalHealth',6,'DiffWalking','Yes','Sex','Male','AgeCategory','65-69',
       'Race','White','Diabetic','Yes','PhysicalActivity','No','GenHealth','Fair','SleepTime',5,
       'Asthma','No','KidneyDisease','No','SkinCancer','No'),
     'High cardiac risk profile', now() - interval '90 days'),
    (v_patient_id, jsonb_build_object('BMI',31.1,'Smoking','Yes','AlcoholDrinking','No','Stroke','No',
       'PhysicalHealth',9,'MentalHealth',4,'DiffWalking','Yes','Sex','Male','AgeCategory','65-69',
       'Race','White','Diabetic','Yes','PhysicalActivity','Yes','GenHealth','Fair','SleepTime',6,
       'Asthma','No','KidneyDisease','No','SkinCancer','No'),
     'High cardiac risk profile', now() - interval '60 days'),
    (v_patient_id, jsonb_build_object('BMI',29.8,'Smoking','No','AlcoholDrinking','No','Stroke','No',
       'PhysicalHealth',5,'MentalHealth',3,'DiffWalking','No','Sex','Male','AgeCategory','65-69',
       'Race','White','Diabetic','Yes','PhysicalActivity','Yes','GenHealth','Good','SleepTime',7,
       'Asthma','No','KidneyDisease','No','SkinCancer','No'),
     'Low cardiac risk profile', now() - interval '14 days');

  -- ECG analyses. Confidence is stored on the same 0-100 scale the API returns.
  insert into public.ecg_analyses (user_id, file_name, prediction, confidence, signal_preview, created_at) values
    (v_patient_id, 'ecg_2026_baseline.csv', 'Premature Ventricular Contraction', 78.4,
     '[0.12,0.18,0.42,0.95,0.31,0.08,0.05,0.11,0.22,0.47]'::jsonb, now() - interval '88 days'),
    (v_patient_id, 'ecg_2026_followup.csv', 'Normal', 91.2,
     '[0.10,0.15,0.38,0.92,0.28,0.07,0.04,0.09,0.19,0.41]'::jsonb, now() - interval '30 days'),
    (v_patient_id, 'ecg_2026_latest.csv',   'Normal', 94.7,
     '[0.09,0.14,0.36,0.90,0.27,0.06,0.04,0.08,0.18,0.39]'::jsonb, now() - interval '7 days');

  -- Monitoring check-ins across eight weeks, improving over time.
  insert into public.monitoring_checkins
    (user_id, resting_heart_rate, breathlessness, fatigue, stress_level,
     activity_minutes, sleep_hours, note, recorded_at) values
    (v_patient_id, 88, 4, 4, 4,  10, 5.0, 'Breathless climbing stairs.',        now() - interval '56 days'),
    (v_patient_id, 84, 3, 4, 3,  25, 5.5, 'Started short daily walks.',          now() - interval '42 days'),
    (v_patient_id, 80, 3, 3, 3,  40, 6.0, 'Ankle swelling reduced.',             now() - interval '28 days'),
    (v_patient_id, 76, 2, 2, 2,  70, 6.5, 'Walking 30 minutes without stopping.',now() - interval '14 days'),
    (v_patient_id, 72, 1, 2, 2,  95, 7.0, 'Best week so far.',                   now() - interval '3 days');

  -- Clinician notes, one shared with the patient and one internal.
  insert into public.doctor_notes (doctor_id, patient_id, body, visible_to_patient, created_at) values
    (v_doctor_id, v_patient_id,
     'Baseline review: HFrEF with frequent PVCs on screening ECG. Started guideline-directed therapy and smoking cessation support.',
     true,  now() - interval '87 days'),
    (v_doctor_id, v_patient_id,
     'Eight-week review: resting heart rate down from 88 to 72 bpm, ECG screening now normal, latest risk assessment moved to low. Continue current therapy.',
     true,  now() - interval '6 days'),
    (v_doctor_id, v_patient_id,
     'Internal: consider ICD discussion only if LVEF stays below 35% after three months of optimal therapy (ESC 2021, p.3626).',
     false, now() - interval '6 days');

  raise notice 'Seed complete. doctor=% patient=%', doctor_email, patient_email;
end
$$;

-- ---------------------------------------------------------------------
--  What was created
-- ---------------------------------------------------------------------
select 'roles'                as seeded, count(*)::text as rows from public.user_roles
union all select 'care-team links',      count(*)::text from public.doctor_patients
union all select 'risk assessments',     count(*)::text from public.predictions
union all select 'ecg analyses',         count(*)::text from public.ecg_analyses
union all select 'monitoring check-ins', count(*)::text from public.monitoring_checkins
union all select 'clinician notes',      count(*)::text from public.doctor_notes;
