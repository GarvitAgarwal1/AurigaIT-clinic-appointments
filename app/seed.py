from sqlalchemy.orm import Session
from sqlalchemy import func

from .models import Appointment, Doctor, Patient, User


def seed_demo_data(db: Session, user: User) -> None:
    if user.demo_seeded:
        _remove_duplicate_demo_rows(db, user)
        return
    db.add_all([
        Doctor(user_id=user.id, name="Dr. Maya Patel", specialty="Family medicine"),
        Doctor(user_id=user.id, name="Dr. James Wilson", specialty="Cardiology"),
        Doctor(user_id=user.id, name="Dr. Sofia Nguyen", specialty="Dermatology"),
        Doctor(user_id=user.id, name="Dr. Daniel Brooks", specialty="Pediatrics"),
        Patient(user_id=user.id, name="Ava Thompson", phone="555-0101", email="ava.thompson@example.com"),
        Patient(user_id=user.id, name="Liam Carter", phone="555-0102", email="liam.carter@example.com"),
        Patient(user_id=user.id, name="Mia Rodriguez", phone="555-0103", email="mia.rodriguez@example.com"),
        Patient(user_id=user.id, name="Noah Williams", phone="555-0104", email="noah.williams@example.com"),
        Patient(user_id=user.id, name="Emma Johnson", phone="555-0105", email="emma.johnson@example.com"),
        Patient(user_id=user.id, name="Oliver Smith", phone="555-0106", email="oliver.smith@example.com"),
    ])
    user.demo_seeded = True
    db.commit()


def _remove_duplicate_demo_rows(db: Session, user: User) -> None:
    demo_doctors = {"Dr. Maya Patel", "Dr. James Wilson", "Dr. Sofia Nguyen", "Dr. Daniel Brooks"}
    demo_patients = {"Ava Thompson", "Liam Carter", "Mia Rodriguez", "Noah Williams", "Emma Johnson", "Oliver Smith"}
    for model, names in ((Doctor, demo_doctors), (Patient, demo_patients)):
        duplicates = db.query(model.name, func.count(model.id)).filter(
            model.user_id == user.id, model.name.in_(names)
        ).group_by(model.name).having(func.count(model.id) > 1).all()
        for name, _ in duplicates:
            rows = db.query(model).filter(model.user_id == user.id, model.name == name).order_by(model.id).all()
            for row in rows[1:]:
                if model is Doctor:
                    used = db.query(Appointment).filter_by(doctor_id=row.id).first()
                else:
                    used = db.query(Appointment).filter_by(patient_id=row.id).first()
                if not used:
                    db.delete(row)
    db.commit()