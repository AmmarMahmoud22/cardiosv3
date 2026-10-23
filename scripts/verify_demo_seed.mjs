// ============================================================
// Cardios demo seed verification
// ============================================================
// Verifies that supabase/demo_seed_template.sql was applied and that the
// doctor account can see the seeded patient, device, alert, and note through
// normal RLS-protected Supabase queries.
//
// Required .env values:
//   VITE_SUPABASE_URL
//   VITE_SUPABASE_ANON_KEY
//   DEMO_DOCTOR_EMAIL
//   DEMO_DOCTOR_PASSWORD
//
// Optional .env values:
//   DEMO_PATIENT_EMAIL
//   DEMO_DEVICE_ID
// ============================================================

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { createClient } from '@supabase/supabase-js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');

function loadEnv() {
  const out = {};
  for (const name of ['.env.local', '.env']) {
    try {
      const text = readFileSync(join(ROOT, name), 'utf8');
      for (const line of text.split(/\r?\n/)) {
        const match = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/i);
        if (!match) continue;
        let value = match[2].trim();
        if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
          value = value.slice(1, -1);
        }
        if (!(match[1] in out)) out[match[1]] = value;
      }
    } catch {
      // Missing .env.local is fine.
    }
  }
  return out;
}

let passed = 0;
let failed = 0;
const lines = [];

function check(name, ok, detail = '') {
  if (ok) {
    passed++;
    lines.push(`  PASS  ${name}${detail ? ` - ${detail}` : ''}`);
  } else {
    failed++;
    lines.push(`  FAIL  ${name}${detail ? ` - ${detail}` : ''}`);
  }
}

async function main() {
  const env = loadEnv();
  const url = env.VITE_SUPABASE_URL;
  const anon = env.VITE_SUPABASE_ANON_KEY || env.VITE_SUPABASE_PUBLISHABLE_KEY;
  const doctorEmail = env.DEMO_DOCTOR_EMAIL || 'doctor@cardios.demo';
  const doctorPassword = env.DEMO_DOCTOR_PASSWORD;
  const patientEmail = env.DEMO_PATIENT_EMAIL || 'patient@cardios.demo';
  const deviceId = env.DEMO_DEVICE_ID || 'esp32-ad8232-demo';

  if (!url || !anon) {
    console.error('Missing VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY in .env.');
    process.exit(2);
  }

  if (!doctorPassword) {
    console.error('Missing DEMO_DOCTOR_PASSWORD in .env. Add it after creating the demo doctor account.');
    process.exit(2);
  }

  const supabase = createClient(url, anon, {
    auth: { persistSession: false, autoRefreshToken: false },
  });

  const signIn = await supabase.auth.signInWithPassword({
    email: doctorEmail,
    password: doctorPassword,
  });
  check('doctor sign-in succeeds', !signIn.error && !!signIn.data.user, signIn.error?.message);
  if (signIn.error || !signIn.data.user) return report();

  const doctorId = signIn.data.user.id;
  const role = await supabase
    .from('user_roles')
    .select('role,is_banned')
    .eq('user_id', doctorId)
    .maybeSingle();
  check('doctor role is active', !role.error && role.data?.role === 'doctor' && !role.data?.is_banned, role.error?.message || `role=${role.data?.role}`);

  const profile = await supabase
    .from('profiles')
    .select('id,email')
    .eq('email', patientEmail)
    .maybeSingle();
  check('doctor can read seeded patient profile', !profile.error && !!profile.data?.id, profile.error?.message || profile.data?.email);

  const patientId = profile.data?.id;
  if (!patientId) return report();

  const link = await supabase
    .from('doctor_patients')
    .select('doctor_id,patient_id,status')
    .eq('doctor_id', doctorId)
    .eq('patient_id', patientId)
    .maybeSingle();
  check('active doctor-patient link exists', !link.error && link.data?.status === 'active', link.error?.message || `status=${link.data?.status}`);

  const device = await supabase
    .from('devices')
    .select('device_id,display_name,patient_id,status')
    .eq('device_id', deviceId)
    .maybeSingle();
  check('seeded device is assigned to patient', !device.error && device.data?.patient_id === patientId && device.data?.status === 'active', device.error?.message || device.data?.display_name);

  const alerts = await supabase
    .from('alerts')
    .select('id,severity,status,title')
    .eq('patient_id', patientId)
    .order('created_at', { ascending: false });
  check('doctor can read seeded patient alerts', !alerts.error && (alerts.data?.length ?? 0) > 0, alerts.error?.message || `count=${alerts.data?.length}`);

  const notes = await supabase
    .from('doctor_notes')
    .select('id,body,visible_to_patient')
    .eq('doctor_id', doctorId)
    .eq('patient_id', patientId)
    .order('created_at', { ascending: false });
  check('doctor can read seeded notes', !notes.error && (notes.data?.length ?? 0) > 0, notes.error?.message || `count=${notes.data?.length}`);

  const predictions = await supabase
    .from('predictions')
    .select('id,prediction_result')
    .eq('user_id', patientId);
  check('doctor can read patient risk history', !predictions.error && (predictions.data?.length ?? 0) > 0, predictions.error?.message || `count=${predictions.data?.length}`);

  const ecg = await supabase
    .from('ecg_analyses')
    .select('id,prediction,confidence')
    .eq('user_id', patientId);
  check('doctor can read patient ECG history', !ecg.error && (ecg.data?.length ?? 0) > 0, ecg.error?.message || `count=${ecg.data?.length}`);

  await supabase.auth.signOut();
  report();
}

function report() {
  console.log('Results:');
  console.log(lines.join('\n'));
  console.log(`\n  ${passed} passed, ${failed} failed`);
  console.log(`\nDEMO SEED VERIFY RESULT: ${failed === 0 ? 'PASS' : 'FAIL'}`);
  process.exit(failed === 0 ? 0 : 1);
}

main().catch((error) => {
  console.error('Unexpected error:', error);
  process.exit(3);
});
