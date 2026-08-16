import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton
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
)


# =========================
# ИНИЦИАЛИЗАЦИЯ
# =========================

init_db()

bot = Bot(token=TOKEN)

dp = Dispatcher()



# =========================
# КНОПКИ ПАРТНЁРА
# =========================


partner_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="🔗 Моя ссылка"
            )
        ],
        [
            KeyboardButton(
                text="👥 Мои клиенты"
            )
        ],
        [
            KeyboardButton(
                text="💰 Мой баланс"
            )
        ],
        [
            KeyboardButton(
                text="📜 История"
            )
        ],
    ],
    resize_keyboard=True
)



# =========================
# КНОПКИ АДМИНА
# =========================


admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="👥 Партнёры"
            )
        ],
        [
            KeyboardButton(
                text="🚗 Сделки"
            )
        ],
        [
            KeyboardButton(
                text="📊 Статистика"
            )
        ],
    ],
    resize_keyboard=True
)



# =========================
# START
# =========================


@dp.message(CommandStart())
async def start(message: Message):

    user = message.from_user

    args = message.text.split()

    invited_by = None


    # если человек пришёл по ссылке партнёра

    if len(args) > 1:

        try:
            invited_by = int(args[1])

        except:
            pass



    add_user(
        telegram_id=user.id,
        username=user.username,
        full_name=user.full_name,
        invited_by=invited_by
    )


    await message.answer(
        "🚗 Добро пожаловать в NY Партнёры!\n\n"
        "Здесь можно получать комиссию "
        "за клиентов на подбор автомобилей.",
        reply_markup=partner_kb
    )

# =========================
# АДМИН: СПИСОК ПАРТНЁРОВ
# =========================

@dp.message(Command("partners"))
async def partners(message: Message):

    if message.from_user.id != ADMIN_ID:
        await message.answer(
            "⛔ У вас нет доступа"
        )
        return

    users = get_partners()

    if not users:
        await message.answer(
            "Партнёров пока нет."
        )
        return

    text = "👥 Партнёры:\n\n"

    for user in users:

        telegram_id = user[0]
        username = user[1]
        name = user[2]
        balance = user[3]

        text += (
            f"👤 {name}\n"
            f"ID: {telegram_id}\n"
            f"Username: @{username}\n"
            f"💰 Баланс: {balance} ₽\n\n"
        )

    await message.answer(text)

# =========================
# МОЯ ССЫЛКА
# =========================


@dp.message(
    F.text == "🔗 Моя ссылка"
)
async def my_link(message: Message):

    me = await bot.get_me()


    link = (
        f"https://t.me/"
        f"{me.username}"
        f"?start={message.from_user.id}"
    )


    await message.answer(
        "Ваша партнёрская ссылка:\n\n"
        f"{link}\n\n"
        "Отправляйте её клиентам."
    )



# =========================
# БАЛАНС
# =========================


@dp.message(
    F.text == "💰 Мой баланс"
)
async def my_balance(message: Message):

    balance = get_balance(
        message.from_user.id
    )


    await message.answer(
        f"💰 Ваш баланс:\n\n"
        f"{balance} ₽"
    )



# =========================
# МОИ КЛИЕНТЫ
# =========================


@dp.message(F.text == "👥 Мои клиенты")
async def clients(message: Message):

    users = get_clients(message.from_user.id)


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
            text += f"👤 @{username}\n"
        else:
            text += f"👤 {name}\n"


    await message.answer(text)



# =========================
# ИСТОРИЯ
# =========================


@dp.message(
    F.text == "📜 История"
)
async def history(message: Message):

    data = get_history(
        message.from_user.id
    )


    if not data:

        await message.answer(
            "История пока пустая."
        )

        return


    text = "📜 История начислений:\n\n"


    for amount, deal_id, date in data:

        text += (
            f"Сделка №{deal_id}\n"
            f"+{amount} ₽\n"
            f"{date}\n\n"
        )


    await message.answer(text)
    # =========================
# ПРОВЕРКА АДМИНА
# =========================

def is_admin(user_id):

    return user_id == ADMIN_ID



# =========================
# АДМИН ПАНЕЛЬ
# =========================


@dp.message(Command("admin"))
async def admin_panel(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return


    await message.answer(
        "👑 Админ-панель\n\n"
        "Доступные команды:\n\n"
        "/partners - список партнёров\n"
        "/deals - список сделок\n"
        "/deal ID_клиента ID_партнёра\n"
        "/done ID_сделки сумма",
        reply_markup=admin_kb
    )



# =========================
# СПИСОК ПАРТНЁРОВ
# =========================


@dp.message(Command("partners"))
async def partners(message: Message):

    if not is_admin(message.from_user.id):

        return


    from database import get_all_users


    users = get_all_users()


    if not users:

        await message.answer(
            "Партнёров нет."
        )

        return


    text = "👥 Партнёры:\n\n"


    for user_id, name, balance in users:

        text += (
            f"👤 {name}\n"
            f"ID: {user_id}\n"
            f"Баланс: {balance} ₽\n\n"
        )


    await message.answer(text)



# =========================
# СОЗДАТЬ СДЕЛКУ
# =========================

@dp.message(Command("deal"))
async def create_deal_cmd(message: Message):

    if not is_admin(message.from_user.id):

        return


    from database import create_deal


    args = message.text.split()


    if len(args) != 3:

        await message.answer(
            "Формат:\n"
            "/deal ID_клиента ID_партнёра"
        )

        return


    try:

        client_id = int(args[1])
        partner_id = int(args[2])


    except:

        await message.answer(
            "ID должны быть числами."
        )

        return



    deal_id = create_deal(
        client_id,
        partner_id
    )


    await message.answer(
        f"🚗 Сделка создана\n\n"
        f"Номер: #{deal_id}\n"
        f"Клиент: {client_id}\n"
        f"Партнёр: {partner_id}\n"
        f"Статус: Новая"
    )



# =========================
# СПИСОК СДЕЛОК
# =========================


@dp.message(Command("deals"))
async def deals(message: Message):

    if not is_admin(message.from_user.id):

        return


    from database import get_deals


    data = get_deals()


    if not data:

        await message.answer(
            "Сделок пока нет."
        )

        return



    text = "🚗 Сделки:\n\n"


    for deal in data:

        deal_id, client, partner, status, money = deal


        text += (
            f"#{deal_id}\n"
            f"Клиент: {client}\n"
            f"Партнёр: {partner}\n"
            f"Статус: {status}\n"
            f"Комиссия: {money} ₽\n\n"
        )


    await message.answer(text)



# =========================
# ЗАВЕРШИТЬ СДЕЛКУ
# =========================


@dp.message(Command("done"))
async def done_deal(message: Message):

    if not is_admin(message.from_user.id):

        return


    from database import finish_deal


    args = message.text.split()


    if len(args) != 3:

        await message.answer(
            "Формат:\n"
            "/done ID_сделки сумма"
        )

        return



    try:

        deal_id = int(args[1])
        amount = int(args[2])


    except:

        await message.answer(
            "ID и сумма должны быть числами."
        )

        return



    partner_id = finish_deal(
        deal_id,
        amount
    )


    if not partner_id:

        await message.answer(
            "Сделка не найдена."
        )

        return



    await message.answer(
        "✅ Сделка завершена\n\n"
        f"Начислено: {amount} ₽\n"
        f"Партнёр: {partner_id}"
    )


    try:

        await bot.send_message(
            partner_id,
            "🎉 Поздравляем!\n\n"
            "Ваша сделка завершена.\n"
            f"Начислено: {amount} ₽"
        )

    except:

        pass



# =========================
# КНОПКИ АДМИНА
# =========================


@dp.message(
    F.text == "👥 Партнёры"
)
async def partners_button(message: Message):

    await partners(message)



@dp.message(
    F.text == "🚗 Сделки"
)
async def deals_button(message: Message):

    await deals(message)



# =========================
# ЗАПУСК
# =========================

@dp.message(Command("delete_partner"))
async def delete_partner(message: Message):

    # проверяем, что пишет именно админ
    if message.from_user.id != ADMIN_ID:
        return

    # разбиваем сообщение
    args = message.text.split()

    # если ID не указан
    if len(args) < 2:
        await message.answer(
            "❌ Укажите ID партнёра\n\n"
            "Пример:\n"
            "/delete_partner 123456789"
        )
        return

    # берём ID из команды
    user_id = int(args[1])

    # удаляем из базы
    delete_user(user_id)

    await message.answer(
        f"✅ Партнёр {user_id} удалён"
    )
    
async def main():

    print("Бот запущен...")

    await dp.start_polling(bot)



if __name__ == "__main__":

    asyncio.run(main())
