import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton

# === НАСТРОЙКИ ===
API_TOKEN = "8129897637:AAHV6aLm2wMYLx0a9SdvFq8Z01b02hW-GdM"
ADMIN_IDS = [497592544]  # ID админов
CHAT_ID = -1001992519263  # ID чата ЖК

logging.basicConfig(level=logging.INFO)
conn = sqlite3.connect("residents.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS residents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE,
    name TEXT,
    apartment TEXT,
    phone TEXT
)
""")
conn.commit()

class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_apartment = State()
    waiting_for_phone = State()
    waiting_for_edit_field = State()

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# === ОБРАБОТКА НОВЫХ УЧАСТНИКОВ ===
@router.chat_member()
async def on_chat_member_update(event: ChatMemberUpdated):
    if event.new_chat_member.status == ChatMemberStatus.MEMBER:
        user = event.from_user
        mention_link = f'<a href="tg://user?id={user.id}">{user.first_name or "Житель"}</a>'
        text = (
            f"Привет, {mention_link}!\n"
            "Добро пожаловать в чат ЖК Акварель.\n"
            "Пройди регистрацию: /register"
        )
        await bot.send_message(user.id, text, parse_mode="HTML")

# === КОМАНДА СТАРТА ===
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Регистрация", callback_data="register")],
        [InlineKeyboardButton(text="📋 Список жильцов", callback_data="list")],
        [InlineKeyboardButton(text="❌ Удалить меня", callback_data="delete_me")]
    ])
    await message.answer("Привет! Выберите действие:", reply_markup=keyboard)

# === РЕГИСТРАЦИЯ ===
@router.callback_query(lambda c: c.data == "register")
async def cmd_register(callback: types.CallbackQuery, state: FSMContext):
    cursor.execute("SELECT * FROM residents WHERE user_id = ?", (callback.from_user.id,))
    if cursor.fetchone():
        await callback.message.answer("Вы уже зарегистрированы!")
        return
    await callback.message.answer("Введите своё имя:")
    await state.set_state(Registration.waiting_for_name)

@router.message(Registration.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите номер квартиры (от 1 до 198):")
    await state.set_state(Registration.waiting_for_apartment)

@router.message(Registration.waiting_for_apartment)
async def process_apartment(message: types.Message, state: FSMContext):
    await state.update_data(apartment=message.text)
    await message.answer("Введите телефон (или '-' если нет):")
    await state.set_state(Registration.waiting_for_phone)

@router.message(Registration.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.text
    data = await state.get_data()
    name, apartment = data["name"], data["apartment"]

    cursor.execute("INSERT INTO residents (user_id, name, apartment, phone) VALUES (?, ?, ?, ?)", 
                   (message.from_user.id, name, apartment, phone))
    conn.commit()

    mention_link = f'<a href="tg://user?id={message.from_user.id}">{name}</a>'
    await message.answer(f"✅ Регистрация успешна!\nИмя: {mention_link}\nКвартира: {apartment}\nТелефон: {phone}", parse_mode="HTML")
    await state.clear()

    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"🔔 Новый житель зарегистрировался: {mention_link}, кв. {apartment}", parse_mode="HTML")

# === СПИСОК ЖИЛЬЦОВ ===
@router.callback_query(lambda c: c.data == "list")
async def cmd_list(callback: types.CallbackQuery):
    cursor.execute("SELECT name, apartment, phone FROM residents WHERE user_id = ?", (callback.from_user.id,))
    if not cursor.fetchone():
        await callback.message.answer("❌ Доступ запрещён! Только зарегистрированные пользователи могут смотреть список.")
        return
    
    cursor.execute("SELECT name, apartment, phone, user_id FROM residents")
    rows = cursor.fetchall()

    text = "📋 <b>Список жильцов</b>:\n\n"
    for r in rows:
        name, apartment, phone, user_id = r
        mention_link = f'<a href="tg://user?id={user_id}">{name}</a>'
        text += f"🏠 Кв. {apartment} - {mention_link}, {phone}\n"

    await callback.message.answer(text, parse_mode="HTML")

# === УДАЛЕНИЕ ДАННЫХ ===
@router.callback_query(lambda c: c.data == "delete_me")
async def cmd_delete(callback: types.CallbackQuery):
    cursor.execute("DELETE FROM residents WHERE user_id = ?", (callback.from_user.id,))
    conn.commit()
    await callback.message.answer("✅ Ваши данные удалены.")

    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"🔴 {callback.from_user.full_name} удалил себя из базы.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
