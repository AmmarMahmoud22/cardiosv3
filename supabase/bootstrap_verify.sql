-- =====================================================================
--  CARDIOS — verify the database bootstrap
--  Run in the Supabase SQL Editor after bootstrap.sql. Read-only.
-- =====================================================================
select
  'tables' as check,
  count(*)::text || ' / 13' as result,
  case when count(*) >= 13 then 'PASS' else 'FAIL — re-run bootstrap.sql' end as status
from pg_tables
where schemaname = 'public'
  and tablename in ('profiles','extended_profiles','user_roles','predictions',
                    'ecg_analyses','monitoring_checkins','doctor_patients',
                    'doctor_notes','devices','alerts','clinical_documents',
                    'clinical_chunks','rag_ingest_reports')

union all
select
  'row-level security',
  count(*) filter (where rowsecurity)::text || ' / ' || count(*)::text || ' protected',
  case when count(*) = count(*) filter (where rowsecurity)
       then 'PASS' else 'FAIL — some tables are unprotected' end
from pg_tables where schemaname = 'public'

union all
select
  'policies',
  count(*)::text || ' defined',
  case when count(*) >= 20 then 'PASS' else 'FAIL — policies missing' end
from pg_policies where schemaname = 'public'

union all
select
  'role helpers',
  string_agg(proname, ', ' order by proname),
  case when count(*) = 2 then 'PASS' else 'FAIL — is_admin/is_doctor missing' end
from pg_proc p join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public' and p.proname in ('is_admin','is_doctor')

union all
select
  'signup trigger',
  coalesce(max(tgname), 'none'),
  case when count(*) = 1 then 'PASS'
       else 'FAIL — new users will get no profile or role' end
from pg_trigger where tgname = 'on_auth_user_created' and not tgisinternal

union all
select
  'existing users provisioned',
  (select count(*) from public.profiles)::text || ' profiles for ' ||
  (select count(*) from auth.users)::text || ' users',
  case when (select count(*) from auth.users) = 0 then 'OK — no users yet'
       when (select count(*) from public.profiles) >= (select count(*) from auth.users)
       then 'PASS' else 'WARN — some users have no profile' end;
