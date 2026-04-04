"""Authentication backend and dependencies for ClipperTV web app."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    BaseUser,
)

from clippertv.auth.crypto import CredentialEncryption
from clippertv.auth.service import AuthService
from clippertv.config import EnvConfig
from clippertv.data.turso_client import get_turso_client, initialize_database
from clippertv.data.user_store import UserStore

if TYPE_CHECKING:
    from starlette.requests import HTTPConnection

    from clippertv.data.models import User

COOKIE_NAME = "clippertv_token"
COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days

# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------

_auth_service: AuthService | None = None
_user_store: UserStore | None = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        key = EnvConfig.JWT_SECRET_KEY
        if not key:
            raise ValueError("JWT_SECRET_KEY not set")
        _auth_service = AuthService(
            secret_key=key,
            algorithm=EnvConfig.JWT_ALGORITHM,
            token_expiry_days=EnvConfig.JWT_EXPIRY_DAYS,
        )
    return _auth_service


def get_user_store() -> UserStore:
    global _user_store
    if _user_store is None:
        initialize_database()
        enc_key = EnvConfig.ENCRYPTION_KEY
        if not enc_key:
            raise ValueError("ENCRYPTION_KEY not set")
        _user_store = UserStore(
            client=get_turso_client(),
            auth_service=get_auth_service(),
            crypto=CredentialEncryption(encryption_key=enc_key),
        )
    return _user_store


# ---------------------------------------------------------------------------
# Starlette AuthenticationBackend
# ---------------------------------------------------------------------------


class AuthenticatedUser(BaseUser):
    """Wraps a clippertv User model for Starlette's auth system."""

    def __init__(self, user: User) -> None:
        self.user = user

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.user.name or self.user.email

    @property
    def identity(self) -> str:
        return self.user.id


class CookieAuthBackend(AuthenticationBackend):
    """Read JWT from httpOnly cookie and resolve to User."""

    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, BaseUser] | None:
        token = conn.cookies.get(COOKIE_NAME)
        if not token:
            return None

        auth = get_auth_service()
        user_id = auth.get_user_id_from_token(token)
        if not user_id:
            return None

        store = get_user_store()
        user = store.get_user_by_id(user_id)
        if not user:
            return None

        return AuthCredentials(["authenticated"]), AuthenticatedUser(user)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def require_auth(request: Request) -> User:
    """FastAPI dependency that ensures the request is authenticated.

    Returns the clippertv User model. Redirects to /login on failure,
    or sends HX-Redirect for HTMX requests.
    """
    if request.user.is_authenticated:
        return request.user.user  # type: ignore[union-attr]

    # HTMX requests: return 401 with HX-Redirect header
    if request.headers.get("HX-Request"):
        raise _htmx_login_redirect()

    raise _html_login_redirect()


class _htmx_login_redirect(Exception):
    """Signal for HTMX auth failure — handled by exception handler."""


class _html_login_redirect(Exception):
    """Signal for regular auth failure — handled by exception handler."""


def auth_exception_handlers() -> dict:
    """Return exception handlers to register on the FastAPI app."""

    async def htmx_redirect(_request: Request, _exc: _htmx_login_redirect):
        return Response(status_code=401, headers={"HX-Redirect": "/login"})

    async def html_redirect(_request: Request, _exc: _html_login_redirect):
        return RedirectResponse("/login", status_code=303)

    return {
        _htmx_login_redirect: htmx_redirect,
        _html_login_redirect: html_redirect,
    }
