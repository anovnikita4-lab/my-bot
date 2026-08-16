import asyncio
import socket

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
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
)


# =========================================================
# НАСТРОЙКИ
# =========================================================

socket.setdefaulttimeout(30)


# =========================================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ
# =========================================================

init_db()


# =========================================================
# TELEGRAM
# =========================================================

bot = Bot(token=TOKEN)

dp = Dispatcher()


# =========================================================
# ПРОВЕРКА АДМИНА
# =========================================================

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# =========================================================
# КЛАВИАТУРА ПАРТНЁРА
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

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="👥 Партнёры")
        ],
        [
            KeyboardButton(text="🚗 Сделки")
        ],
        [
            KeyboardButton(text="📊 Статистика")
        ],
    ],
    resize_keyboard=True,
)


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start(message: Message):

    user = message.from_user

    if user is None:
        return

    # -----------------------------------------------------
    # Получаем аргументы /start
    #
    # Обычный вход:
    # /start
    #
    # Переход по партнёрской ссылке:
    # /start 123456789
    # -----------------------------------------------------

    args = message.text.split()

    invited_by = None

    if len(args) > 1:

        try:
            invited_by = int(args[1])

        except ValueError:
            invited_by = None

    # -----------------------------------------------------
    # Добавляем пользователя
    # -----------------------------------------------------

    add_user(
        telegram_id=user.id,
        username=user.username,
        full_name=user.full_name,
        invited_by=invited_by,
    )

    # -----------------------------------------------------
    # Ответ пользователю
    # -----------------------------------------------------

    await message.answer(
        "🚗 Добро пожаловать в NY Партнёры!\n\n"
        "Здесь можно получать комиссию "
        "за клиентов на подбор автомобилей.",
        reply_markup=partner_kb,
    )


# =========================================================
# МОЯ ПАРТНЁРСКАЯ ССЫЛКА
# =========================================================

@dp.message(F.text == "🔗 Моя ссылка")
async def my_link(message: Message):

    me = await bot.get_me()

    link = (
        f"https://t.me/"
        f"{me.username}"
        f"?start={message.from_user.id}"
    )

    await message.answer(
        "🔗 Ваша партнёрская ссылка:\n\n"
        f"{link}\n\n"
        "Отправляйте её клиентам."
    )


# =========================================================
# МОИ КЛИЕНТЫ
# =========================================================

@dp.message(F.text == "👥 Мои клиенты")
async def clients(message: Message):

    users = get_clients(
        message.from_user.id
    )

    if not users:

        await message.answer(
            "👥 У вас пока нет клиентов."
        )

        return

    text = "👥 Ваши клиенты:\n\n"

    for user in users:

        telegram_id = user[0]
        username = user[1]
        name = user[2]

        if username:

            text += (
                f"👤 @{username}\n"
                f"🆔 ID: {telegram_id}\n\n"
            )

        else:

            text += (
                f"👤 {name}\n"
                f"🆔 ID: {telegram_id}\n\n"
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
        "💰 Ваш баланс:\n\n"
        f"{balance} ₽"
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
            "📜 История пока пустая."
        )

        return

    text = "📜 История начислений:\n\n"

    for amount, deal_id, date in data:

        text += (
            f"🚗 Сделка №{deal_id}\n"
            f"💰 +{amount} ₽\n"
            f"📅 {date}\n\n"
        )

    await message.answer(text)


# =========================================================
# АДМИН-ПАНЕЛЬ
# =========================================================

@dp.message(Command("admin"))
async def admin_panel(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return

    await message.answer(
        "👑 АДМИН-ПАНЕЛЬ\n\n"

        "👥 /partners — список партнёров\n"
        "🔎 /checkdb — количество пользователей\n\n"

        "💰 /commission ID СУММА — начислить комиссию\n"
        "🔄 /resetbalance ID — обнулить баланс\n"
        "⚠️ /resetall — обнулить все балансы\n\n"

        "🗑 /delete_partner ID — удалить партнёра\n\n"

        "🚗 /deal ID_клиента ID_партнёра — создать сделку\n"
        "📋 /deals — список сделок\n"
        "✅ /done ID_сделки СУММА — завершить сделку",

        reply_markup=admin_kb,
    )


# =========================================================
# СПИСОК ПАРТНЁРОВ
# =========================================================

@dp.message(Command("partners"))
async def partners(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return

    users = get_partners()

    if not users:

        await message.answer(
            "👥 Партнёров пока нет."
        )

        return

    text = "👥 СПИСОК ПАРТНЁРОВ\n\n"

    for user in users:

        telegram_id = user[0]
        username = user[1]
        name = user[2]
        balance = user[3]

        if username:
            username_text = f"@{username}"
        else:
            username_text = "не указан"

        text += (
            f"👤 {name}\n"
            f"🆔 ID: {telegram_id}\n"
            f"📱 {username_text}\n"
            f"💰 Баланс: {balance} ₽\n"
            f"────────────────\n"
        )

    await message.answer(text)


# =========================================================
# КНОПКА "ПАРТНЁРЫ"
# =========================================================

@dp.message(F.text == "👥 Партнёры")
async def partners_button(message: Message):

    await partners(message)


# =========================================================
# ПРОВЕРКА БАЗЫ
# =========================================================

@dp.message(Command("checkdb"))
async def checkdb(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return

    users = get_all_users()

    await message.answer(
        "🗄 ПРОВЕРКА БАЗЫ\n\n"
        f"👥 Пользователей в базе: {len(users)}"
    )


# =========================================================
# НАЧИСЛЕНИЕ КОМИССИИ
#
# /commission ID СУММА
#
# Пример:
# /commission 1877434604 15000
# =========================================================

@dp.message(Command("commission"))
async def commission(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return

    # Импорт здесь специально.
    # Если функция есть в database.py,
    # бот сможет ей пользоваться.

    from database import add_balance

    parts = message.text.split()

    if len(parts) != 3:

        await message.answer(
            "❌ Неверный формат.\n\n"
            "Использование:\n"
            "/commission ID СУММА\n\n"
            "Пример:\n"
            "/commission 1877434604 15000"
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

    add_balance(
        partner_id,
        amount
    )

    await message.answer(
        "✅ Комиссия начислена!\n\n"
        f"👤 Партнёр: {partner_id}\n"
        f"💰 Сумма: {amount} ₽"
    )

    # -----------------------------------------------------
    # Уведомляем партнёра
    # -----------------------------------------------------

    try:

        await bot.send_message(
            chat_id=partner_id,
            text=(
                "🎉 Вам начислена комиссия!\n\n"
                f"💰 Сумма: {amount} ₽"
            ),
        )

    except Exception:

        pass


# =========================================================
# ОБНУЛИТЬ БАЛАНС ПАРТНЁРА
#
# /resetbalance ID
# =========================================================

@dp.message(Command("resetbalance"))
async def resetbalance(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return

    from database import set_balance

    parts = message.text.split()

    if len(parts) != 2:

        await message.answer(
            "❌ Неверный формат.\n\n"
            "Использование:\n"
            "/resetbalance ID"
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
        0
    )

    await message.answer(
        "✅ Баланс обнулён.\n\n"
        f"👤 Партнёр: {partner_id}\n"
        "💰 Баланс: 0 ₽"
    )


# =========================================================
# ОБНУЛИТЬ ВСЕ БАЛАНСЫ
#
# /resetall
# =========================================================

@dp.message(Command("resetall"))
async def resetall(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return

    from database import set_balance

    users = get_all_users()

    count = 0

    for user in users:

        telegram_id = user[0]

        set_balance(
            telegram_id,
            0
        )

        count += 1

    await message.answer(
        "⚠️ Все балансы обнулены.\n\n"
        f"Обработано пользователей: {count}"
    )


# =========================================================
# УДАЛЕНИЕ ПАРТНЁРА
#
# /delete_partner ID
# =========================================================

@dp.message(Command("delete_partner"))
async def delete_partner(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return

    args = message.text.split()

    if len(args) != 2:

        await message.answer(
            "❌ Укажите ID партнёра.\n\n"
            "Пример:\n"
            "/delete_partner 1877434604"
        )

        return

    try:

        user_id = int(args[1])

    except ValueError:

        await message.answer(
            "❌ ID должен быть числом."
        )

        return

    # -----------------------------------------------------
    # Проверяем, существует ли пользователь
    # -----------------------------------------------------

    users = get_all_users()

    exists = False

    for user in users:

        if user[0] == user_id:

            exists = True
            break

    if not exists:

        await message.answer(
            "❌ Партнёр с таким ID не найден."
        )

        return

    # -----------------------------------------------------
    # Удаляем
    # -----------------------------------------------------

    delete_user(user_id)

    await message.answer(
        "🗑 Партнёр удалён.\n\n"
        f"🆔 ID: {user_id}"
    )


# =========================================================
# СОЗДАТЬ СДЕЛКУ
#
# /deal ID_клиента ID_партнёра
# =========================================================

@dp.message(Command("deal"))
async def create_deal_cmd(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return

    from database import create_deal

    args = message.text.split()

    if len(args) != 3:

        await message.answer(
            "❌ Неверный формат.\n\n"
            "Использование:\n"
            "/deal ID_клиента ID_партнёра\n\n"
            "Пример:\n"
            "/deal 123456789 1877434604"
        )

        return

    try:

        client_id = int(args[1])
        partner_id = int(args[2])

    except ValueError:

        await message.answer(
            "❌ ID должны быть числами."
        )

        return

    deal_id = create_deal(
        client_id,
        partner_id
    )

    await message.answer(
        "🚗 СДЕЛКА СОЗДАНА\n\n"
        f"🔢 Сделка: #{deal_id}\n"
        f"👤 Клиент: {client_id}\n"
        f"🤝 Партнёр: {partner_id}\n"
        "📌 Статус: Новая"
    )


# =========================================================
# СПИСОК СДЕЛОК
#
# /deals
# =========================================================

@dp.message(Command("deals"))
async def deals(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return

    from database import get_deals

    data = get_deals()

    if not data:

        await message.answer(
            "🚗 Сделок пока нет."
        )

        return

    text = "🚗 СПИСОК СДЕЛОК\n\n"

    for deal in data:

        deal_id = deal[0]
        client = deal[1]
        partner = deal[2]
        status = deal[3]
        money = deal[4]

        text += (
            f"🔢 #{deal_id}\n"
            f"👤 Клиент: {client}\n"
            f"🤝 Партнёр: {partner}\n"
            f"📌 Статус: {status}\n"
            f"💰 Комиссия: {money} ₽\n"
            f"────────────────\n"
        )

    await message.answer(text)


# =========================================================
# КНОПКА "СДЕЛКИ"
# =========================================================

@dp.message(F.text == "🚗 Сделки")
async def deals_button(message: Message):

    await deals(message)


# =========================================================
# ЗАВЕРШИТЬ СДЕЛКУ
#
# /done ID_сделки СУММА
# =========================================================

@dp.message(Command("done"))
async def done_deal(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return

    from database import finish_deal

    args = message.text.split()

    if len(args) != 3:

        await message.answer(
            "❌ Неверный формат.\n\n"
            "Использование:\n"
            "/done ID_сделки СУММА\n\n"
            "Пример:\n"
            "/done 1 15000"
        )

        return

    try:

        deal_id = int(args[1])
        amount = int(args[2])

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

    partner_id = finish_deal(
        deal_id,
        amount
    )

    if not partner_id:

        await message.answer(
            "❌ Сделка не найдена."
        )

        return

    await message.answer(
        "✅ СДЕЛКА ЗАВЕРШЕНА\n\n"
        f"🔢 Сделка: #{deal_id}\n"
        f"💰 Начислено: {amount} ₽\n"
        f"🤝 Партнёр: {partner_id}"
    )

    # -----------------------------------------------------
    # Уведомление партнёра
    # -----------------------------------------------------

    try:

        await bot.send_message(
            chat_id=partner_id,
            text=(
                "🎉 Поздравляем!\n\n"
                f"Ваша сделка #{deal_id} завершена.\n"
                f"💰 Начислено: {amount} ₽"
            ),
        )

    except Exception:

        pass


# =========================================================
# СТАТИСТИКА
# =========================================================

@dp.message(Command("stats"))
async def stats(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return

    users = get_all_users()

    try:

        from database import get_deals

        deals_data = get_deals()

        deals_count = len(deals_data)

    except Exception:

        deals_count = 0

    total_balance = 0

    for user in users:

        try:

            total_balance += int(user[2] or 0)

        except Exception:

            pass

    await message.answer(
        "📊 СТАТИСТИКА\n\n"
        f"👥 Пользователей: {len(users)}\n"
        f"🚗 Сделок: {deals_count}\n"
        f"💰 Балансы: {total_balance} ₽"
    )


# =========================================================
# КНОПКА "СТАТИСТИКА"
# =========================================================

@dp.message(F.text == "📊 Статистика")
async def stats_button(message: Message):

    await stats(message)


# =========================================================
# НЕИЗВЕСТНЫЕ СООБЩЕНИЯ
# =========================================================

@dp.message()
async def other_message(message: Message):

    if is_admin(message.from_user.id):

        await message.answer(
            "👑 Вы находитесь в админ-панели.\n\n"
            "Используйте /admin для списка команд.",
            reply_markup=admin_kb,
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

    print("Бот запущен...")

    await dp.start_polling(bot)


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    asyncio.run(main())
