import logging
import asyncio
import json
import os
from datetime import datetime
from io import BytesIO

import mysql.connector
from mysql.connector import Error
import pandas as pd
import aiohttp

from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.callback_data import CallbackData
from aiogram.utils.executor import start_webhook

# ========================
# ⚙️ CONFIGURATION
# ========================
BOT_TOKEN = "8535307553:AAGnsB0qowUeUaGuVvSBWiOwPEuGY2132rg"
ADMIN_ID = 5200168486
GROQ_API_KEY = "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"

# MySQL Settings (SurkhanDC)
DB_CONFIG = {
    'host': 'localhost',
    'user': 's__42__mahallam.py',
    'password': 'shohruh2006', 
    'database': 's__42__mahallam.py'
}

# Webhook Settings
WEBHOOK_HOST = "https://42.surkhandc.uz"
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = "{}{}".format(WEBHOOK_HOST, WEBHOOK_PATH)

# Webhook server settings
WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = 8443

logging.basicConfig(level=logging.INFO)

# ========================
# 🗄 DATABASE HELPERS
# ========================
def db_query(query, params=None, fetchall=False, commit=False):
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params or ())
        
        if commit:
            conn.commit()
            return cursor.lastrowid
        
        if fetchall:
            return cursor.fetchall()
        return cursor.fetchone()
    except Error as e:
        logging.error("Database error: {}".format(e))
        return None
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def init_db():
    queries = [
        """CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            full_name VARCHAR(255),
            phone VARCHAR(20),
            passport VARCHAR(20),
            address TEXT,
            lat DOUBLE,
            lon DOUBLE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS problems (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT,
            description TEXT,
            lat DOUBLE,
            lon DOUBLE,
            status VARCHAR(50) DEFAULT 'yangi',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS sos_signals (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT,
            lat DOUBLE,
            lon DOUBLE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS market_items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT,
            title VARCHAR(255),
            price VARCHAR(100),
            description TEXT,
            photo_id VARCHAR(255),
            is_paid BOOLEAN DEFAULT FALSE,
            status VARCHAR(50) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    ]
    for q in queries:
        db_query(q, commit=True)

# ========================
# 🤖 AI HELPER (Direct HTTP)
# ========================
async def analyze_with_ai(prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": "Bearer {}".format(GROQ_API_KEY),
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama3-8b-8192",
        "messages": [
            {"role": "system", "content": "Siz Yangi Obod MFY botining aqlli yordamchisisiz. Mahalladoshlarga xushmuomala javob bering."},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['choices'][0]['message']['content']
                return "Kechirasiz, AI hozirda band."
    except Exception:
        return "AI xizmatida xatolik yuz berdi."

# ========================
# 📝 STATES
# ========================
class Registration(StatesGroup):
    full_name = State()
    phone = State()
    passport = State()
    address = State()

class ProblemReport(StatesGroup):
    desc = State()
    location = State()

class SOSStates(StatesGroup):
    location = State()

class AdminStates(StatesGroup):
    broadcast = State()
    private_msg = State()

class MarketPost(StatesGroup):
    title = State()
    price = State()
    desc = State()
    photo = State()

# ========================
# ⌨️ KEYBOARDS
# ========================
def get_main_kb(user_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🆘 SOS", "📝 Muammo yo'llash")
    kb.add("🏗 Mahalla Bozori", "🏢 Mahalla Yettiligi")
    kb.add("🤖 AI Yordamchi", "👤 Ma'lumotlarim")
    if user_id == ADMIN_ID:
        kb.add("⚙️ Admin Panel")
    return kb

def get_admin_kb():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📊 Aholi bazasi (Excel)", callback_data="admin_export"),
        types.InlineKeyboardButton("🛠 Muammolar", callback_data="admin_probs"),
        types.InlineKeyboardButton("📢 Xabar yuborish", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("🛍 Bozor nazorati", callback_data="admin_market")
    )
    return kb

# ========================
# 🚀 HANDLERS
# ========================
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    if message.chat.type != 'private':
        return
    
    user = db_query("SELECT * FROM users WHERE user_id = %s", (message.from_user.id,))
    if user:
        await message.answer("Xush kelibsiz, <b>{}</b>! Yangi Obod MFY botiga xush kelibsiz. ✨".format(user['full_name']), reply_markup=get_main_kb(message.from_user.id))
    else:
        await message.answer("Salom! Yangi Obod MFY botidan foydalanish uchun ro'yxatdan o'ting.\n\n👤 <b>To'liq ism-sharifingizni kiriting:</b>")
        await Registration.full_name.set()

@dp.message_handler(state=Registration.full_name)
async def reg_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("📞 Raqamni yuborish", request_contact=True))
    await message.answer("📞 Telefon raqamingizni yuboring:", reply_markup=kb)
    await Registration.phone.set()

@dp.message_handler(state=Registration.phone, content_types=['contact', 'text'])
async def reg_phone(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text
    await state.update_data(phone=phone)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("O'tkazib yuborish ⏭")
    await message.answer("🆔 Passport ma'lumotlaringizni kiriting (Ixtiyoriy):", reply_markup=kb)
    await Registration.passport.set()

@dp.message_handler(state=Registration.passport)
async def reg_passport(message: types.Message, state: FSMContext):
    passport = message.text if message.text != "O'tkazib yuborish ⏭" else "Kiritilmagan"
    await state.update_data(passport=passport)
    await message.answer("🏠 Yashash manzilingizni kiriting (Masalan: Navro'z ko'chasi, 12-uy):", reply_markup=types.ReplyKeyboardRemove())
    await Registration.address.set()

@dp.message_handler(state=Registration.address)
async def reg_done(message: types.Message, state: FSMContext):
    if len(message.text) < 5:
        await message.answer("❌ Manzil juda qisqa. Iltimos, to'liqroq yozing.")
        return
    
    data = await state.get_data()
    db_query("INSERT INTO users (user_id, full_name, phone, passport, address) VALUES (%s, %s, %s, %s, %s)",
             (message.from_user.id, data['full_name'], data['phone'], data['passport'], message.text), commit=True)
    
    await message.answer("🎉 Ro'yxatdan muvaffaqiyatli o'tdingiz!", reply_markup=get_main_kb(message.from_user.id))
    await state.finish()

# MUAMMO YO'LLASH
@dp.message_handler(Text(equals="📝 Muammo yo'llash"))
async def prob_start(message: types.Message):
    await message.answer("📝 Muammo haqida batafsil yozing:")
    await ProblemReport.desc.set()

@dp.message_handler(state=ProblemReport.desc)
async def prob_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc=message.text)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("📍 Joylashuvni yuborish", request_location=True))
    kb.add("📍 Joylashuvsiz yuborish")
    await message.answer("📍 Muammo joyini yubora olasizmi? (Ixtiyoriy)", reply_markup=kb)
    await ProblemReport.location.set()

@dp.message_handler(state=ProblemReport.location, content_types=['location', 'text'])
async def prob_done(message: types.Message, state: FSMContext):
    lat, lon = (message.location.latitude, message.location.longitude) if message.location else (None, None)
    data = await state.get_data()
    
    prob_id = db_query("INSERT INTO problems (user_id, description, lat, lon) VALUES (%s, %s, %s, %s)",
                       (message.from_user.id, data['desc'], lat, lon), commit=True)
    
    await message.answer("✅ Muammo qabul qilindi. Tez orada ko'rib chiqiladi. ID: #{}".format(prob_id), reply_markup=get_main_kb(message.from_user.id))
    
    # Adminga xabar
    admin_text = "🆕 <b>Yangi muammo keldi!</b>\n\n👤 Kimdan: {}\n📝 Tavsif: {}\n🆔 ID: #{}".format(message.from_user.full_name, data['desc'], prob_id)
    if lat:
        await bot.send_location(ADMIN_ID, lat, lon)
    await bot.send_message(ADMIN_ID, admin_text)
    await state.finish()

# SOS
@dp.message_handler(Text(equals="🆘 SOS"))
async def sos_start(message: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("📍 SOS - Joylashuvni yuborish", request_location=True))
    kb.add("❌ Bekor qilish")
    await message.answer("🚨 SOS tugmasini bosdingiz. Joylashuvingizni yuboring, yordam yuboramiz!", reply_markup=kb)
    await SOSStates.location.set()

@dp.message_handler(state=SOSStates.location, content_types=['location'])
async def sos_done(message: types.Message, state: FSMContext):
    db_query("INSERT INTO sos_signals (user_id, lat, lon) VALUES (%s, %s, %s)",
             (message.from_user.id, message.location.latitude, message.location.longitude), commit=True)
    await message.answer("🚀 SOS xabari barcha mas'ullarga yuborildi! Xavotir olmang.", reply_markup=get_main_kb(message.from_user.id))
    
    # Adminga xabar
    await bot.send_message(ADMIN_ID, "‼️ <b>SHOSHILINCH SOS!</b> ‼️\n👤 Fuqaro: {}".format(message.from_user.full_name))
    await bot.send_location(ADMIN_ID, message.location.latitude, message.location.longitude)
    await state.finish()

# AI
@dp.message_handler(Text(equals="🤖 AI Yordamchi"))
async def ai_menu(message: types.Message):
    await message.answer("🤖 Menga xohlagan savolingizni bering, masalan: <i>'Mahalla raisi kim?'</i> yoki <i>'SOS nima uchun?'</i>")

@dp.message_handler(commands=['ai'])
@dp.message_handler(lambda m: m.text and not m.text.startswith('/') and not m.text in ["🆘 SOS", "📝 Muammo yo'llash", "🏗 Mahalla Bozori", "🏢 Mahalla Yettiligi", "🤖 AI Yordamchi", "👤 Ma'lumotlarim", "⚙️ Admin Panel"])
async def ai_query_handler(message: types.Message):
    wait = await message.answer("🔍 O'ylayapman...")
    response = await analyze_with_ai(message.text)
    await wait.edit_text("🤖 <b>AI javobi:</b>\n\n{}".format(response))

# MARKET
@dp.callback_query_handler(lambda c: c.data == "market_add")
async def market_add_start(callback: types.CallbackQuery):
    await callback.message.answer("🛒 Nima sotmoqchisiz? (Nomini yozing):")
    await MarketPost.title.set()
    await callback.answer()

@dp.message_handler(state=MarketPost.title)
async def market_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("💰 Narxi qancha?")
    await MarketPost.price.set()

@dp.message_handler(state=MarketPost.price)
async def market_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("📝 Tavsif yozing:")
    await MarketPost.desc.set()

@dp.message_handler(state=MarketPost.desc)
async def market_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("📸 Rasm yuboring (yoki matn yozing):")
    await MarketPost.photo.set()

@dp.message_handler(state=MarketPost.photo, content_types=['photo', 'text'])
async def market_photo_done(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id if message.photo else None
    data = await state.get_data()
    db_query("INSERT INTO market_items (user_id, title, price, description, photo_id, is_paid, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
             (message.from_user.id, data['title'], data['price'], data['description'], photo_id, True, 'active'), commit=True)
    await message.answer("✅ E'loningiz bozorga joylashtirildi!", reply_markup=get_main_kb(message.from_user.id))
    await state.finish()

@dp.message_handler(Text(equals="🏗 Mahalla Bozori"))
async def market_menu(message: types.Message):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🛍 Bozor (E'lonlar)", callback_data="market_list"),
        types.InlineKeyboardButton("➕ E'lon berish", callback_data="market_add")
    )
    await message.answer("🏗 Mahalla ichki bozori.", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "market_list")
async def market_list(callback: types.CallbackQuery):
    items = db_query("SELECT m.*, u.full_name, u.phone FROM market_items m JOIN users u ON m.user_id = u.user_id WHERE m.status='active' ORDER BY m.created_at DESC LIMIT 10", fetchall=True)
    if not items:
        await callback.message.answer("Hozircha e'lonlar yo'q.")
    else:
        for it in items:
            text = "🛍 <b>{}</b>\n💰 Narxi: {}\n📝 Tavsif: {}\n👤 Sotuvchi: {}\n📞 Tel: {}".format(
                it['title'], it['price'], it['description'], it['full_name'], it['phone'])
            if it['photo_id']:
                await callback.message.answer_photo(it['photo_id'], caption=text)
            else:
                await callback.message.answer(text)
    await callback.answer()

# ADMIN HANDLERS
@dp.message_handler(Text(equals="⚙️ Admin Panel"), user_id=ADMIN_ID)
async def admin_panel(message: types.Message):
    await message.answer("⚙️ Admin boshqaruv paneli:", reply_markup=get_admin_kb())

@dp.callback_query_handler(lambda c: c.data == "admin_export", user_id=ADMIN_ID)
async def admin_export(callback: types.CallbackQuery):
    users = db_query("SELECT * FROM users", fetchall=True)
    df = pd.DataFrame(users)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    await callback.message.answer_document(types.InputFile(output, filename="aholi_bazasi.xlsx"))
    await callback.answer()

# WEBHOOK STARTUP
async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL)
    init_db()

async def on_shutdown(dp):
    await bot.delete_webhook()

if __name__ == '__main__':
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )
