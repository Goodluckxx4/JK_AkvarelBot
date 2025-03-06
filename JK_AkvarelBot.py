import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ChatPermissions

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

# === ГЛАВНОЕ МЕНЮ ===
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏠 Регистрация")],
        [KeyboardButton(text="📋 Список жильцов")],
        [KeyboardButton(text="❌ Удалить меня")]
    ],
    resize_keyboard=True
)

# === ОБРАБОТКА НОВЫХ УЧАСТНИКОВ ===
@router.chat_member()
async def on_chat_member_update(event: ChatMemberUpdated):
    if event.new_chat_member.status == ChatMemberStatus.MEMBER:
        user = event.from_user
        mention_link = f'<a href="tg://user?id={user.id}">{user.first_name or "Житель"}</a>'
        text = (
            f"Привет, {mention_link}!\n"
            "Добро пожаловать в чат ЖК Акварель.\n"
            "Пройди регистрацию, чтобы писать в чате: /register\n"
            "Если у вас есть вопросы, обратитесь к администраторам."
        )
        await bot.send_message(user.id, text, parse_mode="HTML", reply_markup=main_menu)
        
        # Ограничиваем права, пока не зарегистрируется
        await bot.restrict_chat_member(
            CHAT_ID, user.id,
            ChatPermissions(can_send_messages=False)
        )

# === РАЗРЕШАЕМ ПИСАТЬ ПОСЛЕ РЕГИСТРАЦИИ ===
async def allow_user_to_chat(user_id):
    await bot.restrict_chat_member(
        CHAT_ID, user_id,
        ChatPermissions(can_send_messages=True)
    )

# === КОМАНДА СТАРТА ===
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Я бот вашего дома ЖК Акварель по адресу Волжская 35А.\nВыберите действие:", reply_markup=main_menu)

# === РЕГИСТРАЦИЯ ===
@router.message(lambda m: m.text == "🏠 Регистрация")
async def cmd_register(message: types.Message, state: FSMContext):
    cursor.execute("SELECT * FROM residents WHERE user_id = ?", (message.from_user.id,))
    if cursor.fetchone():
        await message.answer("Вы уже зарегистрированы!")
        return
    await message.answer("Введите своё имя:")
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
    await message.answer(f"✅ Регистрация успешна!\nИмя: {mention_link}\nКвартира: {apartment}\nТелефон: {phone}", parse_mode="HTML", reply_markup=main_menu)
    await state.clear()

    # Разрешаем писать в чате после регистрации
    await allow_user_to_chat(message.from_user.id)
    
    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"🔔 Новый житель зарегистрировался: {mention_link}, кв. {apartment}", parse_mode="HTML")
