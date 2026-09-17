# AI LOGS

PROJECT: Clinic Appointment Booking System (Full-Stack)

CONTEXT
I'm building a full-stack web application for a coding assessment with a 2-hour time limit. 
I need a working, well-structured solution — not just a stub.

PROBLEM STATEMENT
A busy clinic with a few doctors. The front desk books patients into time slots, but keeps 
double-booking a doctor or letting two patients grab the same slot. Patients cancel — if they 
cancel in good time it's free, but a late cancellation should carry a small fee. The desk needs 
to see a doctor's day, find a patient's appointment by name, and never let two appointments for 
the same doctor overlap.

Build this for the front desk staff, for any generic clinic. Priority order:
1. Conflict-free booking (no doctor is ever double-booked — overlapping time slots for the 
   same doctor must be rejected at the database/API level, not just the UI)
2. Correct cancellation-fee rule (on-time cancellation = free, late cancellation = small fee — 
   I need you to help me define a sensible cutoff, e.g. "less than 2 hours before the 
   appointment start time" or similar, and apply it consistently)
3. Lookups: view a doctor's full day schedule, and search for a patient's appointment by name

REQUIRED TECH STACK
- Backend: Python + FastAPI
- ORM/DB: SQLAlchemy + SQLite (file-based, no external DB server)
- Frontend: Jinja2 server-rendered templates (simple, functional UI — not fancy) OR a minimal 
  HTML/JS frontend calling the REST API via fetch — pick whichever is faster to implement 
  end-to-end correctly
- Auth: front-desk user registration and login (hashed passwords, session or JWT-based)

MANDATORY DELIVERABLES (all required — do not skip any)
1. Real relational schema with proper foreign keys (users, doctors, patients, appointments 
   at minimum) — persisted in SQLite, not in-memory
2. REST API endpoints covering all core operations (CRUD on appointments, doctors, patients, 
   auth, search) — must be listed explicitly with method + path + purpose
3. A usable UI over those APIs (forms to book/cancel, a doctor's-day view, a patient search view)
4. User registration and login (for front-desk staff)
5. Search functionality (find appointment/patient by name)
6. Pagination and sorting on any list views (e.g. appointment lists, doctor schedules)
7. A one-page landing page describing: what the product is, key features, target audience, 
   how it helps, and three features planned for the future

CRITICAL CONSTRAINTS
- The double-booking prevention must be enforced server-side/DB-side (e.g. an overlap check 
  in the booking transaction, ideally backed by a DB constraint or a locking/transaction 
  strategy), not just client-side validation
- Explain the overlap-detection logic clearly (I need to be able to explain it if asked)
- Keep the codebase simple and readable given the time constraint — favor working and 
  correct over elaborate architecture

WHAT I NEED FROM YOU
1. The complete database schema (SQL or SQLAlchemy models)
2. All FastAPI route/router code, organized by resource
3. The overlap-prevention logic for booking, explained
4. The cancellation fee logic, explained
5. Minimal but functional templates/frontend code
6. A list of all REST endpoints (method, path, description) — I need this for my README
7. Suggestions for what to test manually to prove no double-booking is possible

Please build this iteratively — start with the schema and overlap logic since those are 
highest priority, then auth, then the rest.


I’ll first inspect the repository and README to confirm the starting point, then I’ll establish the smallest runnable FastAPI/SQLAlchemy slice around schema and transactional overlap checks before layering auth, routes, UI, and documentation. The first cheap discriminator will be whether the repo already has a Python app scaffold or is truly empty.

Read 

Read 

Read memory

Read memory

The workspace is effectively empty: only a placeholder README exists, so there is no existing architecture to preserve. I’m going to build a compact layered app now: SQLAlchemy models plus a booking service that performs an overlap query inside a write transaction, then resource routers and a server-rendered staff UI on top of it.

Created 5 todos

The controlling invariant is clear: an appointment conflicts exactly when `new_start < existing_end AND new_end > existing_start`, ignoring cancelled rows. Because SQLite has no native exclusion constraint, the service will serialize the booking transaction with `BEGIN IMMEDIATE`, re-check that predicate server-side, and only then insert; the focused check after this edit will exercise adjacent, overlapping, and concurrent-style booking cases.

Generating patch (164 lines) in , , , , , 


```

```

```

```

```

```

```

```

```

```


Ran terminal command:  python -m pip install -q -r requirements.txt && python - <<'PY'
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Doctor, Patient
from app.services import book_appointment
from fastapi import HTTPException

engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False})
Base.metadata.create_all(engine)
db = sessionmaker(bind=engine)()
doc, patient = Doctor(name='Dr Test'), Patient(name='Pat Test')
db.add_all([doc, patient]); db.commit()
start = datetime.utcnow() + timedelta(days=1)
book_appointment(db, doc.id, patient.id, start, start + timedelta(minutes=30))
book_appointment(db, doc.id, patient.id, start + timedelta(minutes=30), start + timedelta(minutes=60))
try:
    book_appointment(db, doc.id, patient.id, start + timedelta(minutes=15), start + timedelta(minutes=45))
except HTTPException as exc:
    assert exc.status_code == 409
else:
    raise AssertionError('overlap was accepted')
print('overlap invariant check passed')
PY

The first focused check passed: adjacent appointments are accepted, while a 15-minute overlap is rejected with HTTP 409. I’m moving up one layer now, keeping the same service as the single booking path while adding authenticated API routers and HTML pages that call/use those resource operations.

Generating patch (256 lines) in , , , , 


```

```

```

```

```

```

```

```

```

```


Ran terminal command:  python -m compileall -q app && python - <<'PY'
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)
name = 'desk_test_user'
response = client.post('/api/auth/register', json={'username': name, 'password': 'password123'})
assert response.status_code in (201, 409), response.text
assert client.post('/api/auth/login', json={'username': name, 'password': 'password123'}).status_code == 200
assert client.get('/api/doctors').status_code == 200
print('API import, auth, and protected route check passed')
PY

The API foundation compiles and the smoke test passes through registration, login, and a protected endpoint. I’m adding the actual staff surface next, plus the missing single-resource GETs so “CRUD” is literal for doctors and patients; the UI will stay deliberately plain and use `fetch` against the same authenticated REST API.

Generating patch (88 lines) in , , , , 


```

```

```

```

```

```

```

```

```

```


Ran terminal command:  python -m compileall -q app && python - <<'PY'
from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
username='integration_staff_2026'
r=client.post('/api/auth/register',json={'username':username,'password':'password123'})
assert r.status_code in (201,409),r.text
assert client.post('/api/auth/login',json={'username':username,'password':'password123'}).status_code==200
d=client.post('/api/doctors',json={'name':'Dr Integration','specialty':'Family medicine'})
assert d.status_code==201,d.text
p=client.post('/api/patients',json={'name':'Patient Integration','phone':'555'}); assert p.status_code==201,p.text
from datetime import datetime,timedelta
start=(datetime.utcnow()+timedelta(days=3)).replace(microsecond=0)
payload={'doctor_id':d.json()['id'],'patient_id':p.json()['id'],'starts_at':start.isoformat(),'ends_at':(start+timedelta(hours=1)).isoformat()}
assert client.post('/api/appointments',json=payload).status_code==201
conflict=payload|{'starts_at':(start+timedelta(minutes=20)).isoformat(),'ends_at':(start+timedelta(minutes=40)).isoformat()}
assert client.post('/api/appointments',json=conflict).status_code==409
assert client.get('/').status_code==200 and client.get('/app').status_code==200
print('full API and page smoke check passed')
PY

Checked , no problems found

The browser-facing pages and end-to-end smoke test are working, including protected CRUD, booking conflict rejection, and both HTML routes. One correctness edge surfaced in review before documentation: rescheduling currently deletes before rebooking, which could lose the appointment if the new slot conflicts, so I’m tightening that path to use the same atomic lock-and-check pattern as initial booking.

Generating patch (50 lines) in , , 

Generating patch (45 lines) in , 


```

```

```

```


Ran terminal command:  python -m compileall -q app && python - <<'PY'
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from app.database import Base
from app.models import Doctor, Patient
from app.services import book_appointment, reschedule_appointment
engine=create_engine('sqlite:///:memory:'); Base.metadata.create_all(engine); db=sessionmaker(bind=engine)()
doc, pat=Doctor(name='D'), Patient(name='P'); db.add_all([doc,pat]); db.commit(); start=datetime.utcnow()+timedelta(days=1)
a=book_appointment(db,doc.id,pat.id,start,start+timedelta(hours=1)); b=book_appointment(db,doc.id,pat.id,start+timedelta(hours=2),start+timedelta(hours=3))
try: reschedule_appointment(db,b,start+timedelta(minutes=30),start+timedelta(minutes=90))
except HTTPException as exc: assert exc.status_code==409
else: raise AssertionError('conflicting reschedule accepted')
assert db.get(type(b),b.id).starts_at == start+timedelta(hours=2)
print('atomic reschedule check passed')
PY

The reschedule check now behaves correctly: a conflicting move returns 409 and leaves the original appointment untouched. I’m finishing the assessment-facing README with schema, invariant explanation, fee rule, full endpoint inventory, setup, and a short manual test script so the implementation is explainable as well as runnable.

Generating patch (95 lines) in 


```

```
Documentation is in place, including the exact endpoint table and a concurrency-oriented manual proof checklist. I’m doing the final quality pass now: compile/diagnostics, a cancellation cutoff check, and a quick diff review for accidental omissions; I’ll also align rescheduling with the “no past starts” rule used by new bookings.

Generating patch (10 lines) in 


```

```


Ran terminal command:  python -m compileall -q app && python - <<'PY'
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Doctor, Patient
from app.services import book_appointment, cancel_appointment
engine=create_engine('sqlite:///:memory:'); Base.metadata.create_all(engine); db=sessionmaker(bind=engine)()
d,p=Doctor(name='D'),Patient(name='P'); db.add_all([d,p]); db.commit()
future=datetime.utcnow()+timedelta(hours=3); a=book_appointment(db,d.id,p.id,future,future+timedelta(minutes=30)); cancel_appointment(db,a); assert a.cancellation_fee==Decimal('0.00')
soon=datetime.utcnow()+timedelta(hours=1); b=book_appointment(db,d.id,p.id,soon,soon+timedelta(minutes=30)); cancel_appointment(db,b); assert b.cancellation_fee==Decimal('25.00')
print('compile and cancellation cutoff checks passed')
PY

git diff --stat && git status --short

Checked , no problems found

Final checks pass: diagnostics are clean, the two-hour boundary behavior is verified on both sides, and the change set contains the complete app. The smoke tests created a local `clinic.db` artifact, so I’m excluding that runtime file before closing and will report the exact run command and validation results.

Generating patch (7 lines) in 


```

```


Ran terminal command:  rm -f clinic.db && git status --short

Implemented the complete clinic booking system.

Key pieces:
- SQLAlchemy relational schema for users, doctors, patients, and appointments
- PBKDF2 password hashing with session-based authentication
- Transactional SQLite overlap prevention using `BEGIN IMMEDIATE`
- Two-hour cancellation cutoff with `$25.00` late fee
- Full REST CRUD APIs with pagination, sorting, search, and doctor-day schedules
- Functional staff dashboard for login, booking, cancellation, patient search, and schedules
- Landing page describing the product and future features
- Comprehensive setup, API documentation, overlap explanation, and manual test checklist in `README.md`

Main implementation files:
- `models.py`
- `services.py`
- `routers_auth.py`
- `routers_resources.py`
- `dashboard.html`

Run it with:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Validation completed successfully: compilation, authentication, protected CRUD, overlap rejection, safe rescheduling, page rendering, and cancellation-fee cutoff checks.

Made changes.

can you remove the view documentation button from the home screen and when i login i see doctor name etc there are many fields which are empty so store some of the doctor's name about 4 , some test patient data in the database so that i can check and make the login page ui a little more cleaner 

I’ll update the landing page and dashboard styling, then seed a few doctors and patients automatically on startup so the logged-in desk is immediately testable. I’ll first inspect the current app startup, templates, and database models to keep the seed data idempotent and avoid duplicating records.

Read 

Read 

Read 

Read 

Read 

The current UI has the documentation link exactly where you described, and the empty selectors come from a genuinely empty SQLite file rather than a rendering issue. I’ll remove that link, add idempotent starter records for four doctors and four patients during app startup, and give the login/register area a clearer two-card layout with better spacing and hierarchy.

Generating patch (47 lines) in , , , , 


```

```

```

```

```

```

```

```

```

```
The requested changes are now in place: the home screen has only the staff entry action, and startup seeding is idempotent, so existing data is preserved while an empty database receives four doctors and four patients. I’m running a focused check for syntax, seeded record counts, the removed link, and the login page response.

Ran terminal command:  python -m compileall -q app && python - <<'PY'
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Doctor, Patient

client = TestClient(app)
assert client.get('/').status_code == 200
assert '/docs' not in client.get('/').text
assert client.get('/app').status_code == 200
with SessionLocal() as db:
    assert db.query(Doctor).count() >= 4
    assert db.query(Patient).count() >= 4
    print(f'seeded doctors={db.query(Doctor).count()} patients={db.query(Patient).count()}')
print('UI and seed checks passed')
PY
rm -f clinic.db

Checked , , , , , no problems found

Done.

Changes made:

- Removed the **API documentation** button from the home page.
- Added 4 starter doctors:
  - Dr. Maya Patel
  - Dr. James Wilson
  - Dr. Sofia Nguyen
  - Dr. Daniel Brooks
- Added 4 sample patients with phone numbers and emails.
- Seed data is inserted automatically when the database is empty.
- Cleaned up the login page with:
  - Clearer layout
  - Separate login and registration sections
  - Better spacing and typography
  - Improved mobile layout

Validation passed:

```text
seeded doctors=4 patients=4
UI and seed checks passed
```

Start the app with:

```bash
uvicorn app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/app
```

Made changes.

in the login page first of all give me an eye button on password thingy and also the red text should appear where it is intended to if any invalid in register it should show their not in login

I’ll separate the login and registration feedback targets so validation errors stay with the form that caused them, then add accessible password visibility toggles to both password fields. I’ll keep the existing page structure and verify the rendered HTML contains both controls and independent message elements.

Generating patch (17 lines) in , 


```

```

```

```
The form targets are now independent: login errors write only to the login message, while registration errors and success messages write only beneath registration. Both password inputs have their own Show/Hide control; I’m removing one unnecessary JavaScript expression and then running the final page/compile checks.

Generating patch (6 lines) in 


```

```


Ran terminal command:  python -m compileall -q app && python - <<'PY'
from fastapi.testclient import TestClient
from app.main import app

html = TestClient(app).get('/app').text
assert html.count('data-password-toggle') == 2
assert 'id="login-message"' in html
assert 'id="register-message"' in html
assert "$('login-message').textContent=err.message" in html
assert "$('register-message').textContent=err.message" in html
assert '/docs' not in TestClient(app).get('/').text
print('password toggle and scoped validation checks passed')
PY
Completed with input:  python -m compileall -q app && python - <<'PY'
from fastapi.testclient import TestClient
from app.main import app

html = TestClient(app).get('/app').text
assert html.count('data-password-toggle') == 2
assert 'id="login-message"' in html
assert 'id="register-message"' in html
assert "$('login-message').textContent=err.message" in html
assert "$('register-message').textContent=err.message" in html
assert '/docs' not in TestClient(app).get('/').text
print('password toggle and scoped validation checks passed')
PY

Checked , , no problems found

The code diagnostics are clean; the validation script itself was too strict because it counted the JavaScript selector text in addition to the two rendered controls. I’m correcting that check to count the actual button elements and rerunning it.

Ran terminal command:  python -m compileall -q app && python - <<'PY'
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
html = client.get('/app').text
assert html.count('class="password-toggle"') == 2
assert 'id="login-message"' in html
assert 'id="register-message"' in html
assert "$('login-message').textContent=err.message" in html
assert "$('register-message').textContent=err.message" in html
assert '/docs' not in client.get('/').text
print('password toggle and scoped validation checks passed')
PY

Made changes.

After we login and enter we should also check and make a new portion if the user is new also the doctor's appointment thing is not working i booked an appointment and it is not showing after i do 2 tries also the amount thingy is also not showing like there should be a fair amount charged if they are cancelling the appointment after their time is left before

I’m tracing the actual runtime behavior behind the booking and cancellation symptoms now: the likely issue is that the booking UI is sending the wrong datetime format for the browser form, and the cancellation fee is only updating on the server-side object but not being rendered in the UI or shown as part of the schedule. I’m fixing both at the root rather than patching the symptoms.

Read 

Replacing 27 lines with 41 lines in 

Read 

Read 

Read 

Replacing 13 lines with 63 lines in 

Searched for regex `welcome-card|auth-layout|password-field|password-toggle` (`**/app/**`), 3 results

Replacing 28 lines with 83 lines in , 


```

```


Read 

Read 

Multi-Replace String in Files

Made changes.

Add 3 new features to the existing clinic booking app, without breaking current functionality:

1. RESCHEDULE — PATCH /appointments/{id}/reschedule: change start/end time, keep same 
   doctor_id/patient_id, re-run overlap check against the new slot (exclude this 
   appointment's own row from the conflict query).

2. VIRTUAL CLOCK + REMINDERS — POST /clock: sets/advances the app's simulated "now" 
   (don't use real datetime.now() for anything below). When it crosses into a new day, 
   generate a reminder notification for every patient with an appointment "today" and 
   store it in an outbox table. GET /outbox: returns all generated notifications.

3. AUTO NO-SHOW — On every POST /clock call, also sweep appointments: any still "booked" 
   where current_time >= start_time + 30min gets marked "no_show" (skip cancelled/completed).

Be explicit about POST /clock's request/response shape (pick one: absolute timestamp to 
jump to, or duration to advance) since it's graded directly. List all new/changed endpoints 
(method + path + request/response) at the end for my README.
Btw your cancellation policy is still not working it is just showing 0 dollars even if i cancel after my appointed time so fix that and also customer list should also specify their number and cancellation amount

I’ll trace the current appointment model, service clock usage, cancellation path, and dashboard rendering first. Then I’ll add the simulated clock/outbox schema and routes, fix cancellation against simulated time, and expose patient phone plus cancellation fee in the visible lists.

Read 

Read 

Read 

Read 

Read 

The root causes are visible: cancellation and booking compare against real UTC, there is no persisted simulated clock or outbox model, and patient search only returns contact details without an aggregated fee field. I’m adding a single persisted clock state, an outbox table, a dedicated reschedule route, and making cancellation/no-show/reminder decisions use that clock consistently.

Generating patch (42 lines) in , 


```

```

```

```


Generating patch (76 lines) in 


```

```


Generating patch (65 lines) in , 


```

```

```

```
The API layer now has the new persisted state and business rules, including a dedicated reschedule endpoint and patient `cancellation_amount`. I’m adding a small dashboard display for patient phone/fees and a clock control so the new behavior can be exercised without manually crafting requests, then I’ll add tests for reminders, no-shows, rescheduling, and late cancellation.

Generating patch (15 lines) in , 

Generating patch (20 lines) in , 

Generating patch (14 lines) in 


```

```


Generating patch (5 lines) in 


```

```


Generating patch (44 lines) in 


```

```


Generating patch (9 lines) in 


```

```
The core implementation is complete, including deterministic simulated-time tests. One test setup detail was corrected so it updates the existing clock row instead of inserting a duplicate; I’m now running the suite and static diagnostics to catch integration issues in the new model relationships and routes.

Ran terminal command:  .venv/bin/python -m pytest

Checked , no problems found

All seven tests pass, including reminder deduplication, no-show timing, and late cancellation. I found one runtime edge worth fixing before documenting: the dashboard sends ISO timestamps with `Z` while SQLite stores naive UTC datetimes, so I’m normalizing incoming clock/reschedule/booking timestamps and exposing both `/api/...` and the requested root `/clock` and `/outbox` paths.

Generating patch (48 lines) in , 


```

```

```

```


Generating patch (38 lines) in 


```

```


Generating patch (16 lines) in 


```

```


Read , lines 35 to 110

The timezone normalization is in place, and I caught a test-placement mistake before the final run: part of the reminder test’s assertions was accidentally attached to the timezone test. I’m moving those assertions back, then I’ll run the full suite and an API smoke check for authenticated `/clock`, `/outbox`, and `/reschedule`.

Generating patch (27 lines) in 


```

```


Ran terminal command:  .venv/bin/python -m pytest && .venv/bin/python -m compileall -q app

Ran terminal command:  .venv/bin/python - <<'PY'
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
username = 'feature_smoke_staff'
registered = client.post('/api/auth/register', json={'username': username, 'password': 'password123'})
assert registered.status_code in (201, 409), registered.text
assert client.post('/api/auth/login', json={'username': username, 'password': 'password123'}).status_code == 200

doc = client.post('/api/doctors', json={'name': 'Dr Feature Smoke', 'specialty': 'Testing'}).json()
patient = client.post('/api/patients', json={'name': 'Feature Patient', 'phone': '555-0199'}).json()
start = datetime(2040, 1, 2, 10, 0, tzinfo=timezone.utc)
payload = {'doctor_id': doc['id'], 'patient_id': patient['id'], 'starts_at': start.isoformat(), 'ends_at': (start + timedelta(minutes=30)).isoformat()}
appointment = client.post('/api/appointments', json=payload)
assert appointment.status_code == 201, appointment.text
appointment_id = appointment.json()['id']
rescheduled = client.patch(f'/api/appointments/{appointment_id}/reschedule', json={'starts_at': '2040-01-02T11:00:00Z', 'ends_at': '2040-01-02T11:30:00Z'})
assert rescheduled.status_code == 200, rescheduled.text
clock = client.post('/clock', json={'current_time': '2040-01-02T09:00:00Z'})
assert clock.status_code == 200, clock.text
assert client.get('/outbox').status_code == 200
print('API feature smoke check passed')
PY

The authenticated API smoke check passed for both `/api` and root aliases: rescheduling returned 200, `/clock` returned 200 with an absolute timestamp, and `/outbox` returned 200. I’m cleaning only the temporary smoke records I created and resetting the simulated clock so the app opens in a sensible state with the seeded clinic data intact.

Ran terminal command:  .venv/bin/python - <<'PY'
from datetime import datetime
from app.database import SessionLocal
from app.models import Appointment, ClockState, Doctor, OutboxNotification, Patient, User
with SessionLocal() as db:
    patient_ids = [p.id for p in db.query(Patient).filter(Patient.name == 'Feature Patient').all()]
    doctor_ids = [d.id for d in db.query(Doctor).filter(Doctor.name == 'Dr Feature Smoke').all()]
    if patient_ids:
        db.query(OutboxNotification).filter(OutboxNotification.patient_id.in_(patient_ids)).delete(synchronize_session=False)
        db.query(Appointment).filter(Appointment.patient_id.in_(patient_ids)).delete(synchronize_session=False)
        db.query(Patient).filter(Patient.id.in_(patient_ids)).delete(synchronize_session=False)
    if doctor_ids:
        db.query(Appointment).filter(Appointment.doctor_id.in_(doctor_ids)).delete(synchronize_session=False)
        db.query(Doctor).filter(Doctor.id.in_(doctor_ids)).delete(synchronize_session=False)
    db.query(User).filter(User.username == 'feature_smoke_staff').delete(synchronize_session=False)
    clock = db.get(ClockState, 1)
    if clock:
        clock.current_time = datetime.utcnow()
    db.commit()
print('temporary smoke data removed; simulated clock reset')
PY

Implemented all requested features.

### Added

- `PATCH /api/appointments/{id}/reschedule`
  - Also available through existing appointment APIs
  - Rechecks overlaps
  - Excludes the appointment being rescheduled
  - Keeps the same doctor and patient
  - Returns `409` if the new slot conflicts

- `POST /clock` and `POST /api/clock`
  - Uses an absolute timestamp:
    ```json
    {
      "current_time": "2030-01-02T09:15:00Z"
    }
    ```
  - Cannot move backwards
  - Generates reminder notifications when entering new days
  - Automatically marks bookings as `no_show` 30 minutes after their start

- `GET /outbox` and `GET /api/outbox`
  - Returns generated reminder notifications

- Cancellation policy fixed
  - Cancellation at least 2 hours before appointment: `$0.00`
  - Cancellation less than 2 hours before appointment: `$25.00`
  - Cancellation after appointment time: `$25.00`
  - Uses the simulated clock rather than real time

- Patient list now includes:
  - Patient name
  - Phone number
  - Email
  - Total cancellation amount

- Dashboard now includes a simulated clock control for testing reminders, no-shows, and late cancellations.

Updated documentation is in `README.md`.

Validation completed:

```text
8 passed
```

The only output is existing Python/dependency deprecation warnings for `datetime.utcnow()`.

Made changes.