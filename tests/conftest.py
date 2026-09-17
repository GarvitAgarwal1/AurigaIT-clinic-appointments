import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Doctor, Patient, User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(username="test-owner", password_hash="test")
        session.add(user)
        session.flush()
        session.info["user_id"] = user.id
        doctor = Doctor(user_id=user.id, name="Dr. Test", specialty="Testing")
        patient = Patient(user_id=user.id, name="Test Patient", phone="555-0000", email="test@example.com")
        session.add_all([doctor, patient])
        session.commit()
        yield session, doctor, patient