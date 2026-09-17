import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from starlette.middleware.sessions import SessionMiddleware

from .database import Base, engine, migrate_ownership_schema
from .routers_auth import router as auth_router
from .routers_resources import router as resource_router
from .database import SessionLocal, get_db
from .dependencies import current_user
from .models import Appointment, OutboxNotification
from .models import User
from .schemas import AppointmentOut, RescheduleIn
from .services import reschedule_appointment
from .notification_service import remove_expired_appointments, send_today_reminders
from .seed import seed_demo_data

Base.metadata.create_all(bind=engine)
migrate_ownership_schema()
with SessionLocal() as db:
    for user in db.query(User).all():
        seed_demo_data(db, user)
app = FastAPI(title="Clinic Desk")
app.add_middleware(SessionMiddleware, secret_key=secrets.token_urlsafe(32))
app.include_router(auth_router)
app.include_router(resource_router)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
scheduler = BackgroundScheduler(timezone="UTC")


def run_appointment_jobs():
    with SessionLocal() as db:
        send_today_reminders(db)
        remove_expired_appointments(db)


@app.on_event("startup")
def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(run_appointment_jobs, "interval", minutes=1, id="appointment-jobs", replace_existing=True)
        scheduler.start()


@app.on_event("shutdown")
def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse(request=request, name="landing.html")


@app.get("/app", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")


@app.get("/outbox", dependencies=[Depends(current_user)])
def outbox_root(db=Depends(get_db)):
    notifications = db.query(OutboxNotification).filter(OutboxNotification.user_id == db.info["user_id"]).order_by(OutboxNotification.id).all()
    return [{
        "id": item.id,
        "patient_id": item.patient_id,
        "appointment_date": item.appointment_date,
        "message": item.message,
        "created_at": item.created_at,
    } for item in notifications]


@app.patch("/appointments/{appointment_id}/reschedule", response_model=AppointmentOut, dependencies=[Depends(current_user)])
def reschedule_root(appointment_id: int, data: RescheduleIn, db=Depends(get_db)):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id, Appointment.user_id == db.info["user_id"]).first()
    if not appointment:
        raise HTTPException(404, "Appointment not found")
    return reschedule_appointment(db, appointment, data.starts_at, data.ends_at, duration_minutes=data.duration_minutes)