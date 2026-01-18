from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import User

# ---- Password hashing ----
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)

# ---- JWT config ----
SECRET_KEY = "CHANGE_ME_SUPER_SECRET"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# ---- Bearer schemes ----
# auto_error=True => si pas de token => FastAPI renvoie direct 403 "Not authenticated"
bearer_required = HTTPBearer(auto_error=True)

# auto_error=False => si pas de token => credentials=None (donc on peut retourner None)
bearer_optional = HTTPBearer(auto_error=False)

# ---- Helpers ----
def _decode_user_from_token(token: str, db: Session) -> User | None:
    """
    Décode le JWT, récupère user_id depuis 'sub', et retourne l'utilisateur si existe.
    Retourne None si token invalide / user absent.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            return None
        user_id = int(sub)
    except (JWTError, ValueError):
        return None

    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()

# ---- Dependencies ----
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_required),
    db: Session = Depends(get_db),
) -> User:
    user = _decode_user_from_token(credentials.credentials, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_optional),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    return _decode_user_from_token(credentials.credentials, db)
