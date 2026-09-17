import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Doctor, Patient


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        doctor = Doctor(name="Dr. Test", specialty="Testing")
        patient = Patient(name="Test Patient", phone="555-0000", email="test@example.com")
        session.add_all([doctor, patient])
        session.commit()
        yield session, doctor, patient