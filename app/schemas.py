from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=128)


class DoctorIn(BaseModel):
    name: str
    specialty: str = "General practice"


class PatientIn(BaseModel):
    name: str
    phone: str = ""
    email: str = ""


class AppointmentIn(BaseModel):
    doctor_id: int
    patient_id: int
    starts_at: datetime
    ends_at: datetime
    notes: str = ""


class AppointmentUpdate(BaseModel):
    notes: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class RescheduleIn(BaseModel):
    starts_at: datetime
    ends_at: datetime


class ClockIn(BaseModel):
    current_time: datetime


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    doctor_id: int
    patient_id: int
    starts_at: datetime
    ends_at: datetime
    status: str
    cancellation_fee: Decimal
    notes: str