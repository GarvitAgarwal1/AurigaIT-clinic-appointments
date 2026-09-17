# Reasoning

## Understanding the problem

The brief described a clinic front desk that keeps double-booking doctors and mishandling
cancellations, with no further spec given beyond that and the required deliverables. I
prioritized in this order: (1) make double-booking impossible, (2) get the cancellation-fee
rule right, (3) build the lookups (doctor's day, patient search) on top of a schema that
already guarantees the first two, (4) the reschedule/notification/no-show twists once the
core was solid.

## Tech stack

FastAPI + SQLAlchemy + SQLite, with a simple server-rendered frontend. SQLite needs no
separate server to set up, FastAPI's automatic `/docs` let me test endpoints before the UI
existed, and the whole stack runs with one command — all of which mattered given the time
limit. I kept the frontend intentionally simple since the hard part of this problem is the
booking logic, not the UI polish.

## Project structure

Business logic is split out of the route handlers to keep things testable and readable:
`models.py`/`schemas.py` define the data shapes, `services.py` holds the core booking/
cancellation/reschedule logic, `notification_service.py` owns the virtual clock, reminder
generation, and no-show sweeping, `seed.py` seeds fixed demo data on first run, and
`security.py` handles password hashing and session auth. `routers_auth.py` and
`routers_resources.py` stay thin — they validate input and call into services.

## Data model

Four core tables: `users` (front-desk login), `doctors`, `patients`, `appointments`. Every
domain table carries a `user_id` so ownership can be enforced at the query level. Appointments
store `doctor_id`, `patient_id`, `start_time`, `end_time`, and `status`
(booked/cancelled/completed/no_show).

## Overlap-prevention logic

Two ranges for the same doctor overlap if `existing_start < new_end AND existing_end >
new_start`, scoped to the same doctor, same account, and `booked` status. Before any insert
or reschedule, I take a SQLite write lock, then run this check inside that same transaction,
so the conflict check and the write happen atomically — two near-simultaneous booking
requests for the same slot can't both slip through a race condition. A match is rejected
with a 409.

## Account scoping

Every major read and write is filtered by the logged-in user's `user_id` — doctors, patients,
appointments, all of it. This was a real bug I hit early on: appointment data was leaking
across accounts because queries weren't scoped, and sessions were persisting in a way that
skipped login on restart. I fixed both — every restart now requires logging in again, and
one account can never see or modify another account's data.

## Cancellation-fee rule

The fee scales with how close to the appointment the cancellation happens: free if
cancelled more than 2 hours before the start time, a $25 fee if cancelled inside that
2-hour window but before the appointment starts, and a $1 fee if cancelled after the
appointment has already started. This felt like the right shape for the rule described in
the brief — the fee should reflect the actual state of the appointment at cancellation
time, not a flat penalty.

## Reschedule

Reschedule keeps the same doctor and patient, and re-runs the exact overlap check above
against the newly requested time (excluding the appointment's own row from the conflict
query). If the requested time conflicts with another appointment for that doctor, the
reschedule is rejected with a 409, the same way a fresh booking would be — it does not
silently pick a different time on the caller's behalf, since the brief calls for a
conflict-free re-check, not automatic relocation.

## Virtual clock and the notification twists

Reminders and no-show detection can't rely on real time, since the grading harness needs to
trigger them without waiting for real minutes/hours to pass. `notification_service.py`
maintains a separate, controllable "current time" that only moves when `POST /clock` is
called — none of this logic reads real system time. Every `POST /clock` call triggers two
sweeps: generating reminder notifications (stored in an outbox, readable via `GET /outbox`)
for anything scheduled "today" by the virtual clock, and marking any still-`booked`
appointment as `no_show` once 30+ minutes have passed its start time by the virtual clock.

The outbox is a queue-like table rather than sending anything directly from the booking
logic — it records that a reminder was generated, avoids duplicate reminders for the same
patient on the same day, and is cleared of stale entries once an appointment is completed
or cancelled, so the notification panel doesn't fill up with reminders for appointments
that no longer matter.

I initially tried switching this over to real UTC timestamps because it felt more
production-realistic, but reverted it — the twist spec is explicit that both features are
graded via `/outbox` after `POST /clock`, so the grader needs to be able to fast-forward
time directly, which only the virtual clock supports.

## Testing and fixes

Automated tests under `tests/` cover: two overlapping bookings for the same doctor (second
rejected), cancellations just before vs. well before the 2-hour cutoff (correct fee tier
applied in each case, including the post-start $1 case), a reschedule into a conflicting
slot (rejected, not relocated), and advancing the virtual clock past a booking's start time
by 30+ minutes to confirm it flips to `no_show` while cancelled/completed appointments are
untouched. Along the way I caught and fixed the cross-account data leak, the session-restart
bug, and a detour where I'd swapped the virtual clock for real time and had to revert it
once I re-read the grading requirement closely.

## Trade-offs

Given the time limit, I used simple session-based auth rather than a full permissions
system, and the virtual clock is a manually-triggered mechanism rather than a real
background job scheduler. With more time I'd add doctor availability windows, more edge-case
test coverage, and a more polished UI for the doctor's-day view.