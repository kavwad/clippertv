"""Settings routes for managing Clipper cards and preferences."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from clippertv.config import config
from clippertv.data.models import User
from clippertv.ingest.clipper import validate_and_discover
from clippertv.web.auth import get_user_store, require_auth

_ALL_CATEGORIES = [
    cat
    for cat in config.transit_categories.color_map
    if cat not in ("Unknown", "Other")
]

router = APIRouter(prefix="/settings")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@router.get("", response_class=HTMLResponse)
async def settings_page(request: Request, user: User = Depends(require_auth)):
    """Render settings page with user's clipper cards."""
    store = get_user_store()
    cards = store.get_user_clipper_cards(user.id)
    selected = user.display_categories or _ALL_CATEGORIES
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "user": user,
            "cards": cards,
            "all_categories": _ALL_CATEGORIES,
            "selected_categories": selected,
        },
    )


@router.post("/cards/{card_id}/rename", response_class=HTMLResponse)
async def rename_card(
    request: Request,
    card_id: str,
    user: User = Depends(require_auth),
    rider_name: str = Form(...),
):
    """Rename a clipper card. Returns updated card row partial."""
    store = get_user_store()
    card = store.get_clipper_card(card_id)

    if not card or card.user_id != user.id:
        return Response("Card not found", status_code=404)

    store.update_card_rider_name(card_id, rider_name)
    card = store.get_clipper_card(card_id)
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


@router.post("/categories")
async def save_categories(
    user: User = Depends(require_auth),
    categories: Annotated[list[str], Form()] = [],
):
    """Save display category preferences."""
    store = get_user_store()
    # None means "show all" (default behavior)
    cats = categories if categories else None
    store.update_display_categories(user.id, cats)
    return Response(status_code=204)


@router.post("/refresh-cards", response_class=HTMLResponse)
async def refresh_cards(
    request: Request,
    user: User = Depends(require_auth),
):
    """Re-validate Clipper credentials and discover new cards."""
    store = get_user_store()
    creds = store.decrypt_user_credentials(user)

    if not creds:
        return Response("No stored credentials", status_code=400)

    account_numbers = await asyncio.to_thread(
        validate_and_discover, creds["username"], creds["password"]
    )

    if account_numbers is None:
        store.set_needs_reauth(user.id, True)
        return Response(
            "Could not connect to Clipper. Your password may have changed.",
            status_code=401,
        )

    cards = (
        store.discover_and_sync_cards(user.id, account_numbers)
        if account_numbers
        else store.get_user_clipper_cards(user.id)
    )
    return templates.TemplateResponse(
        request,
        "partials/card_list.html",
        {"cards": cards},
    )
