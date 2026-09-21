"""Authentication and authorization API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user, require_permissions
from app.auth.jwt import create_access_token
from app.auth.schemas import LoginRequest, TokenResponse, UserResponse
from app.auth.service import authenticate_user
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description="Authenticate with email and password to receive a JWT access token.",
)
async def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Validate user credentials and generate an access token."""
    user = authenticate_user(db, email=payload.email, password=payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=user.id)
    return TokenResponse(access_token=access_token, token_type="bearer")


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current User",
    description="Retrieve account details and assigned permissions for the currently authenticated user.",
)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    """Return the profile and roles of the authenticated user."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        roles=[r.name for r in current_user.roles],
        permissions=sorted(list(current_user.permissions)),
    )


@router.get(
    "/admin-test",
    status_code=status.HTTP_200_OK,
    summary="Admin Authorization Test Endpoint",
    description="Protected endpoint requiring administrative permissions (USER_MANAGE) to verify RBAC enforcement.",
)
async def admin_test(
    current_user: User = Depends(require_permissions("USER_MANAGE")),
) -> dict:
    """Verify admin permission enforcement."""
    return {
        "status": "success",
        "message": "Admin authorization verified",
        "user": current_user.email,
    }
