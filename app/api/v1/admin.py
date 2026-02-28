"""Web admin panel routes, auth middleware, and settings persistence."""
from __future__ import annotations

import json
import logging
import math
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import quote

import jwt
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.database.repository import UserRepository
from app.database.session import AsyncSessionLocal
from database.models import Item, User

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/admin", tags=["admin"])

_TEMPLATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "templates"))
templates = Jinja2Templates(directory=_TEMPLATE_DIR)

_CONFIG_JSON_PATH = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")),
    "config.json",
)
_ENV_PATH = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")),
    ".env",
)

# ── JWT helpers ────────────────────────────────────────────────────────────────

_TOKEN_EXPIRE_MINUTES = 480


def _create_token(username: str) -> str:
    settings = get_settings()
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.web_admin_jwt_secret, algorithm="HS256")


def _validate_token(token: str | None) -> bool:
    if not token:
        return False
    try:
        settings = get_settings()
        jwt.decode(token, settings.web_admin_jwt_secret, algorithms=["HS256"])
        return True
    except jwt.PyJWTError:
        return False


# ── Auth middleware ────────────────────────────────────────────────────────────

_OPEN_PATHS = {"/admin/login"}


class AdminAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/admin"):
            return await call_next(request)
        if path in _OPEN_PATHS:
            return await call_next(request)
        token = request.cookies.get("admin_token")
        if not _validate_token(token):
            return RedirectResponse(url="/admin/login", status_code=303)
        return await call_next(request)


# ── DB session helper ──────────────────────────────────────────────────────────

async def _get_session():
    async with AsyncSessionLocal() as session:
        yield session


# ── Flash redirect helper ──────────────────────────────────────────────────────

def _redirect(url: str, msg: str, msg_type: str = "success") -> RedirectResponse:
    sep = "&" if "?" in url else "?"
    return RedirectResponse(
        url=f"{url}{sep}msg={quote(msg)}&type={msg_type}",
        status_code=303,
    )


# ── Login / Logout ─────────────────────────────────────────────────────────────

@admin_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    token = request.cookies.get("admin_token")
    if _validate_token(token):
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@admin_router.post("/login")
async def login_submit(request: Request):
    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    settings = get_settings()

    valid = (
        bool(settings.web_admin_password)
        and secrets.compare_digest(username, settings.web_admin_user)
        and secrets.compare_digest(password, settings.web_admin_password)
    )
    if not valid:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password."},
            status_code=401,
        )

    token = _create_token(username)
    response = RedirectResponse(url="/admin", status_code=303)
    response.set_cookie(
        key="admin_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=_TOKEN_EXPIRE_MINUTES * 60,
    )
    return response


@admin_router.post("/logout")
async def logout():
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie("admin_token")
    return response


# ── Dashboard ──────────────────────────────────────────────────────────────────

@admin_router.get("", response_class=HTMLResponse)
@admin_router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    async with AsyncSessionLocal() as session:
        total_users = (await session.execute(select(func.count()).select_from(User))).scalar() or 0
        total_items = (await session.execute(select(func.count()).select_from(Item))).scalar() or 0
        available_items = (
            await session.execute(select(func.count()).select_from(Item).where(Item.availability.is_(True)))
        ).scalar() or 0

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "active": "dashboard",
            "total_users": total_users,
            "total_items": total_items,
            "available_items": available_items,
        },
    )


# ── Users ──────────────────────────────────────────────────────────────────────

@admin_router.get("/users", response_class=HTMLResponse)
async def users_page(request: Request):
    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        users = await user_repo.list_users()
    return templates.TemplateResponse(
        "users.html",
        {"request": request, "active": "users", "users": users},
    )


@admin_router.post("/users")
async def add_user(request: Request):
    form = await request.form()
    try:
        telegram_id = int(str(form.get("telegram_id", "")).strip())
        role = str(form.get("role", "user")).strip()
        if role not in ("admin", "user"):
            raise ValueError("Invalid role")
    except (ValueError, TypeError):
        return _redirect("/admin/users", "Invalid input.", "error")

    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        existing = await user_repo.get_by_telegram_id(telegram_id)
        if existing:
            return _redirect("/admin/users", f"User {telegram_id} already exists.", "error")
        try:
            await user_repo.create_user(telegram_id, role)
            await session.commit()
        except Exception as e:
            logger.error("Error adding user: %s", e)
            return _redirect("/admin/users", "Failed to add user.", "error")

    return _redirect("/admin/users", f"User {telegram_id} added as {role}.")


@admin_router.post("/users/role")
async def set_user_role(request: Request):
    form = await request.form()
    try:
        telegram_id = int(str(form.get("telegram_id", "")).strip())
        role = str(form.get("role", "")).strip()
        if role not in ("admin", "user"):
            raise ValueError("Invalid role")
    except (ValueError, TypeError):
        return _redirect("/admin/users", "Invalid input.", "error")

    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        user = await user_repo.set_role(telegram_id, role)
        if not user:
            return _redirect("/admin/users", f"User {telegram_id} not found.", "error")
        await session.commit()

    return _redirect("/admin/users", f"User {telegram_id} role set to {role}.")


@admin_router.post("/users/delete")
async def delete_user(request: Request):
    form = await request.form()
    try:
        telegram_id = int(str(form.get("telegram_id", "")).strip())
    except (ValueError, TypeError):
        return _redirect("/admin/users", "Invalid input.", "error")

    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        deleted = await user_repo.delete_user(telegram_id)
        if not deleted:
            return _redirect("/admin/users", f"User {telegram_id} not found.", "error")
        await session.commit()

    return _redirect("/admin/users", f"User {telegram_id} deleted.")


# ── Items ──────────────────────────────────────────────────────────────────────

_ITEMS_PER_PAGE = 25


@admin_router.get("/items", response_class=HTMLResponse)
async def items_page(
    request: Request,
    page: int = 1,
    search: str = "",
    avail: str = "all",
):
    page = max(1, page)
    filters = []
    if search:
        filters.append(Item.item_name.ilike(f"%{search}%"))
    if avail == "yes":
        filters.append(Item.availability.is_(True))
    elif avail == "no":
        filters.append(Item.availability.is_(False))

    async with AsyncSessionLocal() as session:
        count_q = select(func.count()).select_from(Item)
        if filters:
            from sqlalchemy import and_
            count_q = count_q.where(and_(*filters))
        total = (await session.execute(count_q)).scalar() or 0

        total_pages = max(1, math.ceil(total / _ITEMS_PER_PAGE))
        page = min(page, total_pages)
        offset = (page - 1) * _ITEMS_PER_PAGE

        items_q = select(Item).order_by(Item.timestamp.desc()).limit(_ITEMS_PER_PAGE).offset(offset)
        if filters:
            from sqlalchemy import and_
            items_q = items_q.where(and_(*filters))
        items = list((await session.execute(items_q)).scalars().all())

    return templates.TemplateResponse(
        "items.html",
        {
            "request": request,
            "active": "items",
            "items": items,
            "page": page,
            "per_page": _ITEMS_PER_PAGE,
            "total": total,
            "total_pages": total_pages,
            "search": search,
            "avail": avail,
        },
    )


# ── Settings ───────────────────────────────────────────────────────────────────

@admin_router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    settings = get_settings()
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "active": "settings",
            "settings": settings,
            "allowed_types_str": "\n".join(settings.allowed_types),
            "config_json_exists": os.path.exists(_CONFIG_JSON_PATH),
        },
    )


@admin_router.post("/settings")
async def save_settings(request: Request):
    form = await request.form()

    try:
        allowed_types = [t.strip() for t in str(form.get("allowed_types", "")).splitlines() if t.strip()]
        if not allowed_types:
            raise ValueError("allowed_types cannot be empty")
        min_len = int(str(form.get("min_len_str", "1")).strip())
        max_len = int(str(form.get("max_len_str", "255")).strip())
        max_amount = int(str(form.get("max_item_amount", "1000000")).strip())
        max_price = float(str(form.get("max_item_price", "999999.99")).strip())
        skip_hours = form.get("skip_working_hours") == "on"

        if min_len < 1 or max_len < min_len:
            raise ValueError("Invalid string length range")
        if max_amount < 1:
            raise ValueError("max_item_amount must be >= 1")
        if max_price < 0:
            raise ValueError("max_item_price must be >= 0")
    except (ValueError, TypeError) as e:
        settings = get_settings()
        return templates.TemplateResponse(
            "settings.html",
            {
                "request": request,
                "active": "settings",
                "settings": settings,
                "allowed_types_str": "\n".join(settings.allowed_types),
                "config_json_exists": os.path.exists(_CONFIG_JSON_PATH),
                "error": str(e),
            },
            status_code=422,
        )

    new_values = {
        "allowed_types": allowed_types,
        "min_len_str": min_len,
        "max_len_str": max_len,
        "max_item_amount": max_amount,
        "max_item_price": max_price,
        "skip_working_hours": skip_hours,
    }

    try:
        if os.path.exists(_CONFIG_JSON_PATH):
            _save_to_json(_CONFIG_JSON_PATH, new_values)
        else:
            _save_to_env(_ENV_PATH, new_values)
    except Exception as e:
        logger.error("Failed to persist settings: %s", e)
        return _redirect("/admin/settings", f"Save failed: {e}", "error")

    # Reset settings cache so next request reloads from disk
    import app.core.config as _cfg
    _cfg.settings = None

    return _redirect("/admin/settings", "Settings saved.")


def _save_to_json(path: str, new_values: dict) -> None:
    with open(path, "r") as f:
        data = json.load(f)
    data["allowed_types"] = new_values["allowed_types"]
    data["min_len_str"] = new_values["min_len_str"]
    data["max_len_str"] = new_values["max_len_str"]
    data["max_item_amount"] = new_values["max_item_amount"]
    data["max_item_price"] = new_values["max_item_price"]
    data["skip_working_hours"] = str(new_values["skip_working_hours"])
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _save_to_env(path: str, new_values: dict) -> None:
    updates = {
        "ALLOWED_TYPES": json.dumps(new_values["allowed_types"]),
        "MIN_LEN_STR": str(new_values["min_len_str"]),
        "MAX_LEN_STR": str(new_values["max_len_str"]),
        "MAX_ITEM_AMOUNT": str(new_values["max_item_amount"]),
        "MAX_ITEM_PRICE": str(new_values["max_item_price"]),
        "SKIP_WORKING_HOURS": str(new_values["skip_working_hours"]).lower(),
    }
    lines: list[str] = []
    if os.path.exists(path):
        with open(path, "r") as f:
            lines = f.readlines()

    seen: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip().upper()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}\n")
            seen.add(key)
        else:
            new_lines.append(line)

    for key, val in updates.items():
        if key not in seen:
            new_lines.append(f"{key}={val}\n")

    with open(path, "w") as f:
        f.writelines(new_lines)
