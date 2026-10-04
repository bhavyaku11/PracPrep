"""Clerk Authentication Primitives & JWT Token Verification.

Provides asymmetric RS256 JWT validation using Clerk's JSON Web Key Set (JWKS),
deriving instance domains and verifying signature, expiration, and issuer claims.
"""

from collections.abc import Mapping
import logging
import ssl
from typing import Any, Optional

import certifi
import jwt
import jwt.exceptions

from app.core.config import Settings, get_settings
from app.core.security import TokenError

logger = logging.getLogger(__name__)


class ClerkTokenError(TokenError):
    """Base exception for all Clerk token validation failures."""


class ClerkConfigurationError(ClerkTokenError):
    """Raised when Clerk validation is attempted without required configuration."""


class ClerkTokenVerifier:
    """Verifies Clerk-issued asymmetric RS256 JWT tokens using Clerk's public JWKS."""

    def __init__(
        self,
        jwks_url: Optional[str] = None,
        issuer: Optional[str] = None,
        settings: Optional[Settings] = None,
    ):
        self._explicit_jwks_url = jwks_url
        self._explicit_issuer = issuer
        self._settings = settings
        self._jwks_client: Optional[jwt.PyJWKClient] = None
        self._ssl_context: Optional[ssl.SSLContext] = None

    @property
    def jwks_url(self) -> Optional[str]:
        if self._explicit_jwks_url:
            return self._explicit_jwks_url
        current_settings = self._settings or get_settings()
        return current_settings.clerk_jwks_url

    @property
    def issuer(self) -> Optional[str]:
        if self._explicit_issuer:
            return self._explicit_issuer
        current_settings = self._settings or get_settings()
        return current_settings.clerk_issuer_url

    def get_jwks_client(self) -> jwt.PyJWKClient:
        """Initialize and return cached PyJWKClient configured with certifi SSL context."""
        url = self.jwks_url
        if not url:
            raise ClerkConfigurationError("Clerk JWKS URL is not configured.")

        if self._jwks_client is None:
            if self._ssl_context is None:
                try:
                    self._ssl_context = ssl.create_default_context(cafile=certifi.where())
                except Exception:
                    self._ssl_context = ssl.create_default_context()
            self._jwks_client = jwt.PyJWKClient(
                url,
                ssl_context=self._ssl_context,
                cache_jwk_set=True,
                lifespan=3600,
            )
        return self._jwks_client

    def verify_token(self, token: str) -> dict[str, Any]:
        """Verify a Clerk session JWT token against Clerk's public keys.

        Enforces RS256 signature verification, non-expired lifespan,
        matching issuer (if configured), and presence of the 'sub' claim.

        Args:
            token: The raw JWT string from Authorization header or payload.

        Returns:
            Decoded and validated claims dictionary.

        Raises:
            ClerkTokenError: If the token is invalid, expired, or untrusted.
        """
        if not token or not isinstance(token, str) or not token.strip():
            raise ClerkTokenError("Token is empty or invalid.")

        clean_token = token.strip()
        try:
            headers = jwt.get_unverified_header(clean_token)
        except Exception as exc:
            raise ClerkTokenError(f"Malformed token headers: {exc}") from exc

        alg = headers.get("alg")
        if alg != "RS256":
            raise ClerkTokenError(f"Unsupported token algorithm: '{alg}'. Expected 'RS256'.")

        try:
            client = self.get_jwks_client()
            signing_key = client.get_signing_key_from_jwt(clean_token)
        except ClerkConfigurationError:
            raise
        except Exception as exc:
            raise ClerkTokenError(f"Failed to retrieve signing key for token: {exc}") from exc

        issuer = self.issuer
        options: dict[str, Any] = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_iat": True,
            "require": ["sub", "exp", "iat"],
        }
        if issuer:
            options["verify_iss"] = True

        try:
            payload = jwt.decode(
                clean_token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=issuer if issuer else None,
                options=options,
            )
        except jwt.exceptions.ExpiredSignatureError as exc:
            raise ClerkTokenError("Clerk token has expired.") from exc
        except jwt.exceptions.InvalidIssuerError as exc:
            raise ClerkTokenError("Clerk token issuer mismatch.") from exc
        except (jwt.exceptions.InvalidTokenError, jwt.exceptions.PyJWTError) as exc:
            raise ClerkTokenError(f"Invalid Clerk token signature or claims: {exc}") from exc
        except Exception as exc:
            raise ClerkTokenError(f"Token validation failed: {exc}") from exc

        sub = payload.get("sub")
        if not sub or not isinstance(sub, str) or not sub.strip():
            raise ClerkTokenError("Clerk token missing valid 'sub' claim.")

        return payload


_default_verifier: Optional[ClerkTokenVerifier] = None


def get_clerk_verifier() -> ClerkTokenVerifier:
    """Return the global ClerkTokenVerifier singleton instance."""
    global _default_verifier
    if _default_verifier is None:
        _default_verifier = ClerkTokenVerifier()
    return _default_verifier


def reset_clerk_verifier() -> None:
    """Reset global ClerkTokenVerifier instance for isolated tests."""
    global _default_verifier
    _default_verifier = None


def verify_clerk_token(token: str) -> dict[str, Any]:
    """Helper verifying token using the global ClerkTokenVerifier instance."""
    return get_clerk_verifier().verify_token(token)
