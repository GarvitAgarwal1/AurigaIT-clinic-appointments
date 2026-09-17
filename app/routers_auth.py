from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .schemas import UserIn
from .security import hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register(data: UserIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(409, "Username is already registered")
    user = User(username=data.username, password_hash=hash_password(data.password))
    db.add(user); db.commit()
    return {"id": user.id, "username": user.username}


@router.post("/login")
def login(data: UserIn, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid username or password")
    request.session["user_id"] = user.id
    return {"message": "Logged in", "username": user.username}


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"message": "Logged out"}