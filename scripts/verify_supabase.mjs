// ============================================================
// Cardios — automated Supabase verification (anon key only)
// ============================================================
// Exercises the real auth + RLS data flow end-to-end against your Supabase
// project, using ONLY the public anon key (no service role). It verifies:
//   1. signup -> handle_new_user trigger creates profile + 'patient' role
//   2. saving a prediction (prediction_data jsonb + prediction_result text)
//   3. reading your OWN predictions
//   4. RLS isolation: user B cannot read user A's rows
//   5. ecg_analyses + monitoring_checkins insert/read (own rows)
//   6. admin gate: is_admin() returns false for a normal user
//   7. self-promotion to 'admin' via insert is BLOCKED by RLS
//
// PREREQUISITES
//   * Run supabase/setup.sql (or the 20260607 migration) in your project first.
//   * .env must contain VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.
//   * Email confirmation: for a fully automated run, disable "Confirm email"
//     in Supabase > Authentication > Providers > Email (re-enable after). If it
//     stays ON, the script detects it and skips the authenticated checks.
//
// USAGE
//   node scripts/verify_supabase.mjs
//
// CLEANUP
//   The anon key cannot delete auth users, so the two test users linger. Their
//   emails/ids are printed at the end — delete them from Supabase >
//   Authentication > Users (profiles/predictions cascade on delete).
// ============================================================

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { createClient } from '@supabase/supabase-js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');

// ---- tiny .env parser (no extra dependency) ----
function loadEnv() {
  const out = {};
  for (const name of ['.env.local', '.env']) {
    try {
      const text = readFileSync(join(ROOT, name), 'utf8');
      for (const line of text.split(/\r?\n/)) {
        const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/i);
        if (!m) continue;
        let v = m[2].trim();
        if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
          v = v.slice(1, -1);
        }
        if (!(m[1] in out)) out[m[1]] = v;
      }
    } catch {
      /* file may not exist; ignore */
    }
  }
  return out;
}

// ---- result tracking ----
let passed = 0;
let failed = 0;
const lines = [];
function check(name, ok, detail = '') {
  if (ok) {
    passed++;
    lines.push(`  PASS  ${name}${detail ? ` — ${detail}` : ''}`);
  } else {
    failed++;
    lines.push(`  FAIL  ${name}${detail ? ` — ${detail}` : ''}`);
  }
}

const SAMPLE_PREDICTION_DATA = {
  BMI: 24.1, Smoking: 'No', AlcoholDrinking: 'No', Stroke: 'No',
  PhysicalHealth: 2, MentalHealth: 1, DiffWalking: 'No', Sex: 'Male',
  AgeCategory: '40-44', Race: 'White', Diabetic: 'No', PhysicalActivity: 'Yes',
  GenHealth: 'Very good', SleepTime: 7, Asthma: 'No', KidneyDisease: 'No',
  SkinCancer: 'No',
};

async function main() {
  const env = loadEnv();
  const url = env.VITE_SUPABASE_URL;
  const anon = env.VITE_SUPABASE_ANON_KEY || env.VITE_SUPABASE_PUBLISHABLE_KEY;

  if (!url || !anon) {
    console.error('Missing VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY in .env — cannot run.');
    process.exit(2);
  }
  console.log(`Supabase: ${url}\n`);

  const stamp = randomUUID().slice(0, 8);
  const domain = env.VERIFY_EMAIL_DOMAIN || 'example.com';
  const userA = { email: `cardios-verify-a-${stamp}@${domain}`, password: `Aa1!${randomUUID()}` };
  const userB = { email: `cardios-verify-b-${stamp}@${domain}`, password: `Bb1!${randomUUID()}` };

  // fresh client per user so sessions don't collide
  const clientA = createClient(url, anon, { auth: { persistSession: false, autoRefreshToken: false } });
  const clientB = createClient(url, anon, { auth: { persistSession: false, autoRefreshToken: false } });

  // ---------- 1. signup A ----------
  const signA = await clientA.auth.signUp(userA);
  check('signup A succeeds', !signA.error, signA.error?.message);
  if (signA.error) return report(userA, userB);

  const aId = signA.data.user?.id;
  if (!signA.data.session) {
    console.log('Email confirmation appears to be ON (no session after signup).');
    console.log('Authenticated checks are skipped. Disable "Confirm email" for a full run.\n');
    check('profile created by trigger (needs session)', false, 'skipped: email confirmation ON');
    return report(userA, userB);
  }

  // ---------- 2. trigger created profile + role ----------
  const prof = await clientA.from('profiles').select('id,email').eq('id', aId).maybeSingle();
  check('trigger created profile row', !prof.error && !!prof.data, prof.error?.message || prof.data?.email);

  const role = await clientA.from('user_roles').select('role,is_banned').eq('user_id', aId).maybeSingle();
  check("trigger created default 'patient' role", !role.error && role.data?.role === 'patient', role.error?.message || `role=${role.data?.role}`);

  // ---------- 3. save a prediction ----------
  const ins = await clientA.from('predictions').insert({
    user_id: aId,
    prediction_data: SAMPLE_PREDICTION_DATA,
    prediction_result: 'Low risk of heart disease',
  }).select().single();
  check('save prediction (jsonb + text)', !ins.error && !!ins.data?.id, ins.error?.message);
  const predId = ins.data?.id;

  // ---------- 4. read own predictions ----------
  const own = await clientA.from('predictions').select('*').eq('user_id', aId);
  check('read OWN predictions', !own.error && (own.data?.length ?? 0) >= 1, own.error?.message || `count=${own.data?.length}`);

  // ---------- 5. ecg + monitoring tables ----------
  const ecg = await clientA.from('ecg_analyses').insert({
    user_id: aId, file_name: 'verify.csv', prediction: 'Normal',
    confidence: 93.4, signal_preview: [0.1, 0.2, 0.3],
  }).select().single();
  check('insert ecg_analyses (own)', !ecg.error && !!ecg.data?.id, ecg.error?.message);

  const ecgRead = await clientA.from('ecg_analyses').select('*').eq('user_id', aId);
  check('read OWN ecg_analyses', !ecgRead.error && (ecgRead.data?.length ?? 0) >= 1, ecgRead.error?.message);

  const mon = await clientA.from('monitoring_checkins').insert({
    user_id: aId, resting_heart_rate: 72, breathlessness: 1, fatigue: 1,
    stress_level: 2, activity_minutes: 30, sleep_hours: 7, note: 'verify',
  }).select().single();
  check('insert monitoring_checkins (own)', !mon.error && !!mon.data?.id, mon.error?.message);

  // ---------- 6. admin gate: is_admin() == false for normal user ----------
  const adminRpc = await clientA.rpc('is_admin', { uid: aId });
  check('is_admin() returns false for normal user', !adminRpc.error && adminRpc.data === false, adminRpc.error?.message || `value=${adminRpc.data}`);

  // ---------- 7. self-promotion to admin is blocked ----------
  const promote = await clientA.from('user_roles').insert({ user_id: aId, role: 'admin', is_banned: false });
  check('self-promotion to admin is BLOCKED by RLS', !!promote.error, promote.error ? `blocked: ${promote.error.message}` : 'NOT blocked — security hole!');

  // ---------- 8. RLS isolation with user B ----------
  const signB = await clientB.auth.signUp(userB);
  if (signB.error || !signB.data.session) {
    check('RLS isolation (needs user B session)', false, signB.error?.message || 'no session for B');
  } else {
    const bId = signB.data.user?.id;
    // B should NOT see A's prediction by id
    const cross = await clientB.from('predictions').select('*').eq('id', predId);
    check("user B cannot read user A's prediction", !cross.error && (cross.data?.length ?? 0) === 0, cross.error?.message || `rows_visible=${cross.data?.length}`);

    // B should NOT see A's profile
    const crossProf = await clientB.from('profiles').select('*').eq('id', aId);
    check("user B cannot read user A's profile", !crossProf.error && (crossProf.data?.length ?? 0) === 0, crossProf.error?.message || `rows_visible=${crossProf.data?.length}`);

    // B sees only its own predictions (0 so far)
    const bOwn = await clientB.from('predictions').select('id');
    check('user B sees only own predictions', !bOwn.error && (bOwn.data?.length ?? 0) === 0, bOwn.error?.message || `count=${bOwn.data?.length}`);
  }

  await clientA.auth.signOut();
  await clientB.auth.signOut();
  report(userA, userB);
}

function report(userA, userB) {
  console.log('Results:');
  console.log(lines.join('\n'));
  console.log(`\n  ${passed} passed, ${failed} failed`);
  console.log('\nTest users created (delete from Supabase > Authentication > Users):');
  console.log(`  ${userA.email}`);
  console.log(`  ${userB.email}`);
  console.log(`\nVERIFY RESULT: ${failed === 0 ? 'PASS' : 'FAIL'}`);
  process.exit(failed === 0 ? 0 : 1);
}

main().catch((e) => {
  console.error('Unexpected error:', e);
  process.exit(3);
});
