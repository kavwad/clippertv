"""Settings routes for managing Clipper cards."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from clippertv.data.models import ClipperCardCreate, User
from clippertv.web.auth import get_user_store, require_auth

router = APIRouter(prefix="/settings")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@router.get("", response_class=HTMLResponse)
async def settings_page(request: Request, user: User = Depends(require_auth)):
    """Render settings page with user's clipper cards."""
    store = get_user_store()
    cards = store.get_user_clipper_cards(user.id)
    return templates.TemplateResponse(
        request,
        "settings.html",
        {"user": user, "cards": cards},
    )


@router.post("/cards", response_class=HTMLResponse)
async def add_card(
    request: Request,
    user: User = Depends(require_auth),
    account_number: str = Form(...),
    card_serial: str = Form(""),
    rider_name: str = Form(...),
    clipper_email: str = Form(""),
    clipper_password: str = Form(""),
):
    """Add a new clipper card. Returns card row partial for HTMX."""
    store = get_user_store()

    creds = None
    if clipper_email and clipper_password:
        creds = {"username": clipper_email, "password": clipper_password}

    card_data = ClipperCardCreate(
        account_number=account_number,
        card_serial=card_serial or None,
        rider_name=rider_name,
        credentials=creds,
    )

    try:
        card = store.add_clipper_card(user.id, card_data)
    except ValueError as e:
        return Response(str(e), status_code=400)

    return templates.TemplateResponse(
        request,
        "partials/card_row.html",
        {"card": card},
    )


@router.delete("/cards/{card_id}")
async def delete_card(
    card_id: str,
    user: User = Depends(require_auth),
):
    """Delete a clipper card. Verifies ownership."""
    store = get_user_store()
    card = store.get_clipper_card(card_id)

    if not card or card.user_id != user.id:
        return Response("Card not found", status_code=404)

    store.delete_clipper_card(card_id)
    return Response(status_code=200)


@router.post("/cards/{card_id}/credentials")
async def update_credentials(
    card_id: str,
    user: User = Depends(require_auth),
    clipper_email: str = Form(...),
    clipper_password: str = Form(...),
):
    """Update Clipper credentials for a card."""
    store = get_user_store()
    card = store.get_clipper_card(card_id)

    if not card or card.user_id != user.id:
        return Response("Card not found", status_code=404)

    store.update_card_credentials(card_id, clipper_email, clipper_password)
    return Response("Credentials updated", status_code=200)
