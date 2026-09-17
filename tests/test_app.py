from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import Appointment, Doctor, OutboxNotification, Patient, User
from app.security import hash_password, verify_password
from app.notification_service import clear_stale_reminders, remove_expired_appointments, send_today_reminders
from app.services import book_appointment, cancel_appointment, complete_appointment, reschedule_appointment


def future_time(hours=24):
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=hours)


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


def test_conflicting_reschedule_moves_to_next_free_slot(db):
    session, doctor, patient = db
    start = future_time()
    first = book_appointment(session, doctor.id, patient.id, start, start + timedelta(hours=1))
    second = book_appointment(session, doctor.id, patient.id, start + timedelta(hours=2), start + timedelta(hours=3))

    updated = reschedule_appointment(session, second, start + timedelta(minutes=30), start + timedelta(minutes=90))
    assert updated.starts_at == start + timedelta(hours=1)
    assert updated.ends_at == start + timedelta(hours=2)
    assert session.get(type(first), first.id) is not None


def test_cancelled_appointment_cannot_be_rescheduled(db):
    session, doctor, patient = db
    start = future_time()
    appointment = book_appointment(session, doctor.id, patient.id, start, start + timedelta(minutes=30))
    cancel_appointment(session, appointment)
    with pytest.raises(HTTPException) as error:
        reschedule_appointment(session, appointment, start + timedelta(hours=1), start + timedelta(hours=2))
    assert error.value.status_code == 409


def test_completed_appointment_is_not_removed(db):
    session, doctor, patient = db
    start = datetime(2030, 4, 1, 10, 0)
    appointment = book_appointment(session, doctor.id, patient.id, start, start + timedelta(minutes=30))
    complete_appointment(session, appointment)
    remove_expired_appointments(session, datetime(2030, 4, 1, 11, 1))
    session.expire(appointment)
    assert appointment.status == "completed"


def test_sqlite_foreign_keys_are_enforced(db):
    session, _, _ = db
    with pytest.raises(Exception):
        session.add(Appointment(doctor_id=99999, patient_id=99999, starts_at=future_time(), ends_at=future_time(hours=2)))
        session.commit()
    session.rollback()


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


def test_today_reminder_is_created_once(db):
    session, doctor, patient = db
    appointment_start = datetime(2030, 1, 2, 9, 0)
    appointment = book_appointment(session, doctor.id, patient.id, appointment_start, appointment_start + timedelta(minutes=30))
    assert send_today_reminders(session, appointment_start - timedelta(hours=1)) == 1
    assert session.query(OutboxNotification).one().patient_id == patient.id
    assert appointment.status == "booked"
    assert send_today_reminders(session, appointment_start) == 0
    assert session.query(OutboxNotification).count() == 1
    complete_appointment(session, appointment)
    assert clear_stale_reminders(session) == 0
    assert session.query(OutboxNotification).count() == 0


def test_cancellation_after_simulated_appointment_time_charges_fee(db):
    session, doctor, patient = db
    start = future_time(hours=1)
    appointment = book_appointment(session, doctor.id, patient.id, start, start + timedelta(minutes=30))
    cancel_appointment(session, appointment)
    assert appointment.cancellation_fee == Decimal("25.00")


def test_cancellation_after_start_charges_one_dollar(db):
    session, doctor, patient = db
    start = future_time(hours=1)
    appointment = book_appointment(session, doctor.id, patient.id, start, start + timedelta(minutes=30))
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("app.services.utc_now", lambda: start + timedelta(minutes=1))
        cancel_appointment(session, appointment)
    assert appointment.cancellation_fee == Decimal("1.00")


def test_cancelled_amount_is_stored_on_patient(db):
    session, doctor, patient = db
    start = future_time(hours=1)
    appointment = book_appointment(session, doctor.id, patient.id, start, start + timedelta(minutes=30))
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("app.services.utc_now", lambda: start + timedelta(minutes=1))
        cancel_appointment(session, appointment)
    session.refresh(patient)
    assert sum(a.cancellation_fee for a in patient.appointments if a.status == "cancelled") == Decimal("1.00")


def test_booked_appointment_is_removed_after_30_minutes(db):
    session, doctor, patient = db
    start = datetime(2030, 2, 1, 10, 0)
    appointment = book_appointment(session, doctor.id, patient.id, start, start + timedelta(minutes=30))
    assert remove_expired_appointments(session, datetime(2030, 2, 1, 10, 29)) == 0
    assert remove_expired_appointments(session, datetime(2030, 2, 1, 10, 30)) == 1
    assert session.get(Appointment, appointment.id) is None


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
    assert 'id="notifications"' in dashboard.text
    assert "Today's patient reminders" in dashboard.text
    assert "Cancellation fee:" in dashboard.text
    assert "Next free time" not in dashboard.text
    assert "Remember me on this device for 30 days" in dashboard.text
    assert "/appointments/{appointment_id}/reschedule" not in dashboard.text


def test_conflict_returns_last_end_time_for_reschedule_action(db):
    session, doctor, patient = db
    start = future_time()
    book_appointment(session, doctor.id, patient.id, start, start + timedelta(hours=1))
    with pytest.raises(HTTPException) as error:
        book_appointment(session, doctor.id, patient.id, start + timedelta(minutes=30), start + timedelta(hours=1, minutes=30))
    assert error.value.status_code == 409
    assert error.value.detail["last_appointment_ends_at"] == (start + timedelta(hours=1)).isoformat()


def test_accounts_cannot_see_each_others_records():
    first = TestClient(app)
    second = TestClient(app)
    suffix = uuid4().hex[:8]
    first_name, second_name = f"scope-test-a-{suffix}", f"scope-test-b-{suffix}"
    for client, username in ((first, first_name), (second, second_name)):
        response = client.post("/api/auth/register", json={"username": username, "password": "password123"})
        assert response.status_code in (201, 409)
        assert client.post("/api/auth/login", json={"username": username, "password": "password123"}).status_code == 200
    try:
        assert len(first.get("/api/doctors").json()["items"]) == 4
        assert len(first.get("/api/patients").json()["items"]) == 6
        assert len(second.get("/api/doctors").json()["items"]) == 4
        assert len(second.get("/api/patients").json()["items"]) == 6
        first_doctor = first.post("/api/doctors", json={"name": "Private Doctor", "specialty": "Private"}).json()
        assert second.get(f"/api/doctors/{first_doctor['id']}").status_code == 404
    finally:
        with SessionLocal() as db:
            user_ids = [user.id for user in db.query(User).filter(User.username.in_([first_name, second_name])).all()]
            db.query(OutboxNotification).filter(OutboxNotification.user_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(Appointment).filter(Appointment.user_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(Doctor).filter(Doctor.user_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(Patient).filter(Patient.user_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
            db.commit()


def test_outbox_requires_login_and_returns_only_notification_fields():
    client = TestClient(app)
    assert client.get("/outbox").status_code == 401