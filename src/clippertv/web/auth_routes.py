"""Login and logout routes for ClipperTV."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from clippertv.ingest.clipper import validate_and_discover
from clippertv.web.auth import (
    COOKIE_MAX_AGE,
    COOKIE_NAME,
    get_auth_service,
    get_user_store,
)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Show login form, or redirect to dashboard if already authed."""
    if request.user.is_authenticated:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    """Unified login: bcrypt fast path, Clipper fallback for new/changed creds."""
    store = get_user_store()

    # Fast path: bcrypt check (also handles email-not-found → None)
    verified = store.verify_user_credentials(email=email, password=password)
    if verified:
        return _set_cookie_and_redirect(request, verified)

    # Bcrypt failed or email unknown — check if user exists
    existing = store.get_user_by_email(email)
    if existing:
        # Existing user, wrong password — try Clipper (maybe password changed)
        account_numbers = await asyncio.to_thread(
            validate_and_discover, email, password
        )
        if account_numbers is not None:
            store.update_user_credentials(existing.id, email, password)
            if account_numbers:
                store.discover_and_sync_cards(existing.id, account_numbers)
            return _set_cookie_and_redirect(request, existing)

        return _login_error(request, "Invalid credentials")

    # New user — must validate against Clipper
    account_numbers = await asyncio.to_thread(validate_and_discover, email, password)
    if account_numbers is None:
        return _login_error(request, "Invalid Clipper credentials")
    if not account_numbers:
        return _login_error(
            request,
            "Your Clipper account looks good, but we couldn't find any"
            " cards — ClipperTV discovers them from transaction history."
            " Try again after the next time you tag your Clipper card.",
        )

    user = store.create_user(email, password)
    store.discover_and_sync_cards(user.id, account_numbers)
    return _set_cookie_and_redirect(request, user)


def _set_cookie_and_redirect(request: Request, user) -> Response:
    """Create JWT, set cookie, redirect to dashboard."""
    auth = get_auth_service()
    token = auth.create_access_token(user_id=user.id, email=user.email)

    # HTMX requests need HX-Redirect header instead of 303
    if request.headers.get("HX-Request"):
        response = Response(status_code=200, headers={"HX-Redirect": "/"})
    else:
        response = RedirectResponse("/", status_code=303)

    response.set_cookie(
        key=COOKIE_NAME,
        value=token.access_token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
    return response


def _login_error(request: Request, error: str):
    """Render login page with error (for HTMX or full page)."""
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": error},
        status_code=401,
    )


@router.post("/logout")
async def logout():
    """Clear auth cookie and redirect to login."""
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return response
