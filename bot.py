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
    get_user,
    get_balance,
    get_history,
    get_clients,
    delete_user,
    get_partners,
    get_all_users,
    add_partner,
    remove_partner,
    add_balance,
    set_balance,
    create_deal,
    get_deals,
    finish_deal,
)


# =========================================================
# НАСТРОЙКИ
# =========================================================

socket.setdefaulttimeout(30)


# =========================================================
# ИНИЦИАЛИЗАЦИЯ
# =========================================================

init_db()

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
# START
# =========================================================

@dp.message(CommandStart())
async def start(message: Message):

    user = message.from_user

    if user is None:
        return

    args = message.text.split()

    invited_by = None

    # -----------------------------------------------------
    # /start ID
    # -----------------------------------------------------

    if len(args) > 1:

        try:
            invited_by = int(args[1])

        except ValueError:
            invited_by = None

    # -----------------------------------------------------
    # Нельзя пригласить самого себя
    # -----------------------------------------------------

    if invited_by == user.id:
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
    # Админ
    # -----------------------------------------------------

    if is_admin(user.id):

        await message.answer(
            "👑 Добро пожаловать, администратор!\n\n"
            "Админ-панель доступна ниже.\n\n"
            "Используйте /admin для полного списка команд.",
            reply_markup=admin_kb,
        )

        return

    # -----------------------------------------------------
    # Обычный пользователь
    # -----------------------------------------------------

    await message.answer(
        "🚗 Добро пожаловать в NY Партнёры!\n\n"
        "Здесь можно получать комиссию "
        "за клиентов на подбор автомобилей.\n\n"
        "Используйте кнопки меню ниже.",
        reply_markup=partner_kb,
    )


# =========================================================
# МОЯ ССЫЛКА
# =========================================================

@dp.message(F.text == "🔗 Моя ссылка")
async def my_link(message: Message):

    user = message.from_user

    if user is None:
        return

    me = await bot.get_me()

    if not me.username:

        await message.answer(
            "❌ Не удалось получить username бота."
        )

        return

    link = f"https://t.me/{me.username}?start={user.id}"

    await message.answer(
        "🔗 Ваша партнёрская ссылка:\n\n"
        f"{link}\n\n"
        "Отправляйте её клиентам.\n"
        "Когда клиент перейдёт по ссылке, "
        "он будет привязан к вам."
    )


# =========================================================
# МОИ КЛИЕНТЫ
# =========================================================

@dp.message(F.text == "👥 Мои клиенты")
async def clients(message: Message):

    user = message.from_user

    if user is None:
        return

    users = get_clients(user.id)

    if not users:

        await message.answer(
            "👥 У вас пока нет клиентов.\n\n"
            "Отправьте клиенту вашу партнёрскую ссылку."
        )

        return

    text = "👥 ВАШИ КЛИЕНТЫ\n\n"

    for client in users:

        telegram_id = client[0]
        username = client[1]
        name = client[2]

        if username:

            text += (
                f"👤 @{username}\n"
                f"🆔 ID: {telegram_id}\n"
                f"📛 Имя: {name}\n"
                f"────────────────\n"
            )

        else:

            text += (
                f"👤 {name}\n"
                f"🆔 ID: {telegram_id}\n"
                f"────────────────\n"
            )

    await message.answer(text)


# =========================================================
# МОЙ БАЛАНС
# =========================================================

@dp.message(F.text == "💰 Мой баланс")
async def my_balance(message: Message):

    user = message.from_user

    if user is None:
        return

    balance = get_balance(user.id)

    await message.answer(
        "💰 ВАШ БАЛАНС\n\n"
        f"💵 {balance:,} ₽".replace(",", " ")
    )


# =========================================================
# ИСТОРИЯ
# =========================================================

@dp.message(F.text == "📜 История")
async def history(message: Message):

    user = message.from_user

    if user is None:
        return

    data = get_history(user.id)

    if not data:

        await message.answer(
            "📜 История пока пустая.\n\n"
            "Здесь будут отображаться "
            "начисления по завершённым сделкам."
        )

        return

    text = "📜 ИСТОРИЯ НАЧИСЛЕНИЙ\n\n"

    for amount, deal_id, date in data:

        formatted_amount = f"{amount:,}".replace(",", " ")

        text += (
            f"🚗 Сделка №{deal_id}\n"
            f"💰 +{formatted_amount} ₽\n"
            f"📅 {date}\n"
            f"────────────────\n"
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

        "👥 ПАРТНЁРЫ\n"
        "/partners — список партнёров\n"
        "/add_partner ID — назначить партнёра\n"
        "/remove_partner ID — убрать статус партнёра\n"
        "/delete_partner ID — удалить пользователя\n\n"

        "💰 ФИНАНСЫ\n"
        "/commission ID СУММА — начислить комиссию\n"
        "/resetbalance ID — обнулить баланс\n"
        "/resetall — обнулить все балансы\n\n"

        "🚗 СДЕЛКИ\n"
        "/deal ID_клиента ID_партнёра — создать сделку\n"
        "/deals — список сделок\n"
        "/done ID_сделки СУММА — завершить сделку\n\n"

        "📊 СИСТЕМА\n"
        "/stats — статистика\n"
        "/checkdb — количество пользователей",
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
            "👥 Партнёров пока нет.\n\n"
            "Чтобы назначить партнёра:\n"
            "/add_partner ID"
        )

        return

    text = "👥 СПИСОК ПАРТНЁРОВ\n\n"

    for user in users:

        telegram_id = user[0]
        username = user[1]
        name = user[2]
        balance = user[3]

        formatted_balance = f"{balance:,}".replace(",", " ")

        if username:
            username_text = f"@{username}"
        else:
            username_text = "не указан"

        text += (
            f"👤 {name}\n"
            f"🆔 ID: {telegram_id}\n"
            f"📱 {username_text}\n"
            f"💰 Баланс: {formatted_balance} ₽\n"
            f"────────────────\n"
        )

    await message.answer(text)


# =========================================================
# КНОПКА ПАРТНЁРЫ
# =========================================================

@dp.message(F.text == "👥 Партнёры")
async def partners_button(message: Message):

    await partners(message)


# =========================================================
# ДОБАВИТЬ ПАРТНЁРА
# =========================================================

@dp.message(Command("add_partner"))
async def add_partner_cmd(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return

    args = message.text.split()

    if len(args) != 2:

        await message.answer(
            "❌ Неверный формат.\n\n"
            "Использование:\n"
            "/add_partner ID\n\n"
            "Пример:\n"
            "/add_partner 123456789"
        )

        return

    try:

        partner_id = int(args[1])

    except ValueError:

        await message.answer(
            "❌ ID должен быть числом."
        )

        return

    user = get_user(partner_id)

    if not user:

        await message.answer(
            "❌ Пользователь с таким ID ещё не запускал бота.\n\n"
            "Сначала пользователь должен открыть бота "
            "и нажать /start."
        )

        return

    changed = add_partner(partner_id)

    if not changed:

        await message.answer(
            "⚠️ Пользователь уже является партнёром."
        )

        return

    await message.answer(
        "✅ ПАРТНЁР ДОБАВЛЕН\n\n"
        f"🆔 ID: {partner_id}\n"
        f"👤 Имя: {user[2]}\n\n"
        "Теперь пользователь является партнёром."
    )

    try:

        await bot.send_message(
            chat_id=partner_id,
            text=(
                "🎉 Поздравляем!\n\n"
                "Вы стали партнёром NY Партнёры.\n\n"
                "Откройте меню бота и нажмите "
                "«🔗 Моя ссылка», чтобы получить "
                "свою партнёрскую ссылку."
            ),
        )

    except Exception:

        pass


# =========================================================
# УБРАТЬ ПАРТНЁРА
# =========================================================

@dp.message(Command("remove_partner"))
async def remove_partner_cmd(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return

    args = message.text.split()

    if len(args) != 2:

        await message.answer(
            "❌ Неверный формат.\n\n"
            "Использование:\n"
            "/remove_partner ID"
        )

        return

    try:

        partner_id = int(args[1])

    except ValueError:

        await message.answer(
            "❌ ID должен быть числом."
        )

        return

    changed = remove_partner(partner_id)

    if not changed:

        await message.answer(
            "❌ Пользователь не найден."
        )

        return

    await message.answer(
        "✅ Статус партнёра снят.\n\n"
        f"🆔 ID: {partner_id}"
    )


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
        f"👥 Пользователей: {len(users)}"
    )


# =========================================================
# НАЧИСЛЕНИЕ КОМИССИИ
#
# /commission ID СУММА
# =========================================================

@dp.message(Command("commission"))
async def commission(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return

    args = message.text.split()

    if len(args) != 3:

        await message.answer(
            "❌ Неверный формат.\n\n"
            "Использование:\n"
            "/commission ID СУММА\n\n"
            "Пример:\n"
            "/commission 123456789 15000"
        )

        return

    try:

        partner_id = int(args[1])
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

    user = get_user(partner_id)

    if not user:

        await message.answer(
            "❌ Пользователь не найден."
        )

        return

    add_balance(
        partner_id,
        amount
    )

    balance = get_balance(partner_id)

    await message.answer(
        "✅ КОМИССИЯ НАЧИСЛЕНА\n\n"
        f"👤 Партнёр: {partner_id}\n"
        f"💰 Начислено: {amount:,} ₽\n"
        f"💵 Новый баланс: {balance:,} ₽".replace(",", " ")
    )

    try:

        await bot.send_message(
            chat_id=partner_id,
            text=(
                "🎉 Вам начислена комиссия!\n\n"
                f"💰 Сумма: {amount:,} ₽\n"
                f"💵 Баланс: {balance:,} ₽"
            ).replace(",", " "),
        )

    except Exception:

        pass


# =========================================================
# ОБНУЛИТЬ БАЛАНС
# =========================================================

@dp.message(Command("resetbalance"))
async def resetbalance(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return

    args = message.text.split()

    if len(args) != 2:

        await message.answer(
            "❌ Использование:\n"
            "/resetbalance ID"
        )

        return

    try:

        partner_id = int(args[1])

    except ValueError:

        await message.answer(
            "❌ ID должен быть числом."
        )

        return

    user = get_user(partner_id)

    if not user:

        await message.answer(
            "❌ Пользователь не найден."
        )

        return

    set_balance(
        partner_id,
        0
    )

    await message.answer(
        "✅ БАЛАНС ОБНУЛЁН\n\n"
        f"👤 Партнёр: {partner_id}\n"
        "💰 Баланс: 0 ₽"
    )


# =========================================================
# ОБНУЛИТЬ ВСЕ БАЛАНСЫ
# =========================================================

@dp.message(Command("resetall"))
async def resetall(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return

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
        "⚠️ ВСЕ БАЛАНСЫ ОБНУЛЕНЫ\n\n"
        f"👥 Обработано пользователей: {count}"
    )


# =========================================================
# УДАЛЕНИЕ ПОЛЬЗОВАТЕЛЯ / ПАРТНЁРА
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
            "❌ Использование:\n"
            "/delete_partner ID"
        )

        return

    try:

        user_id = int(args[1])

    except ValueError:

        await message.answer(
            "❌ ID должен быть числом."
        )

        return

    user = get_user(user_id)

    if not user:

        await message.answer(
            "❌ Пользователь не найден."
        )

        return

    delete_user(user_id)

    await message.answer(
        "🗑 ПОЛЬЗОВАТЕЛЬ УДАЛЁН\n\n"
        f"🆔 ID: {user_id}\n"
        f"👤 Имя: {user[2]}"
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

    args = message.text.split()

    if len(args) != 3:

        await message.answer(
            "❌ Неверный формат.\n\n"
            "Использование:\n"
            "/deal ID_клиента ID_партнёра\n\n"
            "Пример:\n"
            "/deal 123456789 987654321"
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

    client = get_user(client_id)

    if not client:

        await message.answer(
            "❌ Клиент не найден в базе."
        )

        return

    partner = get_user(partner_id)

    if not partner:

        await message.answer(
            "❌ Партнёр не найден в базе."
        )

        return

    if partner[5] != 1:

        await message.answer(
            "⚠️ Этот пользователь не является партнёром.\n\n"
            "Сначала используйте:\n"
            f"/add_partner {partner_id}"
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
# =========================================================

@dp.message(Command("deals"))
async def deals(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return

    data = get_deals()

    if not data:

        await message.answer(
            "🚗 Сделок пока нет."
        )

        return

    text = "🚗 СПИСОК СДЕЛОК\n\n"

    for deal in data:

        deal_id = deal[0]
        client_id = deal[1]
        partner_id = deal[2]
        status = deal[3]
        commission = deal[4]

        formatted_commission = (
            f"{commission:,}".replace(",", " ")
        )

        text += (
            f"🔢 Сделка #{deal_id}\n"
            f"👤 Клиент: {client_id}\n"
            f"🤝 Партнёр: {partner_id}\n"
            f"📌 Статус: {status}\n"
            f"💰 Комиссия: {formatted_commission} ₽\n"
            f"────────────────\n"
        )

    await message.answer(text)


# =========================================================
# КНОПКА СДЕЛКИ
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

    balance = get_balance(partner_id)

    await message.answer(
        "✅ СДЕЛКА ЗАВЕРШЕНА\n\n"
        f"🔢 Сделка: #{deal_id}\n"
        f"💰 Начислено: {amount:,} ₽\n"
        f"💵 Баланс партнёра: {balance:,} ₽\n"
        f"🤝 Партнёр: {partner_id}".replace(",", " ")
    )

    try:

        await bot.send_message(
            chat_id=partner_id,
            text=(
                "🎉 ПОЗДРАВЛЯЕМ!\n\n"
                f"Ваша сделка #{deal_id} завершена.\n\n"
                f"💰 Начислено: {amount:,} ₽\n"
                f"💵 Ваш баланс: {balance:,} ₽"
            ).replace(",", " "),
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
    partners_data = get_partners()
    deals_data = get_deals()

    total_balance = 0

    for user in users:

        try:
            total_balance += int(user[2] or 0)

        except (ValueError, TypeError):
            pass

    formatted_balance = (
        f"{total_balance:,}".replace(",", " ")
    )

    await message.answer(
        "📊 СТАТИСТИКА\n\n"
        f"👥 Пользователей: {len(users)}\n"
        f"🤝 Партнёров: {len(partners_data)}\n"
        f"🚗 Сделок: {len(deals_data)}\n"
        f"💰 Общий баланс: {formatted_balance} ₽"
    )


# =========================================================
# КНОПКА СТАТИСТИКА
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
# START
# =========================================================

if __name__ == "__main__":

    asyncio.run(main())
