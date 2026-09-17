from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from .database import get_db
from .dependencies import current_user
from .models import Appointment, Doctor, Patient, User
from .schemas import AppointmentIn, AppointmentOut, AppointmentUpdate, ClockIn, DoctorIn, PatientIn, RescheduleIn
from .notification_service import remove_expired_appointments, send_today_reminders
from .services import book_appointment, cancel_appointment, complete_appointment, reschedule_appointment
from .models import ClockState, OutboxNotification

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])


def page(query, page: int, size: int):
    return query.offset((page - 1) * size).limit(size).all()


@router.get("/doctors")
def doctors(page_number: int = Query(1, alias="page", ge=1), page_size: int = Query(20, alias="size", ge=1, le=100), sort: str = "name", db: Session = Depends(get_db)):
    allowed = {"name": Doctor.name, "specialty": Doctor.specialty}
    items = page(db.query(Doctor).filter(Doctor.user_id == db.info["user_id"]).order_by(asc(allowed.get(sort, Doctor.name))), page_number, page_size)
    return {"items": [{"id": d.id, "name": d.name, "specialty": d.specialty} for d in items], "page": page_number, "size": page_size}


@router.post("/doctors", status_code=201)
def create_doctor(data: DoctorIn, db: Session = Depends(get_db)):
    doctor = Doctor(user_id=db.info["user_id"], **data.model_dump()); db.add(doctor); db.commit(); db.refresh(doctor)
    return doctor


@router.get("/doctors/{doctor_id}")
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id, Doctor.user_id == db.info["user_id"]).first()
    if not doctor: raise HTTPException(404, "Doctor not found")
    return doctor


@router.put("/doctors/{doctor_id}")
def update_doctor(doctor_id: int, data: DoctorIn, db: Session = Depends(get_db)):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id, Doctor.user_id == db.info["user_id"]).first()
    if not doctor: raise HTTPException(404, "Doctor not found")
    doctor.name, doctor.specialty = data.name, data.specialty; db.commit(); return doctor


@router.delete("/doctors/{doctor_id}", status_code=204)
def delete_doctor(doctor_id: int, db: Session = Depends(get_db)):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id, Doctor.user_id == db.info["user_id"]).first()
    if not doctor: raise HTTPException(404, "Doctor not found")
    if db.query(Appointment).filter(Appointment.user_id == db.info["user_id"], Appointment.doctor_id == doctor_id).first(): raise HTTPException(409, "Doctor has appointments")
    db.delete(doctor); db.commit()


@router.get("/patients")
def patients(search: str = "", page_number: int = Query(1, alias="page", ge=1), page_size: int = Query(20, alias="size", ge=1, le=100), sort: str = "name", db: Session = Depends(get_db)):
    query = db.query(Patient).filter(Patient.user_id == db.info["user_id"])
    if search: query = query.filter(Patient.name.ilike(f"%{search}%"))
    items = page(query.order_by(asc(Patient.name if sort == "name" else Patient.id)), page_number, page_size)
    return {"items": [{
        "id": p.id, "name": p.name, "phone": p.phone, "email": p.email,
        "cancellation_amount": sum((a.cancellation_fee or 0) for a in p.appointments),
        "cancelled_amount": sum((a.cancellation_fee or 0) for a in p.appointments if a.status == "cancelled"),
    } for p in items], "page": page_number, "size": page_size}


@router.post("/patients", status_code=201)
def create_patient(data: PatientIn, db: Session = Depends(get_db)):
    patient = Patient(user_id=db.info["user_id"], **data.model_dump()); db.add(patient); db.commit(); db.refresh(patient); return patient


@router.get("/patients/{patient_id}")
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.user_id == db.info["user_id"]).first()
    if not patient: raise HTTPException(404, "Patient not found")
    return patient


@router.put("/patients/{patient_id}")
def update_patient(patient_id: int, data: PatientIn, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.user_id == db.info["user_id"]).first()
    if not patient: raise HTTPException(404, "Patient not found")
    for key, value in data.model_dump().items(): setattr(patient, key, value)
    db.commit(); return patient


@router.delete("/patients/{patient_id}", status_code=204)
def delete_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.user_id == db.info["user_id"]).first()
    if not patient: raise HTTPException(404, "Patient not found")
    if db.query(Appointment).filter(Appointment.user_id == db.info["user_id"], Appointment.patient_id == patient_id).first(): raise HTTPException(409, "Patient has appointments")
    db.delete(patient); db.commit()


@router.get("/appointments", response_model=list[AppointmentOut])
def appointments(page_number: int = Query(1, alias="page", ge=1), page_size: int = Query(20, alias="size", ge=1, le=100), sort: str = "starts_at", patient_name: str = "", doctor_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Appointment).join(Patient).filter(Appointment.user_id == db.info["user_id"], Patient.user_id == db.info["user_id"])
    if patient_name: query = query.filter(Patient.name.ilike(f"%{patient_name}%"))
    if doctor_id: query = query.filter(Appointment.doctor_id == doctor_id)
    order_column = Appointment.starts_at if sort == "starts_at" else Appointment.id
    return page(query.order_by(desc(order_column)), page_number, page_size)


@router.get("/appointments/day/{doctor_id}", response_model=list[AppointmentOut])
def doctor_day(doctor_id: int, day: date, page_number: int = Query(1, alias="page", ge=1), page_size: int = Query(100, alias="size", ge=1, le=200), db: Session = Depends(get_db)):
    start, end = datetime.combine(day, time.min), datetime.combine(day, time.max)
    query = db.query(Appointment).filter(Appointment.user_id == db.info["user_id"], Appointment.doctor_id == doctor_id, Appointment.starts_at >= start, Appointment.starts_at <= end).order_by(asc(Appointment.starts_at))
    return page(query, page_number, page_size)


@router.post("/appointments", response_model=AppointmentOut, status_code=201)
def create_appointment(data: AppointmentIn, db: Session = Depends(get_db)):
    if not db.query(Doctor).filter(Doctor.id == data.doctor_id, Doctor.user_id == db.info["user_id"]).first() or not db.query(Patient).filter(Patient.id == data.patient_id, Patient.user_id == db.info["user_id"]).first(): raise HTTPException(404, "Doctor or patient not found")
    return book_appointment(db, **data.model_dump())


@router.get("/appointments/{appointment_id}", response_model=AppointmentOut)
def get_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id, Appointment.user_id == db.info["user_id"]).first()
    if not appointment: raise HTTPException(404, "Appointment not found")
    return appointment


@router.patch("/appointments/{appointment_id}", response_model=AppointmentOut)
def update_appointment(appointment_id: int, data: AppointmentUpdate, db: Session = Depends(get_db)):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id, Appointment.user_id == db.info["user_id"]).first()
    if not appointment: raise HTTPException(404, "Appointment not found")
    values = data.model_dump(exclude_unset=True)
    starts, ends = values.get("starts_at", appointment.starts_at), values.get("ends_at", appointment.ends_at)
    if starts != appointment.starts_at or ends != appointment.ends_at:
        return reschedule_appointment(db, appointment, starts, ends, values.get("notes"))
    for key, value in values.items(): setattr(appointment, key, value)
    db.commit(); db.refresh(appointment); return appointment


@router.patch("/appointments/{appointment_id}/reschedule", response_model=AppointmentOut)
def reschedule(appointment_id: int, data: RescheduleIn, db: Session = Depends(get_db)):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id, Appointment.user_id == db.info["user_id"]).first()
    if not appointment: raise HTTPException(404, "Appointment not found")
    return reschedule_appointment(db, appointment, data.starts_at, data.ends_at, duration_minutes=data.duration_minutes)


@router.post("/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel(appointment_id: int, db: Session = Depends(get_db)):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id, Appointment.user_id == db.info["user_id"]).first()
    if not appointment: raise HTTPException(404, "Appointment not found")
    return cancel_appointment(db, appointment)


@router.post("/appointments/{appointment_id}/complete", response_model=AppointmentOut)
def complete(appointment_id: int, db: Session = Depends(get_db)):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id, Appointment.user_id == db.info["user_id"]).first()
    if not appointment: raise HTTPException(404, "Appointment not found")
    return complete_appointment(db, appointment)


@router.delete("/appointments/{appointment_id}", status_code=204)
def delete_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id, Appointment.user_id == db.info["user_id"]).first()
    if not appointment: raise HTTPException(404, "Appointment not found")
    db.delete(appointment); db.commit()


@router.post("/notifications/run")
def run_notifications(db: Session = Depends(get_db)):
    return {"created": send_today_reminders(db)}


@router.post("/appointments/cleanup")
def cleanup_appointments(db: Session = Depends(get_db)):
    return {"removed": remove_expired_appointments(db)}


@router.get("/outbox")
def outbox(db: Session = Depends(get_db)):
    notifications = db.query(OutboxNotification).filter(OutboxNotification.user_id == db.info["user_id"]).order_by(OutboxNotification.id).all()
    return [{
        "id": item.id,
        "patient_id": item.patient_id,
        "appointment_date": item.appointment_date,
        "message": item.message,
        "created_at": item.created_at,
    } for item in notifications]