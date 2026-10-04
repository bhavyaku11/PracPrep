"""Authentication Route Dependencies.

Provides FastAPI dependencies for extracting, validating, and resolving
authenticated users from Bearer tokens via OAuth2PasswordBearer.
"""

from typing import Annotated
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clerk import ClerkConfigurationError, ClerkTokenError, get_clerk_verifier
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import TokenError, decode_access_token
from app.modules.auth.models import User
from sqlalchemy import or_


settings = get_settings()

# OAuth2 Password Bearer scheme configured for the login endpoint
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    description="Bearer token authentication for PracPrep API endpoints",
)


def get_credentials_exception() -> HTTPException:
    """Return a standard HTTP 401 Unauthorized exception with Bearer challenge."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Validate Bearer token (native PracPrep JWT or Clerk JWT) and resolve the User.

    Args:
        token: Bearer JWT access token extracted from Authorization header.
        db: Asynchronous SQLAlchemy database session.

    Returns:
        The authenticated User ORM model instance.

    Raises:
        HTTPException(401): If token is invalid, expired, or user not found.
    """
    credentials_exception = get_credentials_exception()

    # 1. First attempt to decode as native PracPrep access token
    try:
        payload = decode_access_token(token)
        is_native_token = True
    except TokenError:
        is_native_token = False
        payload = {}

    if is_native_token:
        subject: str | None = payload.get("sub")
        if subject:
            try:
                user_id = uuid.UUID(str(subject))
            except (ValueError, TypeError):
                raise credentials_exception
            stmt = select(User).where(User.id == user_id)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            if user is not None:
                return user
        raise credentials_exception

    # 2. Second attempt: Validate as Clerk session token
    try:
        verifier = get_clerk_verifier()
        clerk_payload = verifier.verify_token(token)
        is_clerk_token = True
    except (ClerkTokenError, ClerkConfigurationError):
        is_clerk_token = False
        clerk_payload = {}

    if is_clerk_token:
        clerk_sub = clerk_payload.get("sub")
        clerk_email = clerk_payload.get("email")

        filters = []
        if clerk_sub:
            filters.append(User.auth_provider == f"clerk:{clerk_sub}")
        if clerk_email:
            filters.append(User.email == clerk_email)

        if filters:
            stmt = select(User).where(or_(*filters))
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            if user is not None:
                return user
        raise credentials_exception

    raise credentials_exception


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Verify that the authenticated user account is active.

    Args:
        current_user: The authenticated User resolved by get_current_user.

    Returns:
        The active User instance.

    Raises:
        HTTPException(403): If the user's account is inactive.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return current_user
