from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .database import Base, engine
from .routers_auth import router as auth_router
from .routers_resources import router as resource_router
from .database import SessionLocal
from .database import get_db
from .dependencies import current_user
from .models import ClockState
from .schemas import ClockIn
from .services import advance_clock
from .models import OutboxNotification
from fastapi import Depends
from .seed import seed_demo_data

Base.metadata.create_all(bind=engine)
with SessionLocal() as db:
    seed_demo_data(db)
    if not db.get(ClockState, 1):
        db.add(ClockState(id=1, current_time=datetime.utcnow()))
        db.commit()
app = FastAPI(title="Clinic Desk")
app.add_middleware(SessionMiddleware, secret_key="change-this-in-production")
app.include_router(auth_router)
app.include_router(resource_router)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse(request=request, name="landing.html")


@app.get("/app", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")


@app.post("/clock", dependencies=[Depends(current_user)])
def set_clock_root(data: ClockIn, db=Depends(get_db)):
    clock = advance_clock(db, data.current_time)
    return {"current_time": clock.current_time, "message": "Clock advanced; reminders generated and no-shows swept"}


@app.get("/outbox", dependencies=[Depends(current_user)])
def outbox_root(db=Depends(get_db)):
    return db.query(OutboxNotification).order_by(OutboxNotification.id).all()