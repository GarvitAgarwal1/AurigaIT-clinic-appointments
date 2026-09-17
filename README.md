# Clinic Desk

A small full-stack clinic appointment booking system for front-desk staff. It uses FastAPI, SQLAlchemy, SQLite, and a server-rendered HTML shell with `fetch` calls to the REST API.

## Run

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/`, register a staff account, then log in at the staff desk. The SQLite file `clinic.db` is created automatically. API documentation is available at `/docs`.

## Test

Run the isolated test suite inside the project virtual environment:

```bash
.venv/bin/python -m pytest
```

The tests cover password hashing, adjacent and overlapping appointment slots, safe rescheduling, cancellation fees, and page rendering. The local `.venv`, pytest cache, and generated SQLite database are ignored by Git.

## Schema

`app/models.py` defines the persisted relational schema:

- `users`: unique username and PBKDF2 password hash for front-desk authentication.
- `doctors`: doctor name and specialty.
- `patients`: patient name and contact details.
- `appointments`: foreign keys to `doctors` and `patients`, start/end times, status, cancellation fee, and notes.

Foreign keys are declared with SQLAlchemy `ForeignKey` columns. SQLite is file-based and tables are created by `Base.metadata.create_all()` on startup.

## Overlap prevention

`app/services.py:book_appointment` starts a SQLite `BEGIN IMMEDIATE` transaction. This obtains SQLite's write lock before checking for conflicts, so two writers cannot both pass the check and insert at the same time.

The conflict predicate is:

```text
same doctor AND status = booked
AND new_start < existing_end
AND new_end > existing_start
```

This treats touching slots such as 10:00-10:30 and 10:30-11:00 as valid, but rejects every real overlap. Cancelled appointments are ignored and can therefore free their time. The same locked check is used for rescheduling. SQLite cannot express a general time-range exclusion constraint, so the transaction lock plus server-side check is the database-level protection used here.

## Cancellation rule

Cancellation is free when it happens at least two hours before the appointment start. A cancellation less than two hours before the start costs `$25.00`. The rule is implemented in one service function and stored on the appointment as `cancellation_fee`; cancelling twice does not charge twice.

## REST API

All paths below except authentication require the signed login session cookie.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/register` | Register a front-desk user |
| POST | `/api/auth/login` | Log in and issue a session cookie |
| POST | `/api/auth/logout` | Clear the session |
| GET | `/api/doctors` | Paginated, sorted doctor list |
| POST | `/api/doctors` | Create a doctor |
| GET | `/api/doctors/{doctor_id}` | Get one doctor |
| PUT | `/api/doctors/{doctor_id}` | Replace a doctor |
| DELETE | `/api/doctors/{doctor_id}` | Delete an unused doctor |
| GET | `/api/patients` | Paginated, sorted name search |
| POST | `/api/patients` | Create a patient |
| GET | `/api/patients/{patient_id}` | Get one patient |
| PUT | `/api/patients/{patient_id}` | Replace a patient |
| DELETE | `/api/patients/{patient_id}` | Delete an unused patient |
| GET | `/api/appointments` | Paginated, sorted appointments; supports `patient_name` and `doctor_id` |
| POST | `/api/appointments` | Book with transactional overlap protection |
| GET | `/api/appointments/{appointment_id}` | Get one appointment |
| PATCH | `/api/appointments/{appointment_id}` | Edit notes or safely reschedule |
| POST | `/api/appointments/{appointment_id}/cancel` | Cancel and calculate fee |
| DELETE | `/api/appointments/{appointment_id}` | Permanently delete an appointment |
| GET | `/api/appointments/day/{doctor_id}?day=YYYY-MM-DD` | Full doctor's day, sorted by start time |
| PATCH | `/api/appointments/{appointment_id}/reschedule` | Change start/end safely while keeping doctor and patient |
| POST | `/api/clock` or `/clock` | Set the simulated absolute current time; generates reminders and sweeps no-shows |
| GET | `/api/outbox` or `/outbox` | Return all generated reminder notifications |

List endpoints accept `page` and `size` (bounded to 100, or 200 for a day schedule). Doctor and appointment lists also accept sorting parameters as documented by their API behavior.

## New simulated-time features

`POST /api/clock` (also available as `POST /clock`) accepts an absolute timestamp and never a duration:

```json
{"current_time": "2030-01-02T09:15:00Z"}
```

The response is:

```json
{"current_time": "2030-01-02T09:15:00", "message": "Clock advanced; reminders generated and no-shows swept"}
```

The simulated clock cannot move backwards. When it crosses into a calendar day, one outbox reminder is generated per patient with an appointment on each crossed day. Every clock request also marks a still-`booked` appointment as `no_show` once simulated time reaches 30 minutes after its start. Cancelled and completed appointments are skipped.

`PATCH /api/appointments/{appointment_id}/reschedule` accepts:

```json
{"starts_at": "2030-01-02T10:00:00Z", "ends_at": "2030-01-02T10:30:00Z"}
```

It returns the updated appointment. The doctor and patient IDs remain unchanged, and an overlapping booking for that doctor returns `409` without changing the original appointment.

Patient list/search results include `phone` and the patient's aggregated `cancellation_amount`.

## Manual proof checklist

1. Register and log in, create one doctor and two patients.
2. Book 10:00-11:00 for the doctor. Try 10:30-10:45 for that doctor: the API must return `409`; try the same time for another doctor: it must succeed.
3. Book 11:00-12:00: it should succeed because touching boundaries do not overlap.
4. Try two POST requests for the same doctor and overlapping times concurrently (for example with two terminal `curl` processes): one must return `201`, the other `409`.
5. Cancel an appointment more than two hours away and confirm `cancellation_fee` is `0.00`; cancel one inside two hours and confirm it is `25.00`.
6. Search a patient by partial name, inspect a doctor's day, and verify results remain sorted and paginated with `?page=1&size=1`.

## Project layout

- `app/models.py`: relational schema
- `app/services.py`: booking and cancellation business rules
- `app/routers_auth.py`: authentication routes
- `app/routers_resources.py`: doctor, patient, and appointment routes
- `app/templates/`: landing page and staff desk
- `app/static/style.css`: minimal responsive styling