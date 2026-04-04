"""Login and logout routes for ClipperTV."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

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


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    """Verify credentials, set JWT cookie, redirect to dashboard."""
    store = get_user_store()
    user = store.verify_user_credentials(email=email, password=password)

    if not user:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid email or password"},
            status_code=401,
        )

    auth = get_auth_service()
    token = auth.create_access_token(user_id=user.id, email=user.email)

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


@router.post("/logout")
async def logout():
    """Clear auth cookie and redirect to login."""
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return response
