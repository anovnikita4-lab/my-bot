import asyncio
import html
import logging
import socket
import sys

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import TOKEN, ADMIN_ID

from database import (
    init_db,
    add_user,
    get_balance,
    get_history,
    get_clients,
    delete_user,
    get_partners,
    get_all_users,
    add_balance,
    set_balance,
    create_deal,
    get_deals,
    finish_deal,
    add_partner,
    remove_partner,
)


# =========================================================
# НАСТРОЙКИ
# =========================================================

socket.setdefaulttimeout(30)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)

init_db()


bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    ),
)

dp = Dispatcher()


# =========================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def money(amount) -> str:
    try:
        return f"{int(amount or 0):,}".replace(",", " ") + " ₽"
    except (TypeError, ValueError):
        return "0 ₽"


def safe(value) -> str:
    return html.escape(str(value or ""))


def inline_menu(rows):
    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


async def deny(message: Message):
    await message.answer("⛔ Доступ запрещён.")


async def deny_callback(callback: CallbackQuery):
    await callback.answer(
        "⛔ Нет доступа",
        show_alert=True,
    )


# =========================================================
# КЛАВИАТУРА ПАРТНЕРА
# =========================================================

partner_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🔗 Моя ссылка")
        ],
        [
            KeyboardButton(text="👥 Мои клиенты")
        ],
        [
            KeyboardButton(text="💰 Мой баланс")
        ],
        [
            KeyboardButton(text="📜 История")
        ],
    ],
    resize_keyboard=True,
)


# =========================================================
# КЛАВИАТУРА АДМИНА
# =========================================================

admin_reply_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="👥 Партнёры"),
            KeyboardButton(text="🚗 Сделки"),
        ],
        [
            KeyboardButton(text="📊 Статистика"),
        ],
    ],
    resize_keyboard=True,
)


# =========================================================
# ГЛАВНОЕ INLINE-МЕНЮ АДМИНА
# =========================================================

def admin_menu(page: int = 1):

    if page == 1:

        keyboard = [
            [
                InlineKeyboardButton(
                    text="👥 Партнёры",
                    callback_data="admin_partners",
                ),
                InlineKeyboardButton(
                    text="🚗 Сделки",
                    callback_data="admin_deals",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data="admin_stats",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="▶️ Далее",
                    callback_data="admin_page_2",
                ),
            ],
        ]

    elif page == 2:

        keyboard = [
            [
                InlineKeyboardButton(
                    text="➕ Добавить партнёра",
                    callback_data="add_partner_help",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💰 Начислить",
                    callback_data="commission_help",
                ),
                InlineKeyboardButton(
                    text="🔄 Баланс",
                    callback_data="balance_menu",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Убрать партнёра",
                    callback_data="remove_partner_help",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data="admin_page_1",
                ),
                InlineKeyboardButton(
                    text="▶️ Далее",
                    callback_data="admin_page_3",
                ),
            ],
        ]

    else:

        keyboard = [
            [
                InlineKeyboardButton(
                    text="🔎 Проверить базу",
                    callback_data="check_database",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📋 Все пользователи",
                    callback_data="all_users",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🚗 Создать сделку",
                    callback_data="create_deal_help",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить пользователя",
                    callback_data="delete_user_help",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data="admin_page_2",
                ),
            ],
        ]

    return inline_menu(keyboard)


# =========================================================
# СТРАНИЦЫ АДМИНКИ
# =========================================================

async def show_admin_page(target, page: int):

    if page == 1:

        text = (
            "👑 <b>АДМИН-ПАНЕЛЬ</b>\n\n"
            "Главное меню управления партнёрской системой."
        )

    elif page == 2:

        text = (
            "👑 <b>УПРАВЛЕНИЕ</b>\n\n"
            "Партнёры, комиссии и баланс."
        )

    else:

        text = (
            "⚙️ <b>ДОПОЛНИТЕЛЬНО</b>\n\n"
            "Системные функции базы и сделок."
        )

    markup = admin_menu(page)

    if isinstance(target, CallbackQuery):

        if target.message:
            await target.message.edit_text(
                text,
                reply_markup=markup,
            )

    else:

        await target.answer(
            text,
            reply_markup=markup,
        )


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start(message: Message):

    user = message.from_user

    if user is None:
        return

    args = (message.text or "").split()

    invited_by = None

    if len(args) > 1:

        try:
            invited_by = int(args[1])

        except ValueError:
            invited_by = None

    # Нельзя пригласить самого себя
    if invited_by == user.id:
        invited_by = None

    try:

        add_user(
            telegram_id=user.id,
            username=user.username,
            full_name=user.full_name,
            invited_by=invited_by,
        )

    except Exception as e:

        logger.exception(
            "Ошибка добавления пользователя %s: %s",
            user.id,
            e,
        )

        await message.answer(
            "⚠️ Произошла ошибка при регистрации.\n"
            "Попробуйте ещё раз через несколько секунд."
        )

        return

    # -----------------------------------------------------
    # АДМИН
    # -----------------------------------------------------

    if is_admin(user.id):

        await message.answer(
            "👑 <b>Добро пожаловать в админ-панель!</b>\n\n"
            "Бот готов к работе.",
            reply_markup=admin_reply_kb,
        )

        await message.answer(
            "👑 <b>АДМИН-ПАНЕЛЬ</b>\n\n"
            "Выберите нужный раздел:",
            reply_markup=admin_menu(1),
        )

        return

    # -----------------------------------------------------
    # ПАРТНЁР
    # -----------------------------------------------------

    await message.answer(
        "🚗 <b>Добро пожаловать в NY Партнёры!</b>\n\n"
        "Здесь вы можете получать комиссию "
        "за клиентов, которых привели на подбор автомобиля.\n\n"
        "Используйте меню ниже.",
        reply_markup=partner_kb,
    )


# =========================================================
# /ADMIN
# =========================================================

@dp.message(Command("admin"))
async def admin_panel(message: Message):

    if not is_admin(message.from_user.id):
        await deny(message)
        return

    await message.answer(
        "👑 <b>АДМИН-ПАНЕЛЬ</b>",
        reply_markup=admin_menu(1),
    )


# =========================================================
# НАВИГАЦИЯ АДМИНКИ
# =========================================================

@dp.callback_query(F.data == "admin_page_1")
async def admin_page_1(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    await callback.answer()
    await show_admin_page(callback, 1)


@dp.callback_query(F.data == "admin_page_2")
async def admin_page_2(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    await callback.answer()
    await show_admin_page(callback, 2)


@dp.callback_query(F.data == "admin_page_3")
async def admin_page_3(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    await callback.answer()
    await show_admin_page(callback, 3)


# =========================================================
# МОЯ ССЫЛКА
# =========================================================

@dp.message(F.text == "🔗 Моя ссылка")
async def my_link(message: Message):

    me = await bot.get_me()

    if not me.username:
        await message.answer(
            "⚠️ Не удалось получить username бота."
        )
        return

    link = (
        f"https://t.me/{me.username}"
        f"?start={message.from_user.id}"
    )

    await message.answer(
        "🔗 <b>ВАША ПАРТНЁРСКАЯ ССЫЛКА</b>\n\n"
        f"<code>{safe(link)}</code>\n\n"
        "Отправляйте эту ссылку клиентам.\n"
        "Когда человек перейдёт по ней, бот "
        "сохранит связь с вами."
    )


# =========================================================
# МОИ КЛИЕНТЫ
# =========================================================

@dp.message(F.text == "👥 Мои клиенты")
async def clients(message: Message):

    users = get_clients(message.from_user.id)

    if not users:

        await message.answer(
            "👥 <b>МОИ КЛИЕНТЫ</b>\n\n"
            "Пока клиентов нет."
        )

        return

    text = "👥 <b>МОИ КЛИЕНТЫ</b>\n\n"

    for user in users:

        telegram_id = user[0]
        username = user[1]
        name = user[2]

        if username:

            text += (
                f"👤 @{safe(username)}\n"
                f"🆔 ID: <code>{telegram_id}</code>\n\n"
            )

        else:

            text += (
                f"👤 {safe(name)}\n"
                f"🆔 ID: <code>{telegram_id}</code>\n\n"
            )

    await message.answer(text)


# =========================================================
# МОЙ БАЛАНС
# =========================================================

@dp.message(F.text == "💰 Мой баланс")
async def my_balance(message: Message):

    balance = get_balance(
        message.from_user.id
    )

    await message.answer(
        "💰 <b>ВАШ БАЛАНС</b>\n\n"
        f"<b>{money(balance)}</b>"
    )


# =========================================================
# ИСТОРИЯ
# =========================================================

@dp.message(F.text == "📜 История")
async def history(message: Message):

    data = get_history(
        message.from_user.id
    )

    if not data:

        await message.answer(
            "📜 <b>ИСТОРИЯ</b>\n\n"
            "История начислений пока пустая."
        )

        return

    text = "📜 <b>ИСТОРИЯ НАЧИСЛЕНИЙ</b>\n\n"

    for item in data:

        amount = item[0]
        deal_id = item[1]
        date = item[2]

        text += (
            f"🚗 Сделка <b>#{deal_id}</b>\n"
            f"💰 +{money(amount)}\n"
            f"📅 {safe(date)}\n"
            "────────────\n"
        )

    await message.answer(text)


# =========================================================
# ПАРТНЁРЫ — ПАГИНАЦИЯ
# =========================================================

def partners_keyboard(page: int = 0):

    users = get_partners()

    per_page = 5

    total_pages = max(
        1,
        (len(users) + per_page - 1) // per_page,
    )

    page = max(
        0,
        min(page, total_pages - 1),
    )

    start_index = page * per_page
    end_index = start_index + per_page

    current = users[start_index:end_index]

    keyboard = []

    for user in current:

        telegram_id = user[0]
        name = user[2]

        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"👤 {str(name)[:50]}",
                    callback_data=(
                        f"partner_view:{telegram_id}"
                    ),
                )
            ]
        )

    navigation = []

    if page > 0:

        navigation.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=(
                    f"partners_page:{page - 1}"
                ),
            )
        )

    navigation.append(
        InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}",
            callback_data="noop",
        )
    )

    if page < total_pages - 1:

        navigation.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=(
                    f"partners_page:{page + 1}"
                ),
            )
        )

    keyboard.append(navigation)

    keyboard.append(
        [
            InlineKeyboardButton(
                text="🔙 В меню",
                callback_data="admin_page_1",
            )
        ]
    )

    return inline_menu(keyboard)


async def show_partners(
    callback: CallbackQuery,
    page: int = 0,
):

    users = get_partners()

    if not users:

        await callback.message.edit_text(
            "👥 <b>ПАРТНЁРЫ</b>\n\n"
            "Партнёров пока нет.",
            reply_markup=inline_menu(
                [
                    [
                        InlineKeyboardButton(
                            text="🔙 В меню",
                            callback_data="admin_page_1",
                        )
                    ]
                ]
            ),
        )

        return

    await callback.message.edit_text(
        "👥 <b>ПАРТНЁРЫ</b>\n\n"
        "Выберите партнёра:",
        reply_markup=partners_keyboard(page),
    )


@dp.callback_query(F.data == "admin_partners")
async def admin_partners_callback(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    await callback.answer()

    await show_partners(
        callback,
        0,
    )


@dp.callback_query(
    F.data.startswith("partners_page:")
)
async def partners_page(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    try:

        page = int(
            callback.data.split(":", 1)[1]
        )

    except (ValueError, AttributeError):

        await callback.answer(
            "Ошибка страницы",
            show_alert=True,
        )

        return

    await callback.answer()

    await show_partners(
        callback,
        page,
    )


# =========================================================
# КАРТОЧКА ПАРТНЁРА
# =========================================================

def partner_card_markup(
    partner_id: int,
):

    return inline_menu(
        [
            [
                InlineKeyboardButton(
                    text="💰 Начислить",
                    callback_data=(
                        f"commission_partner:{partner_id}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Обнулить",
                    callback_data=(
                        f"reset_partner:{partner_id}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="➖ Убрать из партнёров",
                    callback_data=(
                        f"remove_partner:{partner_id}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 К партнёрам",
                    callback_data="admin_partners",
                )
            ],
        ]
    )


async def render_partner_card(
    callback: CallbackQuery,
    partner_id: int,
):

    users = get_partners()

    partner = next(
        (
            user
            for user in users
            if user[0] == partner_id
        ),
        None,
    )

    if not partner:

        await callback.answer(
            "Партнёр не найден",
            show_alert=True,
        )

        return

    telegram_id = partner[0]
    username = partner[1]
    name = partner[2]
    balance = partner[3]

    username_text = (
        f"@{safe(username)}"
        if username
        else "не указан"
    )

    clients_list = get_clients(
        telegram_id
    )

    history_data = get_history(
        telegram_id
    )

    text = (
        "👤 <b>КАРТОЧКА ПАРТНЁРА</b>\n\n"
        f"👤 Имя: <b>{safe(name)}</b>\n"
        f"🆔 ID: <code>{telegram_id}</code>\n"
        f"📱 Username: {username_text}\n\n"
        f"💰 Баланс: <b>{money(balance)}</b>\n"
        f"👥 Клиентов: <b>{len(clients_list)}</b>\n"
        f"📜 Начислений: <b>{len(history_data)}</b>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=partner_card_markup(
            telegram_id
        ),
    )


@dp.callback_query(
    F.data.startswith("partner_view:")
)
async def partner_view(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    try:

        partner_id = int(
            callback.data.split(":", 1)[1]
        )

    except (ValueError, AttributeError):

        await callback.answer(
            "Некорректный ID",
            show_alert=True,
        )

        return

    await callback.answer()

    await render_partner_card(
        callback,
        partner_id,
    )


# =========================================================
# СДЕЛКИ — ПАГИНАЦИЯ
# =========================================================

def deals_keyboard(page: int = 0):

    data = get_deals()

    per_page = 5

    total_pages = max(
        1,
        (len(data) + per_page - 1) // per_page,
    )

    page = max(
        0,
        min(page, total_pages - 1),
    )

    start_index = page * per_page
    end_index = start_index + per_page

    current = data[
        start_index:end_index
    ]

    keyboard = []

    for deal in current:

        deal_id = deal[0]
        status = deal[3]

        keyboard.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"🚗 #{deal_id} — "
                        f"{status}"
                    ),
                    callback_data=(
                        f"deal_view:{deal_id}"
                    ),
                )
            ]
        )

    navigation = []

    if page > 0:

        navigation.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=(
                    f"deals_page:{page - 1}"
                ),
            )
        )

    navigation.append(
        InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}",
            callback_data="noop",
        )
    )

    if page < total_pages - 1:

        navigation.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=(
                    f"deals_page:{page + 1}"
                ),
            )
        )

    keyboard.append(navigation)

    keyboard.append(
        [
            InlineKeyboardButton(
                text="🔙 В меню",
                callback_data="admin_page_1",
            )
        ]
    )

    return inline_menu(keyboard)


async def show_deals(
    callback: CallbackQuery,
    page: int = 0,
):

    data = get_deals()

    if not data:

        await callback.message.edit_text(
            "🚗 <b>СДЕЛКИ</b>\n\n"
            "Сделок пока нет.",
            reply_markup=inline_menu(
                [
                    [
                        InlineKeyboardButton(
                            text="🔙 В меню",
                            callback_data="admin_page_1",
                        )
                    ]
                ]
            ),
        )

        return

    await callback.message.edit_text(
        "🚗 <b>СДЕЛКИ</b>\n\n"
        "Выберите сделку:",
        reply_markup=deals_keyboard(page),
    )


@dp.callback_query(F.data == "admin_deals")
async def admin_deals_callback(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    await callback.answer()

    await show_deals(
        callback,
        0,
    )


@dp.callback_query(
    F.data.startswith("deals_page:")
)
async def deals_page(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    try:

        page = int(
            callback.data.split(":", 1)[1]
        )

    except (ValueError, AttributeError):

        await callback.answer(
            "Ошибка страницы",
            show_alert=True,
        )

        return

    await callback.answer()

    await show_deals(
        callback,
        page,
    )


# =========================================================
# КАРТОЧКА СДЕЛКИ
# =========================================================

@dp.callback_query(
    F.data.startswith("deal_view:")
)
async def deal_view(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    try:

        deal_id = int(
            callback.data.split(":", 1)[1]
        )

    except (ValueError, AttributeError):

        await callback.answer(
            "Некорректный ID сделки",
            show_alert=True,
        )

        return

    data = get_deals()

    deal = next(
        (
            item
            for item in data
            if item[0] == deal_id
        ),
        None,
    )

    if not deal:

        await callback.answer(
            "Сделка не найдена",
            show_alert=True,
        )

        return

    _, client, partner, status, commission = deal

    text = (
        "🚗 <b>КАРТОЧКА СДЕЛКИ</b>\n\n"
        f"🔢 Номер: <b>#{deal_id}</b>\n"
        f"👤 Клиент: <code>{client}</code>\n"
        f"🤝 Партнёр: <code>{partner}</code>\n"
        f"📌 Статус: <b>{safe(status)}</b>\n"
        f"💰 Комиссия: <b>{money(commission)}</b>"
    )

    keyboard = []

    if status != "Завершена":

        keyboard.append(
            [
                InlineKeyboardButton(
                    text="✅ Завершить",
                    callback_data=(
                        f"done_help:{deal_id}"
                    ),
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                text="🔙 К сделкам",
                callback_data="admin_deals",
            )
        ]
    )

    await callback.answer()

    await callback.message.edit_text(
        text,
        reply_markup=inline_menu(keyboard),
    )


# =========================================================
# СТАТИСТИКА
# =========================================================

def build_stats_text():

    users = get_all_users()
    partners = get_partners()
    deals = get_deals()

    total_balance = 0

    for user in users:

        try:
            total_balance += int(
                user[2] or 0
            )

        except (TypeError, ValueError):
            pass

    completed = 0
    new_deals = 0
    total_commission = 0

    for deal in deals:

        status = deal[3]

        try:
            commission = int(
                deal[4] or 0
            )

        except (TypeError, ValueError):
            commission = 0

        total_commission += commission

        if status == "Завершена":

            completed += 1

        else:

            new_deals += 1

    return (
        "📊 <b>СТАТИСТИКА</b>\n\n"
        f"👥 Пользователей: "
        f"<b>{len(users)}</b>\n"
        f"🤝 Партнёров: "
        f"<b>{len(partners)}</b>\n\n"
        f"🚗 Сделок: "
        f"<b>{len(deals)}</b>\n"
        f"✅ Завершено: "
        f"<b>{completed}</b>\n"
        f"🆕 В работе: "
        f"<b>{new_deals}</b>\n\n"
        f"💰 Начислено: "
        f"<b>{money(total_commission)}</b>\n"
        f"💵 Балансы: "
        f"<b>{money(total_balance)}</b>"
    )


@dp.callback_query(
    F.data == "admin_stats"
)
async def admin_stats_callback(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    await callback.answer()

    await callback.message.edit_text(
        build_stats_text(),
        reply_markup=inline_menu(
            [
                [
                    InlineKeyboardButton(
                        text="🔄 Обновить",
                        callback_data="admin_stats",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 В меню",
                        callback_data="admin_page_1",
                    )
                ],
            ]
        ),
    )


# =========================================================
# REPLY-МЕНЮ АДМИНА
# =========================================================

@dp.message(F.text == "👥 Партнёры")
async def partners_button(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "👥 <b>ПАРТНЁРЫ</b>\n\n"
        "Выберите партнёра:",
        reply_markup=partners_keyboard(0),
    )


@dp.message(F.text == "🚗 Сделки")
async def deals_button(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "🚗 <b>СДЕЛКИ</b>\n\n"
        "Выберите сделку:",
        reply_markup=deals_keyboard(0),
    )


@dp.message(F.text == "📊 Статистика")
async def stats_button(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    await message.answer(
        build_stats_text()
    )


# =========================================================
# ПРОВЕРКА БАЗЫ
# =========================================================

@dp.callback_query(
    F.data == "check_database"
)
async def check_database(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    users = get_all_users()
    partners = get_partners()
    deals = get_deals()

    await callback.answer()

    await callback.message.edit_text(
        "🔎 <b>ПРОВЕРКА БАЗЫ</b>\n\n"
        f"👥 Пользователей: "
        f"<b>{len(users)}</b>\n"
        f"🤝 Партнёров: "
        f"<b>{len(partners)}</b>\n"
        f"🚗 Сделок: "
        f"<b>{len(deals)}</b>\n\n"
        "🟢 База отвечает.",
        reply_markup=inline_menu(
            [
                [
                    InlineKeyboardButton(
                        text="🔄 Обновить",
                        callback_data="check_database",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="admin_page_3",
                    )
                ],
            ]
        ),
    )


# =========================================================
# ВСЕ ПОЛЬЗОВАТЕЛИ
# =========================================================

@dp.callback_query(
    F.data == "all_users"
)
async def all_users(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    users = get_all_users()

    if not users:

        await callback.answer()

        await callback.message.edit_text(
            "📋 <b>ПОЛЬЗОВАТЕЛИ</b>\n\n"
            "Пользователей пока нет.",
            reply_markup=inline_menu(
                [
                    [
                        InlineKeyboardButton(
                            text="🔙 Назад",
                            callback_data="admin_page_3",
                        )
                    ]
                ]
            ),
        )

        return

    text = "📋 <b>ПОЛЬЗОВАТЕЛИ</b>\n\n"

    for user in users[:30]:

        telegram_id = user[0]
        name = user[1]
        balance = user[2]

        text += (
            f"👤 {safe(name)}\n"
            f"🆔 <code>{telegram_id}</code>\n"
            f"💰 {money(balance)}\n"
            "────────────\n"
        )

    if len(users) > 30:

        text += (
            f"\nПоказаны первые 30 "
            f"из {len(users)} пользователей."
        )

    await callback.answer()

    await callback.message.edit_text(
        text,
        reply_markup=inline_menu(
            [
                [
                    InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="admin_page_3",
                    )
                ]
            ]
        ),
    )


# =========================================================
# ДОБАВЛЕНИЕ ПАРТНЁРА
# =========================================================

@dp.callback_query(
    F.data == "add_partner_help"
)
async def add_partner_help(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    await callback.answer()

    await callback.message.edit_text(
        "➕ <b>ДОБАВЛЕНИЕ ПАРТНЁРА</b>\n\n"
        "Пользователь должен сначала открыть "
        "бота и отправить /start.\n\n"
        "После этого выполните:\n\n"
        "<code>/add_partner ID</code>\n\n"
        "Например:\n"
        "<code>/add_partner 123456789</code>",
        reply_markup=inline_menu(
            [
                [
                    InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="admin_page_2",
                    )
                ]
            ]
        ),
    )


@dp.message(
    Command("add_partner")
)
async def add_partner_command(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    parts = (
        message.text or ""
    ).split()

    if len(parts) != 2:

        await message.answer(
            "❌ <b>Использование:</b>\n\n"
            "<code>/add_partner ID</code>"
        )

        return

    try:

        partner_id = int(parts[1])

    except ValueError:

        await message.answer(
            "❌ ID должен быть числом."
        )

        return

    changed = add_partner(
        partner_id
    )

    if changed == 0:

        await message.answer(
            "❌ Пользователь не найден.\n\n"
            "Пусть сначала откроет бота "
            "и отправит /start."
        )

        return

    await message.answer(
        "✅ <b>ПАРТНЁР ДОБАВЛЕН</b>\n\n"
        f"🆔 ID: <code>{partner_id}</code>"
    )


# =========================================================
# УБРАТЬ ПАРТНЁРА
# =========================================================

@dp.callback_query(
    F.data == "remove_partner_help"
)
async def remove_partner_help(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    await callback.answer()

    await callback.message.edit_text(
        "➖ <b>УБРАТЬ ПАРТНЁРА</b>\n\n"
        "Откройте карточку партнёра "
        "и нажмите «Убрать из партнёров».\n\n"
        "История и сделки при этом сохранятся.",
        reply_markup=inline_menu(
            [
                [
                    InlineKeyboardButton(
                        text="👥 Партнёры",
                        callback_data="admin_partners",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="admin_page_2",
                    )
                ],
            ]
        ),
    )


@dp.callback_query(
    F.data.startswith("remove_partner:")
)
async def remove_partner_callback(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    try:

        partner_id = int(
            callback.data.split(":", 1)[1]
        )

    except (ValueError, AttributeError):

        await callback.answer(
            "Некорректный ID",
            show_alert=True,
        )

        return

    changed = remove_partner(
        partner_id
    )

    if not changed:

        await callback.answer(
            "Партнёр не найден",
            show_alert=True,
        )

        return

    await callback.answer(
        "Партнёр убран"
    )

    await show_partners(
        callback,
        0,
    )


# =========================================================
# НАЧИСЛЕНИЕ ИЗ КАРТОЧКИ
# =========================================================

@dp.callback_query(
    F.data.startswith("commission_partner:")
)
async def commission_partner(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    try:

        partner_id = int(
            callback.data.split(":", 1)[1]
        )

    except (ValueError, AttributeError):

        await callback.answer(
            "Некорректный ID",
            show_alert=True,
        )

        return

    await callback.answer()

    await callback.message.edit_text(
        "💰 <b>НАЧИСЛЕНИЕ КОМИССИИ</b>\n\n"
        f"Партнёр: <code>{partner_id}</code>\n\n"
        "Введите команду:\n\n"
        f"<code>/commission {partner_id} СУММА</code>\n\n"
        "Например:\n"
        f"<code>/commission {partner_id} 15000</code>",
        reply_markup=inline_menu(
            [
                [
                    InlineKeyboardButton(
                        text="🔙 К партнёру",
                        callback_data=(
                            f"partner_view:{partner_id}"
                        ),
                    )
                ]
            ]
        ),
    )


# =========================================================
# КОМАНДА КОМИССИИ
# =========================================================

@dp.callback_query(
    F.data == "commission_help"
)
async def commission_help(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    await callback.answer()

    await callback.message.edit_text(
        "💰 <b>НАЧИСЛЕНИЕ КОМИССИИ</b>\n\n"
        "Используйте:\n\n"
        "<code>/commission ID СУММА</code>\n\n"
        "Пример:\n"
        "<code>/commission 123456789 15000</code>",
        reply_markup=inline_menu(
            [
                [
                    InlineKeyboardButton(
                        text="👥 Партнёры",
                        callback_data="admin_partners",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="admin_page_2",
                    )
                ],
            ]
        ),
    )


@dp.message(
    Command("commission")
)
async def commission(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    parts = (
        message.text or ""
    ).split()

    if len(parts) != 3:

        await message.answer(
            "❌ <b>Использование:</b>\n\n"
            "<code>/commission ID СУММА</code>"
        )

        return

    try:

        partner_id = int(parts[1])
        amount = int(parts[2])

    except ValueError:

        await message.answer(
            "❌ ID и сумма должны быть числами."
        )

        return

    if amount <= 0:

        await message.answer(
            "❌ Сумма должна быть больше 0."
        )

        return

    partners = get_partners()

    exists = any(
        user[0] == partner_id
        for user in partners
    )

    if not exists:

        await message.answer(
            "❌ Этот пользователь не является партнёром."
        )

        return

    try:

        add_balance(
            partner_id,
            amount,
        )

    except Exception as e:

        logger.exception(
            "Ошибка начисления комиссии: %s",
            e,
        )

        await message.answer(
            "❌ Не удалось начислить комиссию."
        )

        return

    await message.answer(
        "✅ <b>КОМИССИЯ НАЧИСЛЕНА</b>\n\n"
        f"👤 Партнёр: <code>{partner_id}</code>\n"
        f"💰 Сумма: <b>{money(amount)}</b>"
    )

    # Уведомление партнёру
    try:

        new_balance = get_balance(
            partner_id
        )

        await bot.send_message(
            chat_id=partner_id,
            text=(
                "🎉 <b>Вам начислена комиссия!</b>\n\n"
                f"💰 Начислено: <b>{money(amount)}</b>\n"
                f"💵 Ваш баланс: "
                f"<b>{money(new_balance)}</b>"
            ),
        )

    except Exception as e:

        logger.warning(
            "Не удалось уведомить партнёра %s: %s",
            partner_id,
            e,
        )


# =========================================================
# ОБНУЛЕНИЕ БАЛАНСА
# =========================================================

@dp.callback_query(
    F.data.startswith("reset_partner:")
)
async def reset_partner(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    try:

        partner_id = int(
            callback.data.split(":", 1)[1]
        )

    except (ValueError, AttributeError):

        await callback.answer(
            "Некорректный ID",
            show_alert=True,
        )

        return

    try:

        set_balance(
            partner_id,
            0,
        )

    except Exception as e:

        logger.exception(
            "Ошибка обнуления баланса: %s",
            e,
        )

        await callback.answer(
            "Ошибка базы",
            show_alert=True,
        )

        return

    await callback.answer(
        "Баланс обнулён"
    )

    await render_partner_card(
        callback,
        partner_id,
    )


# =========================================================
# МЕНЮ БАЛАНСА
# =========================================================

@dp.callback_query(
    F.data == "balance_menu"
)
async def balance_menu(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    await callback.answer()

    await callback.message.edit_text(
        "🔄 <b>УПРАВЛЕНИЕ БАЛАНСОМ</b>\n\n"
        "Откройте раздел партнёров "
        "и выберите нужного человека.\n\n"
        "В карточке доступны:\n\n"
        "💰 Начислить\n"
        "🔄 Обнулить баланс",
        reply_markup=inline_menu(
            [
                [
                    InlineKeyboardButton(
                        text="👥 Партнёры",
                        callback_data="admin_partners",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="admin_page_2",
                    )
                ],
            ]
        ),
    )


# =========================================================
# RESETBALANCE
# =========================================================

@dp.message(
    Command("resetbalance")
)
async def resetbalance(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    parts = (
        message.text or ""
    ).split()

    if len(parts) != 2:

        await message.answer(
            "❌ <b>Использование:</b>\n\n"
            "<code>/resetbalance ID</code>"
        )

        return

    try:

        partner_id = int(parts[1])

    except ValueError:

        await message.answer(
            "❌ ID должен быть числом."
        )

        return

    set_balance(
        partner_id,
        0,
    )

    await message.answer(
        "✅ <b>Баланс обнулён.</b>\n\n"
        f"🆔 ID: <code>{partner_id}</code>"
    )


# =========================================================
# RESET ALL
# =========================================================

@dp.message(
    Command("resetall")
)
async def resetall(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    users = get_all_users()

    for user in users:

        set_balance(
            user[0],
            0,
        )

    await message.answer(
        "⚠️ <b>ВСЕ БАЛАНСЫ ОБНУЛЕНЫ</b>\n\n"
        f"Обработано пользователей: "
        f"<b>{len(users)}</b>"
    )


# =========================================================
# УСТАНОВИТЬ БАЛАНС
# =========================================================

@dp.message(
    Command("setbalance")
)
async def setbalance(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    parts = (
        message.text or ""
    ).split()

    if len(parts) != 3:

        await message.answer(
            "❌ <b>Использование:</b>\n\n"
            "<code>/setbalance ID СУММА</code>\n\n"
            "Пример:\n"
            "<code>/setbalance 123456789 50000</code>"
        )

        return

    try:

        partner_id = int(parts[1])
        amount = int(parts[2])

    except ValueError:

        await message.answer(
            "❌ ID и сумма должны быть числами."
        )

        return

    if amount < 0:

        await message.answer(
            "❌ Баланс не может быть отрицательным."
        )

        return

    users = get_all_users()

    exists = any(
        user[0] == partner_id
        for user in users
    )

    if not exists:

        await message.answer(
            "❌ Пользователь не найден."
        )

        return

    set_balance(
        partner_id,
        amount,
    )

    await message.answer(
        "✅ <b>БАЛАНС ИЗМЕНЁН</b>\n\n"
        f"🆔 ID: <code>{partner_id}</code>\n"
        f"💰 Новый баланс: "
        f"<b>{money(amount)}</b>"
    )


# =========================================================
# СОЗДАТЬ СДЕЛКУ
# =========================================================

@dp.callback_query(
    F.data == "create_deal_help"
)
async def create_deal_help(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    await callback.answer()

    await callback.message.edit_text(
        "🚗 <b>СОЗДАНИЕ СДЕЛКИ</b>\n\n"
        "Используйте:\n\n"
        "<code>/deal ID_клиента ID_партнёра</code>\n\n"
        "Пример:\n"
        "<code>/deal 123456789 987654321</code>",
        reply_markup=inline_menu(
            [
                [
                    InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="admin_page_3",
                    )
                ]
            ]
        ),
    )


@dp.message(
    Command("deal")
)
async def create_deal_command(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    parts = (
        message.text or ""
    ).split()

    if len(parts) != 3:

        await message.answer(
            "❌ <b>Использование:</b>\n\n"
            "<code>/deal ID_клиента ID_партнёра</code>"
        )

        return

    try:

        client_id = int(parts[1])
        partner_id = int(parts[2])

    except ValueError:

        await message.answer(
            "❌ ID должны быть числами."
        )

        return

    partners = get_partners()

    partner_exists = any(
        user[0] == partner_id
        for user in partners
    )

    if not partner_exists:

        await message.answer(
            "❌ Указанный пользователь "
            "не является партнёром."
        )

        return

    users = get_all_users()

    client_exists = any(
        user[0] == client_id
        for user in users
    )

    if not client_exists:

        await message.answer(
            "❌ Клиент не найден в базе.\n\n"
            "Пусть сначала откроет бота "
            "и отправит /start."
        )

        return

    try:

        deal_id = create_deal(
            client_id,
            partner_id,
        )

    except Exception as e:

        logger.exception(
            "Ошибка создания сделки: %s",
            e,
        )

        await message.answer(
            "❌ Не удалось создать сделку."
        )

        return

    await message.answer(
        "🚗 <b>СДЕЛКА СОЗДАНА</b>\n\n"
        f"🔢 Номер: <b>#{deal_id}</b>\n"
        f"👤 Клиент: <code>{client_id}</code>\n"
        f"🤝 Партнёр: <code>{partner_id}</code>\n"
        "📌 Статус: <b>Новая</b>"
    )


# =========================================================
# DONE HELP
# =========================================================

@dp.callback_query(
    F.data.startswith("done_help:")
)
async def done_help(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    try:

        deal_id = int(
            callback.data.split(":", 1)[1]
        )

    except (ValueError, AttributeError):

        await callback.answer(
            "Некорректный ID",
            show_alert=True,
        )

        return

    await callback.answer()

    await callback.message.edit_text(
        "✅ <b>ЗАВЕРШЕНИЕ СДЕЛКИ</b>\n\n"
        f"Сделка: <b>#{deal_id}</b>\n\n"
        "Введите:\n\n"
        f"<code>/done {deal_id} СУММА</code>\n\n"
        "Например:\n"
        f"<code>/done {deal_id} 15000</code>",
        reply_markup=inline_menu(
            [
                [
                    InlineKeyboardButton(
                        text="🔙 К сделке",
                        callback_data=(
                            f"deal_view:{deal_id}"
                        ),
                    )
                ]
            ]
        ),
    )


# =========================================================
# ЗАВЕРШИТЬ СДЕЛКУ
# =========================================================

@dp.message(
    Command("done")
)
async def done_deal(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    parts = (
        message.text or ""
    ).split()

    if len(parts) != 3:

        await message.answer(
            "❌ <b>Использование:</b>\n\n"
            "<code>/done ID_сделки СУММА</code>"
        )

        return

    try:

        deal_id = int(parts[1])
        amount = int(parts[2])

    except ValueError:

        await message.answer(
            "❌ ID и сумма должны быть числами."
        )

        return

    if amount <= 0:

        await message.answer(
            "❌ Сумма должна быть больше 0."
        )

        return

    deals = get_deals()

    selected_deal = next(
        (
            deal
            for deal in deals
            if deal[0] == deal_id
        ),
        None,
    )

    if not selected_deal:

        await message.answer(
            "❌ Сделка не найдена."
        )

        return

    if selected_deal[3] == "Завершена":

        await message.answer(
            "⚠️ <b>Сделка уже завершена.</b>\n\n"
            "Повторное начисление запрещено."
        )

        return

    partner_id = finish_deal(
        deal_id,
        amount,
    )

    if not partner_id:

        await message.answer(
            "❌ Не удалось завершить сделку."
        )

        return

    await message.answer(
        "✅ <b>СДЕЛКА ЗАВЕРШЕНА</b>\n\n"
        f"🔢 Сделка: <b>#{deal_id}</b>\n"
        f"💰 Начислено: <b>{money(amount)}</b>\n"
        f"🤝 Партнёр: <code>{partner_id}</code>"
    )

    # -----------------------------------------------------
    # УВЕДОМЛЕНИЕ ПАРТНЁРУ
    # -----------------------------------------------------

    try:

        new_balance = get_balance(
            partner_id
        )

        await bot.send_message(
            chat_id=partner_id,
            text=(
                "🎉 <b>Сделка завершена!</b>\n\n"
                f"🚗 Сделка: <b>#{deal_id}</b>\n"
                f"💰 Начислено: "
                f"<b>{money(amount)}</b>\n"
                f"💵 Ваш баланс: "
                f"<b>{money(new_balance)}</b>"
            ),
        )

    except Exception as e:

        logger.warning(
            "Не удалось уведомить партнёра %s: %s",
            partner_id,
            e,
        )


# =========================================================
# DELETE USER HELP
# =========================================================

@dp.callback_query(
    F.data == "delete_user_help"
)
async def delete_user_help(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await deny_callback(callback)
        return

    await callback.answer()

    await callback.message.edit_text(
        "🗑 <b>УДАЛЕНИЕ ПОЛЬЗОВАТЕЛЯ</b>\n\n"
        "Используйте:\n\n"
        "<code>/delete_partner ID</code>\n\n"
        "⚠️ Пользователь будет удалён "
        "из таблицы пользователей.\n\n"
        "История и сделки зависят от настроек "
        "внешних ключей базы.",
        reply_markup=inline_menu(
            [
                [
                    InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="admin_page_3",
                    )
                ]
            ]
        ),
    )


@dp.message(
    Command("delete_partner")
)
async def delete_partner_command(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    parts = (
        message.text or ""
    ).split()

    if len(parts) != 2:

        await message.answer(
            "❌ <b>Использование:</b>\n\n"
            "<code>/delete_partner ID</code>"
        )

        return

    try:

        user_id = int(parts[1])

    except ValueError:

        await message.answer(
            "❌ ID должен быть числом."
        )

        return

    deleted = delete_user(
        user_id
    )

    if deleted:

        await message.answer(
            "🗑 <b>ПОЛЬЗОВАТЕЛЬ УДАЛЁН</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>"
        )

    else:

        await message.answer(
            "❌ Пользователь не найден."
        )


# =========================================================
# /PARTNERS
# =========================================================

@dp.message(
    Command("partners")
)
async def partners_command(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    users = get_partners()

    if not users:

        await message.answer(
            "👥 Партнёров пока нет."
        )

        return

    text = "👥 <b>ПАРТНЁРЫ</b>\n\n"

    for user in users:

        telegram_id = user[0]
        username = user[1]
        name = user[2]
        balance = user[3]

        username_text = (
            f"@{safe(username)}"
            if username
            else "не указан"
        )

        text += (
            f"👤 <b>{safe(name)}</b>\n"
            f"🆔 <code>{telegram_id}</code>\n"
            f"📱 {username_text}\n"
            f"💰 {money(balance)}\n"
            "────────────\n"
        )

    await message.answer(text)


# =========================================================
# /CHECKDB
# =========================================================

@dp.message(
    Command("checkdb")
)
async def checkdb(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    users = get_all_users()
    partners = get_partners()
    deals = get_deals()

    await message.answer(
        "🔎 <b>БАЗА</b>\n\n"
        f"👥 Пользователей: "
        f"<b>{len(users)}</b>\n"
        f"🤝 Партнёров: "
        f"<b>{len(partners)}</b>\n"
        f"🚗 Сделок: "
        f"<b>{len(deals)}</b>"
    )


# =========================================================
# /STATS
# =========================================================

@dp.message(
    Command("stats")
)
async def stats_command(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    await message.answer(
        build_stats_text()
    )


# =========================================================
# NOOP
# =========================================================

@dp.callback_query(
    F.data == "noop"
)
async def noop(
    callback: CallbackQuery,
):

    await callback.answer()


# =========================================================
# ОБРАБОТКА ОШИБОК
# =========================================================

@dp.error()
async def global_error_handler(
    event,
):

    logger.exception(
        "Необработанная ошибка Telegram/update: %s",
        event.exception,
    )


# =========================================================
# НЕИЗВЕСТНЫЕ СООБЩЕНИЯ
# =========================================================

@dp.message()
async def other_message(
    message: Message,
):

    if is_admin(message.from_user.id):

        await message.answer(
            "👑 <b>АДМИН-ПАНЕЛЬ</b>\n\n"
            "Используйте кнопки меню ниже.",
            reply_markup=admin_reply_kb,
        )

    else:

        await message.answer(
            "Используйте кнопки меню ниже.",
            reply_markup=partner_kb,
        )


# =========================================================
# ЗАПУСК
# =========================================================

async def main():

    logger.info("Бот запускается...")

    try:

        me = await bot.get_me()

        logger.info(
            "Бот: @%s | ID: %s",
            me.username,
            me.id,
        )

        print("Бот запущен...")

        await dp.start_polling(
            bot
        )

    finally:

        await bot.session.close()

        logger.info(
            "Соединение с Telegram закрыто."
        )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        logger.info(
            "Бот остановлен пользователем."
        )
