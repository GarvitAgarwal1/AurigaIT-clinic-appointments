from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from .database import utc_now
from .models import Appointment, OutboxNotification, Patient


def clear_stale_reminders(db: Session) -> int:
    removed = 0
    notifications = db.query(OutboxNotification).all()
    for notification in notifications:
        day_start = notification.appointment_date
        day_end = day_start + timedelta(days=1)
        active = db.query(Appointment).filter(
            Appointment.user_id == notification.user_id,
            Appointment.patient_id == notification.patient_id,
            Appointment.starts_at >= day_start,
            Appointment.starts_at < day_end,
            Appointment.status == "booked",
        ).first()
        if not active:
            db.delete(notification)
            removed += 1
    if removed:
        db.commit()
    return removed


def send_today_reminders(db: Session, now: datetime | None = None) -> int:
    """Queue one notification per patient with a booked appointment today.

    The outbox is the notification-service boundary: a production adapter can
    publish these rows to SMS/email, while the assessment can inspect them.
    """
    now = now or utc_now()
    clear_stale_reminders(db)
    day_start = datetime.combine(now.date(), time.min)
    day_end = day_start + timedelta(days=1)
    appointments = db.query(Appointment).filter(
        Appointment.starts_at >= day_start,
        Appointment.starts_at < day_end,
        Appointment.status == "booked",
    ).all()
    created = 0
    for appointment in appointments:
        exists = db.query(OutboxNotification).filter(
            OutboxNotification.user_id == appointment.user_id,
            OutboxNotification.patient_id == appointment.patient_id,
            OutboxNotification.appointment_date == day_start,
        ).first()
        if exists:
            continue
        patient = db.get(Patient, appointment.patient_id)
        db.add(OutboxNotification(
            user_id=appointment.user_id,
            patient_id=appointment.patient_id,
            appointment_date=day_start,
            message=f"Reminder for {patient.name}: your appointment is today at {appointment.starts_at.strftime('%H:%M')}.",
        ))
        created += 1
    if created:
        db.commit()
    return created


def remove_expired_appointments(db: Session, now: datetime | None = None) -> int:
    """Delete booked appointments at least 30 minutes after their start."""
    now = now or utc_now()
    expired = db.query(Appointment).filter(
        Appointment.status == "booked",
        Appointment.starts_at <= now - timedelta(minutes=30),
    ).all()
    for appointment in expired:
        db.delete(appointment)
    if expired:
        db.commit()
    return len(expired)