from sqlalchemy.orm import Session

from .models import Doctor, Patient


def seed_demo_data(db: Session) -> None:
    if db.query(Doctor).count() == 0:
        db.add_all([
            Doctor(name="Dr. Maya Patel", specialty="Family medicine"),
            Doctor(name="Dr. James Wilson", specialty="Cardiology"),
            Doctor(name="Dr. Sofia Nguyen", specialty="Dermatology"),
            Doctor(name="Dr. Daniel Brooks", specialty="Pediatrics"),
        ])
    if db.query(Patient).count() == 0:
        db.add_all([
            Patient(name="Ava Thompson", phone="555-0101", email="ava.thompson@example.com"),
            Patient(name="Liam Carter", phone="555-0102", email="liam.carter@example.com"),
            Patient(name="Mia Rodriguez", phone="555-0103", email="mia.rodriguez@example.com"),
            Patient(name="Noah Williams", phone="555-0104", email="noah.williams@example.com"),
        ])
    db.commit()