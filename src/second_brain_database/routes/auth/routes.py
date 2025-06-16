from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import bcrypt
import jwt
import logging
from datetime import datetime, timedelta

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.routes.auth.models import UserIn, UserOut, Token

logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
router = APIRouter(prefix="/auth", tags=["auth"])

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

@router.post("/register", response_model=UserOut)
async def register(user: UserIn):
    """Register a new user"""
    try:
        # Check if user already exists
        existing_user = await db_manager.get_collection("users").find_one({"username": user.username})
        if existing_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
        
        # Hash password and create user
        hashed_pw = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode()
        await db_manager.get_collection("users").insert_one({
            "username": user.username, 
            "hashed_password": hashed_pw
        })
        return UserOut(username=user.username)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Registration failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Registration failed")

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate user and return JWT token"""
    try:
        user = await db_manager.get_collection("users").find_one({"username": form_data.username})
        if not user or not bcrypt.checkpw(form_data.password.encode(), user["hashed_password"].encode()):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        
        access_token = create_access_token({"sub": user["username"]})
        return Token(access_token=access_token, token_type="bearer")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Login failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed")

@router.get("/me", response_model=UserOut)
async def read_users_me(token: str = Depends(oauth2_scheme)):
    """Get current authenticated user"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return UserOut(username=username)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")