import hashlib
import hmac
import html
import json
import os
import time
from urllib.parse import parse_qsl, urlencode

from aiohttp import web

from config import TOKEN, ADMIN_ID
from database import (
    add_user,
    get_user,
    get_balance,
    is_partner,
    set_partner,
    remove_partner,
    attach_client_to_partner,
    get_client,
    get_partner_clients,
    get_client_requests,
    create_car_request,
    create_deal,
    link_request_deal,
    get_partner_deals,
    get_history,
    get_request,
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "miniapp")
HOST = os.getenv("WEB_HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
AUTH_MAX_AGE = int(os.getenv("WEBAPP_AUTH_MAX_AGE", "86400"))


def validate_init_data(init_data: str):
    if not init_data:
        raise web.HTTPUnauthorized(text="Missing Telegram initData")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise web.HTTPUnauthorized(text="Missing initData hash")

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(pairs.items())
    )
    secret_key = hmac.new(
        b"WebAppData", TOKEN.encode(), hashlib.sha256
    ).digest()
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise web.HTTPUnauthorized(text="Invalid Telegram initData")

    auth_date = int(pairs.get("auth_date", "0"))
    if not auth_date or time.time() - auth_date > AUTH_MAX_AGE:
        raise web.HTTPUnauthorized(text="Expired Telegram initData")

    user_raw = pairs.get("user")
    if not user_raw:
        raise web.HTTPUnauthorized(text="Telegram user is missing")

    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        raise web.HTTPUnauthorized(text="Invalid Telegram user data")

    return user, pairs.get("start_param")


async def get_context(request):
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user, start_param = validate_init_data(init_data)
    telegram_id = int(user["id"])
    add_user(telegram_id, user.get("username"), user.get("first_name") or user.get("last_name") or "Клиент")

    # Direct Mini App referral: ?startapp=p_<partner_id>
    if start_param and start_param.startswith("p_"):
        try:
            partner_id = int(start_param[2:])
        except ValueError:
            partner_id = None
        if partner_id and partner_id != telegram_id:
            attach_client_to_partner(telegram_id, partner_id)

    db_user = get_user(telegram_id) or {
        "telegram_id": telegram_id,
        "username": user.get("username"),
        "full_name": user.get("first_name") or "Клиент",
        "balance": 0,
        "is_partner": 0,
    }
    return db_user, start_param


def user_payload(u):
    return {
        "id": u["telegram_id"],
        "username": u.get("username"),
        "name": u.get("full_name") or "Клиент",
        "is_partner": bool(u.get("is_partner")),
        "balance": int(u.get("balance") or 0),
    }


def request_payload(r):
    return dict(r)


def deal_payload(d):
    return dict(d)


async def api_me(request):
    u, start_param = await get_context(request)
    partner = get_client(u["telegram_id"])
    return web.json_response({
        "user": user_payload(u),
        "client": partner,
        "start_param": start_param,
    })


async def api_dashboard(request):
    u, _ = await get_context(request)
    uid = u["telegram_id"]
    client = get_client(uid)
    partner = bool(u.get("is_partner"))
    partners_clients = get_partner_clients(uid) if partner else []
    requests = []
    if partner:
        for c in partners_clients:
            requests.extend(get_client_requests(c["client_id"]))
    else:
        requests = get_client_requests(uid)
    requests = sorted(requests, key=lambda x: x.get("id", 0), reverse=True)[:30]
    deals = get_partner_deals(uid) if partner else []
    history = get_history(uid) if partner else []

    bot_username = ""
    # The frontend gets the actual link from BOT_USERNAME if configured.
    bot_username = os.getenv("BOT_USERNAME", "")
    referral_link = f"https://t.me/{bot_username}?startapp=p_{uid}" if partner and bot_username else ""

    return web.json_response({
        "user": user_payload(u),
        "client": client,
        "clients": partners_clients,
        "requests": [request_payload(r) for r in requests],
        "deals": [deal_payload(d) for d in deals[:30]],
        "history": [dict(x) for x in history[:30]],
        "referral_link": referral_link,
    })


async def api_submit_request(request):
    u, _ = await get_context(request)
    data = await request.json()
    required = ["country", "criteria", "budget", "year", "mileage", "engine", "payment", "timing", "additional"]
    missing = [k for k in required if not str(data.get(k, "")).strip()]
    if missing:
        return web.json_response({"ok": False, "error": "Заполните все поля заявки."}, status=400)

    uid = u["telegram_id"]
    client = get_client(uid)
    partner_id = client["partner_id"] if client else None

    request_id = create_car_request(uid, partner_id, data)
    deal_id = create_deal(uid, partner_id, 0)
    link_request_deal(request_id, deal_id)

    # Notifications are intentionally sent through the existing bot backend.
    bot = request.app["bot"]
    summary = (
        f"🚗 <b>НОВАЯ ЗАЯВКА #{request_id}</b>\n\n"
        f"👤 Клиент: <a href=\"tg://user?id={uid}\">{html.escape(u.get('full_name') or 'Клиент')}</a>\n"
        f"🌍 Страна: <b>{html.escape(str(data['country']))}</b>\n"
        f"🚘 Авто: <b>{html.escape(str(data['criteria']))}</b>\n"
        f"💰 Бюджет: <b>{html.escape(str(data['budget']))}</b>\n"
        f"📅 Год: <b>{html.escape(str(data['year']))}</b>\n"
        f"🛣 Пробег: <b>{html.escape(str(data['mileage']))}</b>\n"
        f"⚙️ Двигатель: <b>{html.escape(str(data['engine']))}</b>\n"
        f"💳 Оплата: <b>{html.escape(str(data['payment']))}</b>\n"
        f"⏱ Срок: <b>{html.escape(str(data['timing']))}</b>\n"
        f"📝 Дополнительно: <b>{html.escape(str(data['additional']))}</b>\n"
        f"📞 Контакт: <a href=\"tg://user?id={uid}\">{html.escape('@' + u.get('username')) if u.get('username') else html.escape(u.get('full_name') or 'Открыть профиль')}</a>\n"
        f"🤝 Партнёр: <code>{partner_id or 'нет'}</code>\n"
        f"🔢 Сделка: <b>#{deal_id}</b>"
    )
    try:
        await bot.send_message(ADMIN_ID, summary, parse_mode="HTML")
        if partner_id:
            await bot.send_message(partner_id, summary, parse_mode="HTML")
    except Exception:
        pass

    return web.json_response({"ok": True, "request_id": request_id, "deal_id": deal_id, "telegram_contact": f"tg://user?id={uid}"})


async def api_partner_start(request):
    u, _ = await get_context(request)
    set_partner(u["telegram_id"], True)
    u = get_user(u["telegram_id"])
    return web.json_response({"ok": True, "user": user_payload(u)})


async def api_partner_stop(request):
    u, _ = await get_context(request)
    remove_partner(u["telegram_id"])
    u = get_user(u["telegram_id"])
    return web.json_response({"ok": True, "user": user_payload(u)})


async def api_support(request):
    u, _ = await get_context(request)
    data = await request.json()
    text = str(data.get("text", "")).strip()
    if not text:
        return web.json_response({"ok": False, "error": "Напишите сообщение."}, status=400)
    bot = request.app["bot"]
    await bot.send_message(
        ADMIN_ID,
        f"📞 <b>Сообщение в поддержку</b>\n\n"
        f"👤 <a href=\"tg://user?id={u['telegram_id']}\">{html.escape(u.get('full_name') or 'Клиент')}</a>\n"
        f"🆔 <code>{u['telegram_id']}</code>\n\n"
        f"{html.escape(text)}",
        parse_mode="HTML",
    )
    return web.json_response({"ok": True})


async def index(request):
    return web.FileResponse(os.path.join(STATIC_DIR, "index.html"))


async def start_web_server(bot):
    app = web.Application()
    app["bot"] = bot
    app.router.add_get("/", index)
    app.router.add_get("/api/me", api_me)
    app.router.add_get("/api/dashboard", api_dashboard)
    app.router.add_post("/api/request", api_submit_request)
    app.router.add_post("/api/partner/start", api_partner_start)
    app.router.add_post("/api/partner/stop", api_partner_stop)
    app.router.add_post("/api/support", api_support)
    app.router.add_static("/static/", STATIC_DIR)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()
    return runner
