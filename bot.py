
import asyncio
import html
import logging
import os
import socket
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
    WebAppInfo,
    MenuButtonWebApp,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import TOKEN, ADMIN_ID, DEFAULT_COMMISSION
from database import (
    init_db,
    add_user,
    get_user,
    get_balance,
    add_balance,
    set_balance,
    get_all_users,
    set_partner,
    remove_partner,
    is_partner,
    attach_client_to_partner,
    get_client,
    get_partner_clients,
    get_all_clients,
    create_car_request,
    link_request_deal,
    get_client_requests,
    get_request,
    set_request_status,
    add_commission_history,
    get_history,
    get_partners,
    create_deal,
    get_deals,
    get_partner_deals,
    get_deal,
    finish_deal,
    delete_user,
    count_stats,
)

socket.setdefaulttimeout(30)
logging.basicConfig(level=logging.INFO)

init_db()
bot = Bot(token=TOKEN)
dp = Dispatcher()
MINI_APP_URL = os.getenv("MINI_APP_URL", "").strip()

# ---------- States ----------

class CarRequest(StatesGroup):
    country = State()
    criteria = State()
    budget = State()
    year = State()
    mileage = State()
    engine = State()
    payment = State()
    timing = State()
    additional = State()
    contact = State()
    confirm = State()

class AdminCommission(StatesGroup):
    partner_id = State()
    amount = State()

class AdminDeal(StatesGroup):
    client_id = State()
    partner_id = State()
    amount = State()

# ---------- Keyboards ----------

main_keyboard_rows = [
    [KeyboardButton(text="🚗 Подобрать автомобиль")],
    [KeyboardButton(text="📋 Моя заявка"), KeyboardButton(text="🤝 Стать партнёром")],
    [KeyboardButton(text="📖 Как это работает"), KeyboardButton(text="💰 Баланс")],
    [KeyboardButton(text="📞 Поддержка")],
]
if MINI_APP_URL:
    main_keyboard_rows.insert(0, [KeyboardButton(text="📱 Открыть Mini App", web_app=WebAppInfo(url=MINI_APP_URL))])

main_kb = ReplyKeyboardMarkup(
    keyboard=main_keyboard_rows,
    resize_keyboard=True,
)

partner_keyboard_rows = [
    [KeyboardButton(text="🚗 Мои клиенты")],
    [KeyboardButton(text="📋 Мои заявки"), KeyboardButton(text="🚘 Мои сделки")],
    [KeyboardButton(text="🔗 Моя ссылка")],
    [KeyboardButton(text="💰 Мой баланс"), KeyboardButton(text="📜 История")],
    [KeyboardButton(text="❌ Разорвать партнёрство")],
    [KeyboardButton(text="🏠 Главное меню")],
]
if MINI_APP_URL:
    partner_keyboard_rows.insert(0, [KeyboardButton(text="📱 Открыть Mini App", web_app=WebAppInfo(url=MINI_APP_URL))])

partner_kb = ReplyKeyboardMarkup(
    keyboard=partner_keyboard_rows,
    resize_keyboard=True,
    is_persistent=True,
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👥 Партнёры"), KeyboardButton(text="🚗 Сделки")],
        [KeyboardButton(text="📋 Заявки"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="➕ Добавить партнёра")],
        [KeyboardButton(text="💰 Начислить комиссию"), KeyboardButton(text="🔄 Обнулить баланс")],
        [KeyboardButton(text="⚠️ Обнулить все балансы")],
    ],
    resize_keyboard=True,
)

def country_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇯🇵 Япония", callback_data="country:Япония"),
         InlineKeyboardButton(text="🇨🇳 Китай", callback_data="country:Китай")],
        [InlineKeyboardButton(text="🇰🇷 Корея", callback_data="country:Корея")],
    ])

def confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Всё верно", callback_data="request_confirm"),
         InlineKeyboardButton(text="✏️ Заполнить заново", callback_data="request_restart")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="request_cancel")],
    ])

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Партнёры", callback_data="admin_partners"),
         InlineKeyboardButton(text="🚗 Сделки", callback_data="admin_deals")],
        [InlineKeyboardButton(text="📋 Заявки", callback_data="admin_requests"),
         InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="➕ Добавить партнёра", callback_data="admin_add_partner")],
    ])

def back_admin():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_home")]
    ])

# ---------- Helpers ----------

def admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def money(n):
    return f"{int(n or 0):,}".replace(",", " ") + " ₽"

async def notify_admin(text):
    try:
        await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
    except Exception:
        logging.exception("Cannot notify admin")

async def notify_partner(partner_id, text):
    try:
        await bot.send_message(partner_id, text, parse_mode="HTML")
    except Exception:
        logging.exception("Cannot notify partner %s", partner_id)

def telegram_link(user_id: int, full_name: str = "Клиент") -> str:
    """Clickable Telegram profile link that works even without @username."""
    name = html.escape(full_name or "Клиент")
    return f'<a href="tg://user?id={int(user_id)}">{name}</a>'

def contact_display(user_id: int, username: str | None, full_name: str, preference: str) -> str:
    """Show the selected contact method plus a direct Telegram link."""
    tg = telegram_link(user_id, full_name)
    username_text = f' (@{html.escape(username)})' if username else ''
    preference = str(preference or "—")
    if preference.lower() in {"только telegram", "⏭ только telegram"}:
        return f"{tg}{username_text}"
    return f"{html.escape(preference)} | Telegram: {tg}{username_text}"

def request_summary(data, client_user=None):
    if client_user:
        contact = contact_display(
            client_user["telegram_id"],
            client_user.get("username"),
            client_user.get("full_name") or "Клиент",
            data.get("contact", "—"),
        )
    else:
        contact = html.escape(str(data.get("contact", "—")))

    return (
        "🚗 <b>ЗАЯВКА НА АВТО</b>\n\n"
        f"🌍 Страна: <b>{html.escape(str(data.get('country','—')))}</b>\n"
        f"🚘 Что ищем: <b>{html.escape(str(data.get('criteria','—')))}</b>\n"
        f"💰 Бюджет: <b>{html.escape(str(data.get('budget','—')))}</b>\n"
        f"📅 Год: <b>{html.escape(str(data.get('year','—')))}</b>\n"
        f"🛣 Пробег: <b>{html.escape(str(data.get('mileage','—')))}</b>\n"
        f"⚙️ Двигатель: <b>{html.escape(str(data.get('engine','—')))}</b>\n"
        f"💳 Оплата: <b>{html.escape(str(data.get('payment','—')))}</b>\n"
        f"⏱ Срок: <b>{html.escape(str(data.get('timing','—')))}</b>\n"
        f"📝 Дополнительно: <b>{html.escape(str(data.get('additional','—')))}</b>\n"
        f"📞 Контакт: {contact}"
    )

async def start_car_request(message, state):
    await state.clear()
    await state.set_state(CarRequest.country)
    await message.answer(
        "🚗 <b>Начинаем подбор автомобиля</b>\n\n"
        "Я задам несколько коротких вопросов. После этого заявка уйдёт ответственному менеджеру.\n\n"
        "Сначала выберите страну покупки:",
        reply_markup=country_kb(),
        parse_mode="HTML",
    )

# ---------- /start + referral ----------

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    user = message.from_user
    add_user(user.id, user.username, user.full_name)

    args = (message.text or "").split(maxsplit=1)
    referral_partner = None
    if len(args) == 2:
        try:
            referral_partner = int(args[1])
        except ValueError:
            referral_partner = None

    if referral_partner and referral_partner != user.id:
        result = attach_client_to_partner(user.id, referral_partner)
        if result == "attached":
            p = get_user(referral_partner)
            pname = p["full_name"] if p else str(referral_partner)
            await message.answer(
                f"🤝 Вы пришли по рекомендации партнёра <b>{html.escape(pname)}</b>.\n"
                "Он закреплён за вашей заявкой и будет видеть статус подбора.",
                parse_mode="HTML",
            )
        elif result == "already":
            c = get_client(user.id)
            if c:
                await message.answer(
                    "ℹ️ Вы уже закреплены за своим партнёром. "
                    "Повторная реферальная ссылка другого партнёра не меняет закрепление."
                )

    if admin(user.id):
        await message.answer("👑 <b>АДМИН-ПАНЕЛЬ</b>\nВыберите раздел:", reply_markup=admin_kb, parse_mode="HTML")
        await message.answer("Управление:", reply_markup=admin_menu())
        return

    if is_partner(user.id):
        await message.answer(
            "🤝 <b>Кабинет партнёра NY</b>\n\n"
            "Здесь вы можете получать клиентов по своей ссылке, "
            "видеть их заявки и контролировать сделки.",
            reply_markup=partner_kb,
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "<b>Приветствуем вас в NY!</b>\n\n"
            "Мы знаем, что выбор автомобиля — это не просто покупка, а поиск друга на дороге. "
            "Чтобы мы могли помочь вам найти именно тот вариант, который вас обрадует, "
            "давайте просто и быстро обсудим ваши предпочтения.\n\n"
            "Наш бот сделает всю рутину за вас — всего несколько шагов, и мы уже будем знать, что вам нужно.\n\n"
            "<b>Как это работает (очень просто):</b>\n\n"
            "1. Нажмите кнопку <b>«🚗 Подобрать автомобиль»</b> — и начнём.\n"
            "2. Выберите страну производства: Япония, Китай или Корея — какой рынок вам ближе по духу и задачам?\n"
            "3. Ответьте на несколько коротких вопросов о технике, внешности и удобстве — это займёт буквально пару минут.\n"
            "4. Проверьте получившуюся заявку — если всё так, как вы хотели, смело жмите <b>«✅ Всё верно»</b>.\n"
            "5. Сразу после этого ваш персональный менеджер получит все детали и свяжется с вами — без лишних ожиданий.\n\n"
            "<b>🤝 Для партнёров</b>\n"
            "Если вы хотите рекомендовать нас своим знакомым или клиентам и получать за это приятное вознаграждение — "
            "просто перейдите в раздел <b>«🤝 Стать партнёром»</b>. Расскажем все условия с удовольствием.",
            reply_markup=main_kb,
            parse_mode="HTML",
        )

# ---------- Client request FSM ----------

@dp.message(F.text == "🚗 Подобрать автомобиль")
async def pick_car(message: Message, state: FSMContext):
    await start_car_request(message, state)

@dp.callback_query(F.data.startswith("country:"))
async def country_selected(callback: CallbackQuery, state: FSMContext):
    country = callback.data.split(":", 1)[1]
    await state.update_data(country=country)
    await state.set_state(CarRequest.criteria)
    await callback.answer()
    extra = {
        "Япония": "Для Японии особенно важно указать: готовы ли рассматривать правый руль, нужен ли аукционный лист и допустим ли гибрид.",
        "Китай": "Для Китая важно указать: нужен ли новый автомобиль, желаемую комплектацию, готовы ли рассматривать локальную китайскую версию и важна ли гарантия.",
        "Корея": "Для Кореи важно указать: левый руль обязателен, желаемый двигатель/комплектацию и допустим ли пробег по корейским дорогам."
    }[country]
    await callback.message.answer(
        "🚘 <b>Что именно хотите купить?</b>\n\n"
        "Напишите своими словами: марка, модель, комплектация, кузов, двигатель и любые пожелания.\n\n"
        f"💡 {extra}\n\n"
        "Например: <i>Toyota RAV4, 2021–2023, гибрид, полный привод, "
        "белый, без серьёзных ДТП.</i>",
        parse_mode="HTML",
    )

@dp.message(CarRequest.criteria)
async def criteria(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if len(text) < 3:
        await message.answer("Напишите хотя бы несколько слов о желаемом автомобиле.")
        return
    await state.update_data(criteria=text)
    await state.set_state(CarRequest.budget)
    await message.answer("💰 <b>Какой бюджет?</b>\n\nНапишите сумму или диапазон и укажите валюту.\nНапример: <i>3–3,5 млн ₽</i>.", parse_mode="HTML")

@dp.message(CarRequest.budget)
async def budget(message: Message, state: FSMContext):
    await state.update_data(budget=(message.text or "").strip())
    await state.set_state(CarRequest.year)
    await message.answer("📅 <b>Какой год выпуска рассматриваете?</b>\n\nНапример: <i>2021–2024</i> или <i>от 2022</i>.", parse_mode="HTML")

@dp.message(CarRequest.year)
async def year(message: Message, state: FSMContext):
    await state.update_data(year=(message.text or "").strip())
    await state.set_state(CarRequest.mileage)
    await message.answer("🛣 <b>Какой максимальный пробег?</b>\n\nМожно написать <i>до 50 000 км</i>, <i>не важно</i> и т.п.", parse_mode="HTML")

@dp.message(CarRequest.mileage)
async def mileage(message: Message, state: FSMContext):
    await state.update_data(mileage=(message.text or "").strip())
    await state.set_state(CarRequest.engine)
    await message.answer(
        "⚙️ <b>Какой двигатель рассматриваете?</b>\n\n"
        "Напишите объём, бензин/дизель/гибрид/электро или допустимую мощность. "
        "Если ограничений нет — так и напишите."
    )

@dp.message(CarRequest.engine)
async def engine(message: Message, state: FSMContext):
    await state.update_data(engine=(message.text or "").strip())
    await state.set_state(CarRequest.payment)
    await message.answer("💳 <b>Как планируете оплачивать?</b>\n\nНапример: свои средства, кредит, частичная оплата, пока не определился.")

@dp.message(CarRequest.payment)
async def payment(message: Message, state: FSMContext):
    await state.update_data(payment=(message.text or "").strip())
    await state.set_state(CarRequest.timing)
    await message.answer("⏱ <b>Когда хотите получить автомобиль?</b>\n\nНапример: срочно, в течение месяца, 2–3 месяца, пока просто изучаю варианты.")

@dp.message(CarRequest.timing)
async def timing(message: Message, state: FSMContext):
    await state.update_data(timing=(message.text or "").strip())
    await state.set_state(CarRequest.additional)
    await message.answer(
        "📝 <b>Что ещё важно учесть?</b>\n\n"
        "Напишите любые дополнительные требования: цвет, привод, руль, "
        "аукционный лист, состояние, комплектация, гарантия, растаможка "
        "или просто «на ваше усмотрение»."
    )

@dp.message(CarRequest.additional)
async def additional(message: Message, state: FSMContext):
    await state.update_data(additional=(message.text or "").strip())
    await state.set_state(CarRequest.contact)
    await message.answer(
        "📞 <b>Как с вами связаться?</b>\n\n"
        "Можно отправить номер телефона кнопкой ниже или написать Telegram/WhatsApp.\n\n"
        "Если не хотите оставлять номер — напишите «только Telegram».",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📱 Отправить номер", request_contact=True)],
                      [KeyboardButton(text="⏭ Только Telegram")]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
        parse_mode="HTML",
    )

@dp.message(CarRequest.contact)
async def contact(message: Message, state: FSMContext):
    if message.contact:
        contact_value = message.contact.phone_number
    else:
        contact_value = (message.text or "").strip()
    if not contact_value:
        await message.answer("Укажите способ связи или нажмите «⏭ Только Telegram».")
        return
    await state.update_data(contact=contact_value)
    data = await state.get_data()
    await state.set_state(CarRequest.confirm)
    await message.answer(
        request_summary(data) + "\n\n<b>Проверьте данные перед отправкой.</b>",
        reply_markup=confirm_kb(),
        parse_mode="HTML",
        )
    await message.answer("Нажмите «Всё верно» или исправьте заявку.", reply_markup=ReplyKeyboardRemove())

@dp.callback_query(F.data == "request_restart")
async def request_restart(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await start_car_request(callback.message, state)

@dp.callback_query(F.data == "request_cancel")
async def request_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Заявка отменена")
    await callback.message.answer("Заявка отменена.", reply_markup=main_kb)

@dp.callback_query(F.data == "request_confirm")
async def request_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    client_id = callback.from_user.id
    client = get_client(client_id)
    partner_id = client["partner_id"] if client else None

    request_id = create_car_request(client_id, partner_id, data)
    deal_id = create_deal(client_id, partner_id, 0)
    link_request_deal(request_id, deal_id)
    await state.clear()
    await callback.answer("Заявка отправлена!")
    await callback.message.answer(
        f"✅ <b>Заявка #{request_id} принята.</b>\n🚗 Сделка <b>#{deal_id}</b> создана и передана в работу. \n\n"
        "Менеджер изучит параметры и свяжется с вами.\n"
        "Если вы пришли по партнёрской ссылке, заявка автоматически закреплена за этим партнёром.",
        reply_markup=main_kb,
        parse_mode="HTML",
    )

    client_user = get_user(client_id)
    partner_user = get_user(partner_id) if partner_id else None
    client_name = client_user["full_name"] if client_user else str(client_id)
    partner_name = partner_user["full_name"] if partner_user else "без партнёра"
    text = (
        f"🆕 <b>НОВАЯ ЗАЯВКА #{request_id}</b>\n\n"
        f"👤 Клиент: <b>{html.escape(client_name)}</b>\n"
        f"🆔 <code>{client_id}</code>\n"
        f"🤝 Партнёр: <b>{html.escape(partner_name)}</b>\n\n"
        + request_summary(data, client_user)
    )
    contact_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать клиенту", url=f"tg://user?id={client_id}")]
    ])
    try:
        await bot.send_message(ADMIN_ID, text, parse_mode="HTML", reply_markup=contact_kb)
    except Exception:
        logging.exception("Cannot notify admin")
    if partner_id:
        try:
            await bot.send_message(
                partner_id,
                f"🆕 <b>Новая заявка вашего клиента #{request_id}</b>\n\n" + request_summary(data, client_user),
                parse_mode="HTML",
                reply_markup=contact_kb,
            )
        except Exception:
            logging.exception("Cannot notify partner %s", partner_id)

@dp.message(F.text == "📋 Моя заявка")
async def my_request(message: Message):
    rows = get_client_requests(message.from_user.id)
    if not rows:
        await message.answer("📋 У вас пока нет заявок.")
        return
    text = "📋 <b>ВАШИ ЗАЯВКИ</b>\n\n"
    for r in rows[:10]:
        text += f"🚗 <b>#{r['id']}</b> — {html.escape(r['status'])}\n🌍 {html.escape(r['country'])}\n🚘 {html.escape(r['criteria'])}\n\n"
    await message.answer(text, parse_mode="HTML")

# ---------- Partner ----------

@dp.message(F.text == "🤝 Стать партнёром")
async def become_partner(message: Message):
    if is_partner(message.from_user.id):
        await message.answer(
            "🤝 <b>Вы уже являетесь партнёром NY.</b>\n\n"
            "Ваша партнёрская ссылка доступна в разделе «🔗 Моя ссылка».\n"
            "Если хотите прекратить партнёрство, используйте кнопку «❌ Разорвать партнёрство».",
            reply_markup=partner_kb,
            parse_mode="HTML",
        )
        return

    set_partner(message.from_user.id, True)
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={message.from_user.id}"
    break_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Разорвать партнёрство", callback_data="partner_break_confirm")]
    ])
    await message.answer(
        "🤝 <b>Партнёрство активировано!</b>\n\n"
        "Теперь вы можете приглашать клиентов своей ссылкой.\n"
        "Когда новый клиент впервые откроет бота по вашей ссылке и нажмёт /start, он автоматически закрепится за вами.\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n<code>{link}</code>\n\n"
        "❌ Если захотите прекратить партнёрство, кнопка «❌ Разорвать партнёрство» всегда находится в партнёрском меню ниже.",
        reply_markup=break_kb,
        parse_mode="HTML",
    )
    await message.answer("🤝 <b>Кабинет партнёра</b>", reply_markup=partner_kb, parse_mode="HTML")

@dp.message(F.text == "❌ Разорвать партнёрство")
async def break_partnership(message: Message):
    if not is_partner(message.from_user.id):
        await message.answer(
            "ℹ️ Вы сейчас не являетесь партнёром.",
            reply_markup=main_kb,
        )
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚠️ Да, разорвать", callback_data="partner_break_confirm"),
            InlineKeyboardButton(text="↩️ Отмена", callback_data="partner_break_cancel"),
        ]
    ])
    await message.answer(
        "⚠️ <b>Разорвать партнёрство?</b>\n\n"
        "Партнёрская ссылка перестанет работать для новых клиентов, а вы больше не сможете получать новых клиентов по реферальной системе.\n\n"
        "Уже закреплённые клиенты, заявки, сделки и история комиссий сохранятся.",
        reply_markup=keyboard,
        parse_mode="HTML",
    )

@dp.callback_query(F.data == "partner_break_cancel")
async def partner_break_cancel(callback: CallbackQuery):
    await callback.answer("Партнёрство сохранено")
    await callback.message.edit_text("↩️ <b>Партнёрство не изменено.</b>", parse_mode="HTML")
    await callback.message.answer("🤝 <b>Кабинет партнёра</b>", reply_markup=partner_kb, parse_mode="HTML")

@dp.callback_query(F.data == "partner_break_confirm")
async def partner_break_confirm(callback: CallbackQuery):
    remove_partner(callback.from_user.id)
    await callback.answer("Партнёрство прекращено")
    await callback.message.edit_text(
        "❌ <b>Партнёрство прекращено.</b>\n\n"
        "Ваши старые клиенты, заявки, сделки и история комиссий сохранены.\n"
        "Новые клиенты по вашей партнёрской ссылке больше закрепляться не будут.\n\n"
        "Если захотите вернуться в программу, нажмите «🤝 Стать партнёром».",
        parse_mode="HTML",
    )
    await callback.message.answer("Главное меню", reply_markup=main_kb)

@dp.message(F.text.in_({"🔗 Моя ссылка"}))
async def mylink(message: Message):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={message.from_user.id}"
    if is_partner(message.from_user.id):
        await message.answer(
            "🔗 <b>ВАША ПАРТНЁРСКАЯ ССЫЛКА</b>\n\n"
            f"<code>{link}</code>\n\n"
            "Клиенту нужно открыть ссылку и нажать /start.",
            parse_mode="HTML",
        )
    else:
        await message.answer(f"🔗 Ваша ссылка:\n<code>{link}</code>", parse_mode="HTML")

@dp.message(F.text.in_({"💰 Баланс", "💰 Мой баланс"}))
async def balance(message: Message):
    await message.answer(f"💰 <b>Баланс:</b> {money(get_balance(message.from_user.id))}", parse_mode="HTML")

@dp.message(F.text == "🚗 Мои клиенты")
async def my_clients(message: Message):
    if not is_partner(message.from_user.id):
        await message.answer("Сначала станьте партнёром.")
        return
    rows = get_partner_clients(message.from_user.id)
    if not rows:
        await message.answer("👥 Клиентов пока нет.")
        return
    text = "👥 <b>МОИ КЛИЕНТЫ</b>\n\n"
    for c in rows[:30]:
        u = get_user(c["client_id"])
        name = u["full_name"] if u else str(c["client_id"])
        text += f"👤 <b>{html.escape(name)}</b>\n🆔 <code>{c['client_id']}</code>\n📌 {html.escape(c['status'])}\n\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "📋 Мои заявки")
async def my_partner_requests(message: Message):
    if not is_partner(message.from_user.id):
        await message.answer("Сначала станьте партнёром.")
        return
    rows = get_partner_clients(message.from_user.id)
    sent = 0
    for c in rows:
        for r in get_client_requests(c["client_id"])[:5]:
            sent += 1
            await message.answer(
                f"🚗 <b>Заявка #{r['id']}</b>\n"
                f"👤 Клиент: <code>{c['client_id']}</code>\n"
                f"📌 Статус: <b>{html.escape(r['status'])}</b>\n\n"
                f"{request_summary(r)}",
                parse_mode="HTML",
            )
    if not sent:
        await message.answer("📋 Заявок от ваших клиентов пока нет.")

@dp.message(F.text == "🚘 Мои сделки")
async def my_partner_deals(message: Message):
    if not is_partner(message.from_user.id):
        await message.answer("Сначала станьте партнёром.")
        return
    rows = get_partner_deals(message.from_user.id)
    if not rows:
        await message.answer("🚘 Сделок пока нет.")
        return
    for d in rows[:20]:
        await message.answer(
            f"🚗 <b>Сделка #{d['id']}</b>\n"
            f"👤 Клиент: <code>{d['client_id']}</code>\n"
            f"📌 Статус: <b>{html.escape(d['status'])}</b>\n"
            f"💰 Комиссия: <b>{money(d['commission'])}</b>",
            parse_mode="HTML",
        )

@dp.message(F.text == "📜 История")
async def history(message: Message):
    rows = get_history(message.from_user.id)
    if not rows:
        await message.answer("📜 История начислений пока пустая.")
        return
    text = "📜 <b>ИСТОРИЯ НАЧИСЛЕНИЙ</b>\n\n"
    for row in rows[:30]:
        deal_text = f"#{row['deal_id']}" if row["deal_id"] else "ручное начисление"
        text += f"🚗 {deal_text}\n💰 +{money(row['amount'])}\n📅 {row['created_at']}\n\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "🏠 Главное меню")
async def home(message: Message):
    await message.answer("Главное меню.", reply_markup=partner_kb if is_partner(message.from_user.id) else main_kb)

@dp.message(F.text == "📖 Как это работает")
async def how_it_works(message: Message):
    await message.answer(
        "📖 <b>КАК ПОЛЬЗОВАТЬСЯ БОТОМ</b>\n\n"
        "🚗 <b>1. Подбор автомобиля</b>\n"
        "Выберите страну и ответьте на вопросы: автомобиль, бюджет, год, пробег, двигатель, оплата, сроки и дополнительные требования.\n\n"
        "📋 <b>2. Заявка</b>\n"
        "Перед отправкой вы увидите все данные и сможете исправить их. После подтверждения заявка передаётся менеджеру.\n\n"
        "🤝 <b>3. Если вы пришли по партнёрской ссылке</b>\n"
        "Заявка автоматически закрепляется за пригласившим партнёром.\n\n"
        "💬 <b>4. Связь</b>\n"
        "Можно оставить телефон или выбрать «Только Telegram».\n\n"
        "🚘 <b>5. Дальше</b>\n"
        "Менеджер изучает запрос, проверяет варианты и связывается с вами.",
        parse_mode="HTML",
    )

@dp.message(F.text == "📞 Поддержка")
async def support(message: Message):
    await message.answer("📞 По вопросам заказа и работы бота напишите администратору.")

# ---------- Admin ----------

@dp.message(Command("admin"))
async def admin_command(message: Message):
    if not admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer("👑 <b>АДМИН-ПАНЕЛЬ</b>", reply_markup=admin_kb, parse_mode="HTML")
    await message.answer("Выберите раздел:", reply_markup=admin_menu())

@dp.callback_query(F.data == "admin_home")
async def admin_home(callback: CallbackQuery):
    if not admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True); return
    await callback.answer()
    await callback.message.edit_text("👑 <b>АДМИН-ПАНЕЛЬ</b>", reply_markup=admin_menu(), parse_mode="HTML")

@dp.message(F.text == "👥 Партнёры")
async def partners_button(message: Message):
    if not admin(message.from_user.id): return
    await show_partners(message)

@dp.callback_query(F.data == "admin_partners")
async def admin_partners(callback: CallbackQuery):
    if not admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True); return
    await callback.answer()
    await show_partners(callback)

async def show_partners(target):
    rows = get_partners()
    text = "👥 <b>ПАРТНЁРЫ</b>\n\n"
    if not rows: text += "Партнёров пока нет."
    for r in rows:
        text += f"🤝 <b>{html.escape(r['full_name'])}</b>\n🆔 <code>{r['telegram_id']}</code>\n💰 {money(r['balance'])}\n👥 Клиентов: {r['clients_count']}\n\n"
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=back_admin(), parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=back_admin(), parse_mode="HTML")

@dp.message(F.text == "🚗 Сделки")
async def deals_button(message: Message):
    if admin(message.from_user.id):
        await show_deals(message)

@dp.callback_query(F.data == "admin_deals")
async def admin_deals(callback: CallbackQuery):
    if not admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True); return
    await callback.answer(); await show_deals(callback)

async def show_deals(target):
    rows = get_deals()
    text = "🚗 <b>СДЕЛКИ</b>\n\n"
    if not rows: text += "Сделок пока нет."
    for d in rows[:30]:
        text += f"#{d['id']} — {html.escape(d['status'])}\n👤 {d['client_id']} | 🤝 {d['partner_id'] or '—'}\n💰 {money(d['commission'])}\n\n"
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=back_admin(), parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=back_admin(), parse_mode="HTML")

@dp.message(F.text == "📋 Заявки")
async def requests_button(message: Message):
    if not admin(message.from_user.id): return
    await show_requests(message)

@dp.callback_query(F.data == "admin_requests")
async def admin_requests(callback: CallbackQuery):
    if not admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True); return
    await callback.answer(); await show_requests(callback)

async def show_requests(target):
    rows = get_all_clients()
    text = "📋 <b>ЗАЯВКИ / КЛИЕНТЫ</b>\n\n"
    for c in rows[:30]:
        u = get_user(c["client_id"])
        name = u["full_name"] if u else str(c["client_id"])
        text += f"👤 <b>{html.escape(name)}</b>\n🆔 <code>{c['client_id']}</code>\n🤝 Партнёр: <code>{c['partner_id'] or '—'}</code>\n📌 {html.escape(c['status'])}\n\n"
    if not rows: text += "Заявок пока нет."
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=back_admin(), parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=back_admin(), parse_mode="HTML")

@dp.message(F.text == "📊 Статистика")
async def stats_button(message: Message):
    if admin(message.from_user.id):
        await show_stats(message)

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True); return
    await callback.answer(); await show_stats(callback)

async def show_stats(target):
    s = count_stats()
    text = (
        "📊 <b>СТАТИСТИКА</b>\n\n"
        f"👥 Пользователей: <b>{s['users']}</b>\n"
        f"🤝 Партнёров: <b>{s['partners']}</b>\n"
        f"👤 Клиентов: <b>{s['clients']}</b>\n"
        f"📋 Заявок: <b>{s['requests']}</b>\n"
        f"🚗 Сделок: <b>{s['deals']}</b>\n"
        f"✅ Завершено: <b>{s['completed']}</b>\n"
        f"💰 Балансы: <b>{money(s['balances'])}</b>\n"
        f"💵 Комиссий: <b>{money(s['commissions'])}</b>"
    )
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=back_admin(), parse_mode="HTML")
    else:
        await target.answer(text, parse_mode="HTML")

@dp.message(F.text == "➕ Добавить партнёра")
async def add_partner_button(message: Message):
    if not admin(message.from_user.id): return
    await message.answer("Используйте команду:\n/add_partner ID\n\nПример:\n/add_partner 123456789")

@dp.callback_query(F.data == "admin_add_partner")
async def admin_add_partner(callback: CallbackQuery):
    if not admin(callback.from_user.id): return
    await callback.answer()
    await callback.message.edit_text("➕ <b>ДОБАВЛЕНИЕ ПАРТНЁРА</b>\n\n/add_partner ID", reply_markup=back_admin(), parse_mode="HTML")

@dp.message(Command("add_partner"))
async def add_partner_command(message: Message):
    if not admin(message.from_user.id): return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /add_partner ID"); return
    try: pid = int(parts[1])
    except ValueError:
        await message.answer("ID должен быть числом."); return
    if not get_user(pid):
        await message.answer("Пользователь не найден. Сначала он должен открыть бота /start."); return
    set_partner(pid, True)
    await message.answer(f"✅ Партнёр {pid} добавлен.")

@dp.message(F.text == "💰 Начислить комиссию")
async def commission_button(message: Message, state: FSMContext):
    if not admin(message.from_user.id): return
    await state.set_state(AdminCommission.partner_id)
    await message.answer("Введите Telegram ID партнёра:")

@dp.message(AdminCommission.partner_id)
async def commission_partner_id(message: Message, state: FSMContext):
    try: pid = int((message.text or "").strip())
    except ValueError:
        await message.answer("ID должен быть числом."); return
    await state.update_data(partner_id=pid)
    await state.set_state(AdminCommission.amount)
    await message.answer("Введите сумму комиссии:")

@dp.message(AdminCommission.amount)
async def commission_amount(message: Message, state: FSMContext):
    try: amount = int((message.text or "").strip())
    except ValueError:
        await message.answer("Сумма должна быть числом."); return
    data = await state.get_data()
    pid = data["partner_id"]
    if amount <= 0:
        await message.answer("Сумма должна быть больше 0."); return
    if not get_user(pid):
        await message.answer("Пользователь не найден."); await state.clear(); return
    add_balance(pid, amount)
    add_commission_history(pid, amount, None)
    await state.clear()
    await message.answer(f"✅ Начислено {money(amount)} партнёру {pid}.")
    await notify_partner(pid, f"💰 Вам начислена комиссия <b>{money(amount)}</b>.",)

@dp.message(F.text == "🔄 Обнулить баланс")
async def reset_balance_button(message: Message):
    if admin(message.from_user.id):
        await message.answer("Используйте /resetbalance ID")

@dp.message(Command("resetbalance"))
async def resetbalance(message: Message):
    if not admin(message.from_user.id): return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /resetbalance ID"); return
    try: pid = int(parts[1])
    except ValueError:
        await message.answer("ID должен быть числом."); return
    set_balance(pid, 0)
    await message.answer(f"✅ Баланс {pid} обнулён.")

@dp.message(F.text == "⚠️ Обнулить все балансы")
async def resetall_button(message: Message):
    if admin(message.from_user.id):
        await resetall(message)

@dp.message(Command("resetall"))
async def resetall(message: Message):
    if not admin(message.from_user.id): return
    for u in get_all_users():
        set_balance(u["telegram_id"], 0)
    await message.answer("⚠️ Все балансы обнулены.")

# ---------- Admin deal commands ----------

@dp.message(Command("deal"))
async def deal_command(message: Message):
    if not admin(message.from_user.id): return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Использование: /deal ID_клиента ID_партнёра"); return
    try:
        cid, pid = int(parts[1]), int(parts[2])
    except ValueError:
        await message.answer("ID должны быть числами."); return
    deal_id = create_deal(cid, pid, 0)
    await message.answer(f"🚗 Сделка #{deal_id} создана.")

@dp.message(Command("done"))
async def done_command(message: Message):
    if not admin(message.from_user.id): return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Использование: /done ID_сделки СУММА"); return
    try:
        did, amount = int(parts[1]), int(parts[2])
    except ValueError:
        await message.answer("ID и сумма должны быть числами."); return
    deal = get_deal(did)
    if not deal:
        await message.answer("Сделка не найдена."); return
    if deal["status"] == "Завершена":
        await message.answer("⚠️ Сделка уже завершена."); return
    partner_id = finish_deal(did, amount)
    add_commission_history(partner_id, amount, did)
    await message.answer(f"✅ Сделка #{did} завершена. Начислено {money(amount)}.")
    await notify_partner(partner_id, f"🎉 Сделка <b>#{did}</b> завершена.\n💰 Начислено: <b>{money(amount)}</b>.")

# ---------- Cancel ----------

@dp.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    if await state.get_state():
        await state.clear()
        await message.answer("❌ Текущая операция отменена.", reply_markup=main_kb)

# ---------- Unknown ----------

@dp.message()
async def other(message: Message):
    if admin(message.from_user.id):
        await message.answer("👑 Используйте админское меню.", reply_markup=admin_kb)
    elif is_partner(message.from_user.id):
        await message.answer("Используйте кнопки партнёрского меню.", reply_markup=partner_kb)
    else:
        await message.answer("Используйте кнопки меню.", reply_markup=main_kb)

async def setup_mini_app_menu():
    """Configure Telegram chat menu button when MINI_APP_URL is set."""
    if not MINI_APP_URL:
        logging.warning("MINI_APP_URL is not set; Mini App menu button is disabled.")
        return
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🚗 Открыть приложение",
                web_app=WebAppInfo(url=MINI_APP_URL),
            )
        )
        logging.info("Mini App menu button configured: %s", MINI_APP_URL)
    except Exception:
        logging.exception("Failed to configure Mini App menu button")


async def main():
    print("Бот запущен...")
    await setup_mini_app_menu()
    from webapp import start_web_server
    web_runner = await start_web_server(bot)
    try:
        await dp.start_polling(bot)
    finally:
        await web_runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
