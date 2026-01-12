from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from datetime import timedelta
import uuid

from app.models.schemas import Token, UserLogin, UserCreate, UserResponse
from app.models.models import User
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limiter import limiter

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/day")
async def register(request_data: UserCreate, db: Session = Depends(get_db), request=None):
    """Register a new user - Security Disabled"""
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == request_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # Create new user (password stored as plain text - NO SECURITY)
        user = User(
            id=uuid.uuid4(),
            email=request_data.email,
            password_hash=request_data.password,  # Storing plain text
            full_name=request_data.full_name,
            company=request_data.company or "BCom Offshore SAL"
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            company=user.company
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/login", response_model=Token)
@limiter.limit("20/hour")
async def login(credentials: UserLogin, db: Session = Depends(get_db), request=None):
    """Login user - Security Disabled"""
    try:
        # Find user by email
        user = db.query(User).filter(User.email == credentials.email).first()

        if not user or user.password_hash != credentials.password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Return a dummy token (no JWT, just a simple token)
        return Token(access_token=f"token_{user.id}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )


@router.get("/me", response_model=UserResponse)
@limiter.limit("100/minute")
async def get_current_user_info(request=None):
    """Get current user information - Security Disabled"""
    # Without authentication, return a default response or require user_id in query params
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="This endpoint requires user_id query parameter (security disabled)"
    )


