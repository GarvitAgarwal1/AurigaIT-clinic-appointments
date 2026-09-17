from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from .models import Appointment, ClockState, OutboxNotification, Patient


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def get_current_time(db: Session) -> datetime:
    clock = db.get(ClockState, 1)
    if not clock:
        clock = ClockState(id=1, current_time=datetime.utcnow())
        db.add(clock)
        db.commit()
    return clock.current_time


def book_appointment(
    db: Session, doctor_id: int, patient_id: int, starts_at: datetime,
    ends_at: datetime, notes: str = "",
) -> Appointment:
    starts_at, ends_at = normalize_utc(starts_at), normalize_utc(ends_at)
    if ends_at <= starts_at:
        raise HTTPException(400, "Appointment end must be after its start")
    if starts_at < get_current_time(db):
        raise HTTPException(400, "Appointments cannot start in the past")

    # SQLite serializes writers after BEGIN IMMEDIATE, making the check-and-insert atomic.
    db.rollback()
    db.execute(text("BEGIN IMMEDIATE"))
    try:
        conflict = db.query(Appointment).filter(
            Appointment.doctor_id == doctor_id,
            Appointment.status == "booked",
            Appointment.starts_at < ends_at,
            Appointment.ends_at > starts_at,
        ).first()
        if conflict:
            db.rollback()
            raise HTTPException(409, "Doctor already has an appointment in that time range")
        appointment = Appointment(
            doctor_id=doctor_id, patient_id=patient_id,
            starts_at=starts_at, ends_at=ends_at, notes=notes,
        )
        db.add(appointment)
        db.commit()
        db.refresh(appointment)
        return appointment
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise


def reschedule_appointment(db: Session, appointment: Appointment, starts_at: datetime, ends_at: datetime, notes: str | None = None) -> Appointment:
    starts_at, ends_at = normalize_utc(starts_at), normalize_utc(ends_at)
    if ends_at <= starts_at:
        raise HTTPException(400, "Appointment end must be after its start")
    if starts_at < get_current_time(db):
        raise HTTPException(400, "Appointments cannot start in the past")
    db.rollback()
    db.execute(text("BEGIN IMMEDIATE"))
    conflict = db.query(Appointment).filter(
        Appointment.id != appointment.id,
        Appointment.doctor_id == appointment.doctor_id,
        Appointment.status == "booked",
        Appointment.starts_at < ends_at,
        Appointment.ends_at > starts_at,
    ).first()
    if conflict:
        db.rollback()
        raise HTTPException(409, "Doctor already has an appointment in that time range")
    appointment.starts_at, appointment.ends_at = starts_at, ends_at
    if notes is not None:
        appointment.notes = notes
    db.commit()
    db.refresh(appointment)
    return appointment


def cancel_appointment(db: Session, appointment: Appointment) -> Appointment:
    if appointment.status == "cancelled":
        return appointment
    cutoff = appointment.starts_at - timedelta(hours=2)
    appointment.status = "cancelled"
    appointment.cancellation_fee = Decimal("0.00") if get_current_time(db) <= cutoff else Decimal("25.00")
    db.commit()
    db.refresh(appointment)
    return appointment


def advance_clock(db: Session, new_time: datetime) -> ClockState:
    new_time = normalize_utc(new_time)
    clock = db.get(ClockState, 1)
    if not clock:
        clock = ClockState(id=1, current_time=new_time)
        db.add(clock)
        previous_time = None
    else:
        previous_time = clock.current_time
        if new_time < previous_time:
            raise HTTPException(400, "Simulated clock cannot move backwards")
        clock.current_time = new_time

    if previous_time is not None and new_time.date() > previous_time.date():
        crossed_date = previous_time.date() + timedelta(days=1)
        while crossed_date <= new_time.date():
            day_start = datetime.combine(crossed_date, datetime.min.time())
            day_end = day_start + timedelta(days=1)
            appointments = db.query(Appointment).filter(
                Appointment.starts_at >= day_start,
                Appointment.starts_at < day_end,
                Appointment.status.in_(["booked", "no_show"]),
            ).all()
            for appointment in appointments:
                exists = db.query(OutboxNotification).filter(
                    OutboxNotification.patient_id == appointment.patient_id,
                    OutboxNotification.appointment_date == day_start,
                ).first()
                if not exists:
                    patient = db.get(Patient, appointment.patient_id)
                    db.add(OutboxNotification(
                        patient_id=appointment.patient_id,
                        appointment_date=day_start,
                        message=f"Reminder for {patient.name}: appointment on {crossed_date.isoformat()} at {appointment.starts_at.strftime('%H:%M')}",
                    ))
            crossed_date += timedelta(days=1)

    sweep_time = new_time
    for appointment in db.query(Appointment).filter(Appointment.status == "booked").all():
        if sweep_time >= appointment.starts_at + timedelta(minutes=30):
            appointment.status = "no_show"
    db.commit()
    db.refresh(clock)
    return clock