from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import utc_now
from .models import Appointment
from .notification_service import clear_stale_reminders


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def book_appointment(
    db: Session, doctor_id: int, patient_id: int, starts_at: datetime,
    ends_at: datetime, notes: str = "",
) -> Appointment:
    starts_at, ends_at = normalize_utc(starts_at), normalize_utc(ends_at)
    if ends_at <= starts_at:
        raise HTTPException(400, "Appointment end must be after its start")
    if starts_at < utc_now():
        raise HTTPException(400, "Appointments cannot start in the past")

    # SQLite serializes writers after BEGIN IMMEDIATE, making the check-and-insert atomic.
    db.rollback()
    db.execute(text("BEGIN IMMEDIATE"))
    try:
        conflicts = db.query(Appointment).filter(
            Appointment.user_id == db.info["user_id"], Appointment.doctor_id == doctor_id,
            Appointment.status == "booked",
            Appointment.starts_at < ends_at,
            Appointment.ends_at > starts_at,
        ).order_by(Appointment.ends_at).all()
        if conflicts:
            last_end = max(item.ends_at for item in conflicts)
            db.rollback()
            raise HTTPException(409, detail={
                "message": "Doctor is already booked for that time.",
                "last_appointment_ends_at": last_end.isoformat(),
                "suggested_starts_at": last_end.isoformat(),
                "suggested_ends_at": (last_end + (ends_at - starts_at)).isoformat(),
            })
        appointment = Appointment(
            user_id=db.info["user_id"], doctor_id=doctor_id, patient_id=patient_id,
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


def reschedule_appointment(db: Session, appointment: Appointment, starts_at: datetime | None = None, ends_at: datetime | None = None, notes: str | None = None, duration_minutes: int = 30) -> Appointment:
    if appointment.status != "booked":
        raise HTTPException(409, "Only booked appointments can be rescheduled")
    starts_at = normalize_utc(starts_at) if starts_at else utc_now()
    ends_at = normalize_utc(ends_at) if ends_at else starts_at + timedelta(minutes=duration_minutes)
    if ends_at <= starts_at:
        raise HTTPException(400, "Appointment end must be after its start")
    if starts_at < utc_now():
        starts_at = utc_now()
        ends_at = starts_at + timedelta(minutes=duration_minutes)
    db.rollback()
    db.execute(text("BEGIN IMMEDIATE"))
    conflicts = db.query(Appointment).filter(
        Appointment.user_id == db.info["user_id"], Appointment.id != appointment.id,
        Appointment.doctor_id == appointment.doctor_id, Appointment.status == "booked",
    ).order_by(Appointment.starts_at).all()
    while any(starts_at < item.ends_at and ends_at > item.starts_at for item in conflicts):
        next_end = max(item.ends_at for item in conflicts if starts_at < item.ends_at and ends_at > item.starts_at)
        starts_at, ends_at = next_end, next_end + (ends_at - starts_at)
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
    now = utc_now()
    appointment.status = "cancelled"
    if now >= appointment.starts_at:
        appointment.cancellation_fee = Decimal("1.00")
    elif now <= cutoff:
        appointment.cancellation_fee = Decimal("0.00")
    else:
        appointment.cancellation_fee = Decimal("25.00")
    db.commit()
    clear_stale_reminders(db)
    db.refresh(appointment)
    return appointment


def complete_appointment(db: Session, appointment: Appointment) -> Appointment:
    if appointment.status != "booked":
        raise HTTPException(409, "Only booked appointments can be completed")
    appointment.status = "completed"
    db.commit()
    clear_stale_reminders(db)
    db.refresh(appointment)
    return appointment

