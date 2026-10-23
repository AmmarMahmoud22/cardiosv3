# Cardios — Supabase setup from scratch

Everything here was verified against PostgreSQL 16 before shipping: `bootstrap.sql`
was applied to an empty database, run a second time to confirm it is idempotent,
and then exercised to confirm the signup trigger provisions users and that
row-level security genuinely isolates one user's data from another's.

---

## What actually needs a database

| Feature | Needs Supabase? |
|---|---|
| Heart-risk prediction (`/predict`) | No — pure API call |
| ECG file analysis (`/predict-ecg`) | No |
| **Clinical Evidence Advisor** (`/evidence`) | **No** — the corpus lives in local SQLite, and the page is public |
| Login / signup | Yes |
| Saved history, profile, doctor and admin views | Yes |

The three intelligence layers all work without a database. Supabase provides
identity and persistence around them.

`/evidence` is deliberately **not** behind login: it reads only published
guideline text, holds no patient data, and gating it made the hackathon feature
fail whenever Supabase was unavailable — a dependency it does not otherwise
have. The client also treats the auth header as optional there and gives up on
it after two seconds, so a paused project cannot stall a guideline lookup.
Every other clinical page still requires signing in.

---

## Step 1 — Is the old project recoverable?

Free-tier Supabase projects pause after a week of inactivity, and paused projects
can be restored with their data intact. Deleted projects cannot.

1. Open <https://supabase.com/dashboard>
2. Find the project (the old one was `ataiqwgfjffwcnsrnlse`)
3. If it shows **Paused** → click **Restore**. Wait a few minutes, then skip to
   Step 3 and just refresh your keys.
4. If it is gone → create a new one, Step 2.

---

## Step 2 — Create a new project

1. **New project** → name it `cardios`
2. Choose a strong database password and **save it somewhere** — it cannot be
   recovered later, only reset
3. Pick the region closest to you
4. Wait for provisioning (~2 minutes)

---

## Step 3 — Create the schema

1. In the dashboard: **SQL Editor** → **New query**
2. Open `supabase/bootstrap.sql`, copy all of it, paste, **Run**
3. Expect "Success. No rows returned". Notices reading *"... does not exist,
   skipping"* are normal — those are the idempotency guards.

Then confirm it worked: **New query** → paste `supabase/bootstrap_verify.sql` →
**Run**. Every row should read `PASS`:

```
 tables                     | 13 / 13                | PASS
 row-level security         | 13 / 13 protected      | PASS
 policies                   | 40 defined             | PASS
 role helpers               | is_admin, is_doctor    | PASS
 signup trigger             | on_auth_user_created   | PASS
```

---

## Step 4 — Point the app at it

**Settings → API**, then copy into `.env`:

```
VITE_SUPABASE_URL=https://<your-project-ref>.supabase.co
VITE_SUPABASE_ANON_KEY=<the anon / public key>
```

Use the **anon public** key, not the service-role key. The service-role key
bypasses row-level security completely and must never reach a browser.

Restart the frontend afterwards — Vite only reads `.env` at startup.

---

## Step 5 — Create accounts

**Authentication → Providers → Email**: for a hackathon demo turn
*Confirm email* **off**, or every test signup waits on an inbox.

Then sign up through the app itself. The `on_auth_user_created` trigger creates
the profile and assigns the `patient` role automatically — verified in testing.

To promote someone, in the SQL Editor:

```sql
-- make a user a doctor (or 'admin')
update public.user_roles
   set role = 'doctor'
 where user_id = (select id from auth.users where email = 'you@example.com');
```

---

## Step 6 — Seed the demo (optional)

Empty doctor and admin portals demo badly. `supabase/demo_seed.sql` fills them
with a coherent three-month clinical story: risk assessments trending from high
to low, ECG analyses improving from PVCs to normal, eight weeks of monitoring
check-ins, and clinician notes.

1. Sign up two accounts through the app, e.g. `doctor@cardios.demo` and
   `patient@cardios.demo` (passwords are hashed by Supabase Auth, so accounts
   cannot be created from SQL — the script wires up existing users).
2. Edit the two emails at the top of `supabase/demo_seed.sql`.
3. Run it in the SQL Editor.

It promotes one account to `doctor`, links the pair, and writes the history. Safe
to re-run — clinical rows are rewritten rather than duplicated. If an account is
missing it stops with a message naming the one to create rather than failing
obscurely.

Verified against PostgreSQL 16: after seeding, the doctor sees all 3 risk
assessments, 3 ECG analyses, 5 check-ins and 3 notes, while the patient sees
their own records and only the 2 notes marked visible to them — the internal
note stays hidden by row-level security.

---

## What the schema contains

**Identity** `profiles` · `extended_profiles` · `user_roles`
**Clinical records** `predictions` · `ecg_analyses` · `monitoring_checkins`
**Care team** `doctor_patients` · `doctor_notes` · `devices` · `alerts`
**Evidence corpus** `clinical_documents` · `clinical_chunks` · `rag_ingest_reports`

All 13 have row-level security enabled, with 40 policies. Patients reach only
their own rows; doctors reach their assigned patients through `is_doctor()`;
admins read across the platform through `is_admin()`.

The evidence tables are created but stay empty: the running app keeps its vectors
in local SQLite, and the pgvector column is intentionally commented out because
`vector(N)` needs the exact dimension of whichever embedding model is chosen.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `Invalid API key` | Wrong key, or the frontend was not restarted after editing `.env` |
| Login succeeds, profile empty | Trigger missing — re-run `bootstrap.sql` |
| `relation "profiles" does not exist` | `bootstrap.sql` was never run, or run on a different project |
| Signup hangs | Email confirmation is on — turn it off, or confirm via the inbox |
| Everything 401s | Row-level security is working and the session expired; sign in again |
