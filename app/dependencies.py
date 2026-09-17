from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .database import get_db
from .models import User


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    user = db.get(User, user_id) if user_id else None
    if not user:
        token = request.cookies.get("clinic_remember")
        user = db.query(User).filter(User.remember_token == token, User.is_active.is_(True)).first() if token else None
        if user:
            request.session["user_id"] = user.id
    if not user or not user.is_active:
        raise HTTPException(401, "Login required")
    db.info["user_id"] = user.id
    return user