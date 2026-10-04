"""Authentication API Router.

Provides registration, login, token refresh, and logout endpoints with Argon2id
password hashing, atomic UserSettings provisioning, and JWT token management.
"""

from datetime import datetime, timezone
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clerk import ClerkConfigurationError, ClerkTokenError, get_clerk_verifier
from app.core.config import get_settings
from app.core.database import get_db
from app.core.limiter import limiter
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.modules.auth.dependencies import get_current_active_user
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    AuthResponse,
    ClerkSyncRequest,
    LogoutResponse,
    TokenRefreshRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.modules.users.models import UserSettings
from sqlalchemy import or_


router = APIRouter()


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new student account",
    description="Creates a new student user, hashes password with Argon2id, provisions default study settings, and issues tokens.",
)
@limiter.limit(get_settings().RATE_LIMIT_AUTH_DEFAULT)
async def register(
    request: Request,
    payload: UserRegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthResponse:
    """Register a new student user account and provision default study settings."""
    # Check if an account with this normalized email already exists
    existing_stmt = select(User).where(User.email == payload.email)
    existing_result = await db.execute(existing_stmt)
    if existing_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists",
        )

    # Hash password with Argon2id
    hashed_pwd = hash_password(payload.password)
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Create new User model instance
    new_user = User(
        id=user_id,
        email=payload.email,
        password_hash=hashed_pwd,
        full_name=payload.full_name,
        university=payload.university,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    # Provision default UserSettings linked to the user
    new_settings = UserSettings(
        user_id=user_id,
        user=new_user,
        default_difficulty="medium",
        default_question_count=5,
        preferred_focus="all",
    )

    db.add(new_user)
    db.add(new_settings)

    # Persist both atomically
    try:
        await db.commit()
        await db.refresh(new_user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists",
        )
    except Exception:
        await db.rollback()
        raise

    # Issue access and refresh tokens
    settings = get_settings()
    access_token = create_access_token(new_user.id)
    refresh_token = create_refresh_token(new_user.id)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(new_user),
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate with email and password",
    description="Validates student credentials, checks active account status, and issues access and refresh tokens.",
)
@limiter.limit(get_settings().RATE_LIMIT_AUTH_DEFAULT)
async def login(
    request: Request,
    payload: UserLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthResponse:
    """Authenticate an existing user with email and password."""
    stmt = select(User).where(User.email == payload.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # Reject non-existent user or invalid password without revealing user existence
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reject inactive accounts with 403 Forbidden
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Issue access and refresh tokens
    settings = get_settings()
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Validates a refresh token, verifies the user account, and issues a fresh access token without rotating the refresh token.",
)
@limiter.limit(get_settings().RATE_LIMIT_AUTH_DEFAULT)
async def refresh_token_endpoint(
    request: Request,
    payload: TokenRefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Validate refresh token and issue a fresh access token without rotating refresh token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        decoded_payload = decode_refresh_token(payload.refresh_token)
    except TokenError:
        raise credentials_exception from None

    subject = decoded_payload.get("sub")
    if not subject:
        raise credentials_exception

    try:
        user_id = uuid.UUID(str(subject))
    except (ValueError, TypeError):
        raise credentials_exception

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    settings = get_settings()
    new_access_token = create_access_token(user.id)

    # Return new access token while retaining the submitted refresh token's validity
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=payload.refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="User logout",
    description="Stateless logout confirmation for authenticated user. Client discards its locally stored tokens.",
)
async def logout(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> LogoutResponse:
    """Confirm user logout.

    Stateless Architectural Note:
    PracPrep utilizes stateless JWTs without server-side token blacklists or
    database revocation storage. Logout confirms that the authenticated request
    was received and relies on the client discarding its stored tokens.
    """
    return LogoutResponse(message="Logged out successfully")


@router.post(
    "/clerk-sync",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Synchronize Clerk authentication session",
    description="Validates a Clerk session JWT token, provisions or links the corresponding PracPrep User, and issues native JWT tokens.",
)
@limiter.limit(get_settings().RATE_LIMIT_AUTH_DEFAULT)
async def clerk_sync(
    request: Request,
    payload: ClerkSyncRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthResponse:
    """Validate Clerk session token and exchange for PracPrep access and refresh tokens."""
    # 1. Extract raw token from Authorization header or request body
    auth_header = request.headers.get("Authorization")
    token: str | None = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif payload.clerk_token:
        token = payload.clerk_token.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Clerk session token in Authorization header or payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Cryptographically verify Clerk session token against Clerk JWKS
    try:
        claims = get_clerk_verifier().verify_token(token)
    except ClerkConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Clerk authentication configuration error: {exc}",
        ) from exc
    except ClerkTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Clerk token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Clerk token verification failed: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    clerk_sub = claims["sub"]
    email = claims.get("email") or claims.get("primary_email_address") or payload.email
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User email is required for account synchronization",
        )
    email = email.strip().lower()

    # 3. Locate existing user by Clerk provider ID or email address
    stmt = select(User).where(
        or_(
            User.auth_provider == f"clerk:{clerk_sub}",
            User.email == email,
        )
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if user is not None:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )
        # Link Clerk ID if user previously registered with email/password or another method
        if user.auth_provider != f"clerk:{clerk_sub}":
            user.auth_provider = f"clerk:{clerk_sub}"
            user.updated_at = now
        # Update full name if payload provided one and existing full_name is empty
        if payload.full_name and (not user.full_name or user.full_name == email):
            user.full_name = payload.full_name
            user.updated_at = now
        if payload.university and not user.university:
            user.university = payload.university
            user.updated_at = now
        await db.commit()
        await db.refresh(user)
    else:
        # Create new student User record linked to Clerk identity
        user_id = uuid.uuid4()
        full_name = payload.full_name or claims.get("name") or email.split("@")[0]
        # Generate secure random Argon2id password hash for placeholder authentication
        hashed_pwd = hash_password(uuid.uuid4().hex)

        user = User(
            id=user_id,
            email=email,
            password_hash=hashed_pwd,
            full_name=full_name,
            university=payload.university,
            is_active=True,
            auth_provider=f"clerk:{clerk_sub}",
            created_at=now,
            updated_at=now,
        )

        new_settings = UserSettings(
            user_id=user_id,
            user=user,
            default_difficulty="medium",
            default_question_count=5,
            preferred_focus="all",
        )

        db.add(user)
        db.add(new_settings)

        try:
            await db.commit()
            await db.refresh(user)
        except IntegrityError:
            await db.rollback()
            # If concurrent registration occurred, fetch existing user
            re_stmt = select(User).where(User.email == email)
            re_result = await db.execute(re_stmt)
            user = re_result.scalar_one_or_none()
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to synchronize user account",
                )
        except Exception:
            await db.rollback()
            raise

    # 4. Issue native PracPrep access and refresh tokens
    settings = get_settings()
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )
