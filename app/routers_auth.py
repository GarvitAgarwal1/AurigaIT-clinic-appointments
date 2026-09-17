import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .seed import seed_demo_data
from .schemas import UserIn
from .security import hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register(data: UserIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(409, "Username is already registered")
    user = User(username=data.username, password_hash=hash_password(data.password))
    db.add(user); db.commit(); db.refresh(user)
    seed_demo_data(db, user)
    return {"id": user.id, "username": user.username}


@router.post("/login")
def login(data: UserIn, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid username or password")
    request.session["user_id"] = user.id
    user.remember_token = secrets.token_urlsafe(48) if data.remember_me else None
    db.commit()
    if user.remember_token:
        response.set_cookie("clinic_remember", user.remember_token, max_age=60 * 60 * 24 * 30, httponly=True, samesite="lax")
    else:
        response.delete_cookie("clinic_remember")
    seed_demo_data(db, user)
    return {"message": "Logged in", "username": user.username}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if user_id:
        user = db.get(User, user_id)
        if user:
            user.remember_token = None
            db.commit()
    request.session.clear()
    response.delete_cookie("clinic_remember")
    return {"message": "Logged out"}