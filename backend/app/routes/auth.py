from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException , status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import Token, RefreshTokenRequest, UserCreate, UserResponse
from app.services.user import register_user
from app.services.auth import login_user, refresh_access_token
from .dependencies import get_current_user
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

@router.post("/login", response_model=Token)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                db: Annotated[Session, Depends(get_db)]) -> Token | HTTPException:
    """ 
    Authenticate a user and return access and refresh tokens.
    
    raises HTTPException with status code 400 if authentication fails.
    and returns a Token object containing the access and refresh tokens.
    """
    try:
        return login_user(db, form_data.username, form_data.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    

@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token_request: RefreshTokenRequest,
                        db: Annotated[Session, Depends(get_db)]) -> Token | HTTPException:
    """
    Refresh the access token using a valid refresh token.
    
    Raises an HTTPException with status code 400 if the refresh token is invalid or expired.
    Returns a Token object containing the new access token.
    """
    try:
        return refresh_access_token(db, refresh_token_request.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register( 
                user_create: UserCreate,
                db: Annotated[Session, Depends(get_db)]) -> UserResponse | HTTPException:
    """
    Register (sign up) a new user with the given email and password.
    
    Raises an HTTPException with status code 400 if the email is already registered.
    Returns a UserResponse object of the newly created user.
    """
    try:
        return register_user(db, user_create)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))



# test route to verify token
@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)