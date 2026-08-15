import asyncio
import socket

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from config import TOKEN, ADMIN_ID
from database import (
    init_db,
    add_user,
    get_balance,
    add_balance,
    set_balance,
    get_all_users,
)

# Используем IPv4
socket.setdefaulttimeout(30)

init_db()

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ------------------------
# Клавиатуры
# ------------------------

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚗 Подобрать автомобиль")],
        [KeyboardButton(text="🤝 Стать партнёром")],
        [KeyboardButton(text="🔗 Моя ссылка")],
        [KeyboardButton(text="💰 Баланс")],
        [KeyboardButton(text="📞 Поддержка")],
    ],
    resize_keyboard=True,
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👥 Все партнёры")],
        [KeyboardButton(text="💰 Начислить комиссию")],
        [KeyboardButton(text="🔄 Обнулить баланс")],
        [KeyboardButton(text="⚠️ Обнулить все балансы")],
    ],
    resize_keyboard=True,
)

# ------------------------
# /start
# ------------------------

@dp.message(CommandStart())
async def start(message: Message):
    user = message.from_user

    add_user(
        telegram_id=user.id,
        username=user.username,
        full_name=user.full_name,
    )

    await message.answer(
        "Добро пожаловать в NY Партнёры!",
        reply_markup=main_kb,
    )

# ------------------------
# /admin
# ------------------------

@dp.message(Command("admin"))
async def admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ запрещён.")
        return

    await message.answer(
        "Добро пожаловать в админ-панель.",
        reply_markup=admin_kb,
    )

# ------------------------
# /partners
# ------------------------

@dp.message(Command("partners"))
async def partners(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ запрещён.")
        return

    users = get_all_users()

    if not users:
        await message.answer("Партнёров пока нет.")
        return

    text = "Партнёры:\\n\\n"

    for telegram_id, full_name, balance in users:
        text += (
            f"{full_name}\\n"
            f"ID: {telegram_id}\\n"
            f"Баланс: {balance} ₽\\n\\n"
        )

    await message.answer(text)

# ------------------------
# /commission ID СУММА
# ------------------------

@dp.message(Command("commission"))
async def commission(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ запрещён.")
        return

    parts = message.text.split()

    if len(parts) != 3:
        await message.answer(
            "Использование:\\n/commission ID СУММА\\n\\nПример:\\n/commission 1877434604 15000"
        )
        return

    try:
        partner_id = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        await message.answer("ID и сумма должны быть числами.")
        return

    add_balance(partner_id, amount)

    await message.answer(
        f"Начислено {amount} ₽ партнёру {partner_id}."
    )

    try:
        await bot.send_message(
            chat_id=partner_id,
            text=f"По вашей сделке начислена комиссия {amount} ₽.",
        )
    except Exception:
        pass

# ------------------------
# /resetbalance ID
# ------------------------

@dp.message(Command("resetbalance"))
async def resetbalance(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ запрещён.")
        return

    parts = message.text.split()

    if len(parts) != 2:
        await message.answer(
            "Использование:\\n/resetbalance ID"
        )
        return

    try:
        partner_id = int(parts[1])
    except ValueError:
        await message.answer("ID должен быть числом.")
        return

    set_balance(partner_id, 0)

    await message.answer(
        f"Баланс партнёра {partner_id} обнулён."
    )

# ------------------------
# /resetall
# ------------------------

@dp.message(Command("resetall"))
async def resetall(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ запрещён.")
        return

    users = get_all_users()

    for telegram_id, _, _ in users:
        set_balance(telegram_id, 0)

    await message.answer(
        "Балансы всех партнёров обнулены."
    )

# ------------------------
# Кнопки
# ------------------------

@dp.message(F.text == "🚗 Подобрать автомобиль")
async def pick_car(message: Message):
    await message.answer(
        "Напишите, какой автомобиль вы хотите найти."
    )

@dp.message(F.text == "🤝 Стать партнёром")
async def become_partner(message: Message):
    await message.answer(
        "Вы уже зарегистрированы как партнёр NY."
    )

@dp.message(F.text == "🔗 Моя ссылка")
async def mylink(message: Message):
    me = await bot.get_me()

    link = f"https://t.me/{me.username}?start={message.from_user.id}"

    await message.answer(
        f"Ваша партнёрская ссылка:\\n\\n{link}"
    )

@dp.message(F.text == "💰 Баланс")
async def balance(message: Message):
    bal = get_balance(message.from_user.id)

    await message.answer(
        f"Ваш баланс: {bal} ₽"
    )

@dp.message(F.text == "📞 Поддержка")
async def support(message: Message):
    await message.answer(
        "Напишите: @your_username"
    )

@dp.message()
async def other(message: Message):
    await message.answer(
        "Используйте кнопки меню ниже.",
        reply_markup=main_kb,
    )

# ------------------------
# Запуск
# ------------------------

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())