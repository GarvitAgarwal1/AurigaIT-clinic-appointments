from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.security import hash_password, verify_password
from app.models import ClockState, OutboxNotification
from app.services import advance_clock, book_appointment, cancel_appointment, reschedule_appointment


def future_time(hours=24):
    return datetime.utcnow() + timedelta(hours=hours)


def test_password_hash_is_verifiable_and_not_plaintext():
    encoded = hash_password("correct horse battery staple")
    assert encoded != "correct horse battery staple"
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_adjacent_slots_are_allowed_but_overlapping_slots_are_rejected(db):
    session, doctor, patient = db
    start = future_time()
    first = book_appointment(session, doctor.id, patient.id, start, start + timedelta(minutes=30))
    adjacent = book_appointment(session, doctor.id, patient.id, start + timedelta(minutes=30), start + timedelta(hours=1))
    assert first.id != adjacent.id

    with pytest.raises(HTTPException) as error:
        book_appointment(session, doctor.id, patient.id, start + timedelta(minutes=15), start + timedelta(minutes=45))
    assert error.value.status_code == 409


def test_conflicting_reschedule_keeps_original_slot(db):
    session, doctor, patient = db
    start = future_time()
    first = book_appointment(session, doctor.id, patient.id, start, start + timedelta(hours=1))
    second = book_appointment(session, doctor.id, patient.id, start + timedelta(hours=2), start + timedelta(hours=3))

    with pytest.raises(HTTPException) as error:
        reschedule_appointment(session, second, start + timedelta(minutes=30), start + timedelta(minutes=90))
    assert error.value.status_code == 409
    session.refresh(second)
    assert second.starts_at == start + timedelta(hours=2)
    assert session.get(type(first), first.id) is not None


def test_cancellation_fee_is_free_before_cutoff_and_25_dollars_inside_cutoff(db):
    session, doctor, patient = db
    on_time_start = future_time(hours=3)
    on_time = book_appointment(session, doctor.id, patient.id, on_time_start, on_time_start + timedelta(minutes=30))
    cancel_appointment(session, on_time)
    assert on_time.cancellation_fee == Decimal("0.00")

    late_start = future_time(hours=1)
    late = book_appointment(session, doctor.id, patient.id, late_start, late_start + timedelta(minutes=30))
    cancel_appointment(session, late)
    assert late.cancellation_fee == Decimal("25.00")


def test_clock_generates_one_reminder_and_marks_old_booking_no_show(db):
    session, doctor, patient = db
    previous_day = datetime(2030, 1, 1, 23, 0)
    appointment_start = datetime(2030, 1, 2, 9, 0)
    appointment = book_appointment(session, doctor.id, patient.id, appointment_start, appointment_start + timedelta(minutes=30))
    session.get(ClockState, 1).current_time = previous_day
    session.commit()

    advance_clock(session, datetime(2030, 1, 2, 9, 15))
    assert session.query(OutboxNotification).count() == 1
    assert session.query(OutboxNotification).one().patient_id == patient.id
    assert appointment.status == "booked"

    advance_clock(session, datetime(2030, 1, 2, 9, 31))
    session.refresh(appointment)
    assert appointment.status == "no_show"
    advance_clock(session, datetime(2030, 1, 2, 10, 0))
    assert session.query(OutboxNotification).count() == 1


def test_clock_accepts_iso_timestamp_with_timezone(db):
    session, _, _ = db
    clock = advance_clock(session, datetime(2030, 3, 1, 12, 0, tzinfo=timezone.utc))
    assert clock.current_time == datetime(2030, 3, 1, 12, 0)


def test_cancellation_after_simulated_appointment_time_charges_fee(db):
    session, doctor, patient = db
    start = datetime(2030, 2, 1, 10, 0)
    appointment = book_appointment(session, doctor.id, patient.id, start, start + timedelta(minutes=30))
    session.get(ClockState, 1).current_time = datetime(2030, 2, 1, 10, 31)
    session.commit()
    cancel_appointment(session, appointment)
    assert appointment.cancellation_fee == Decimal("25.00")


def test_landing_and_dashboard_pages_render():
    client = TestClient(app)
    landing = client.get("/")
    dashboard = client.get("/app")
    assert landing.status_code == 200
    assert "API documentation" not in landing.text
    assert dashboard.status_code == 200
    assert dashboard.text.count("data-password-toggle aria-label") == 2
    assert 'id="login-message"' in dashboard.text
    assert 'id="register-message"' in dashboard.text
    assert "/appointments/{appointment_id}/reschedule" not in dashboard.text