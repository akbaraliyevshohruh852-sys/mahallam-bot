import logging
import pandas as pd
import os
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from datetime import datetime

# ========================
# ⚙️ KONFIGURATSIYA
# ========================
BOT_TOKEN = "8535307553:AAGnsB0qowUeUaGuVvSBWiOwPEuGY2132rg"
ADMIN_ID = 5200168486
GROQ_API_KEY = "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"
DB_FILE = "mahallam_bazasi.csv"
NEWS_FILE = "yangiliklar.txt"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())

# ========================
# 📝 HOLATLAR (FSM)
# ========================
class Registration(StatesGroup):
    gender = State()
    full_name = State()
    street = State()
    phone = State()

class ProblemReport(StatesGroup):
    target = State()
    content = State()

class AdminStates(StatesGroup):
    broadcast = State()
    add_news = State()

class ChatAI(StatesGroup):
    waiting_message = State()

# ========================
# 🛠 BAZA FUNKSIYALARI
# ========================
def save_user(data):
    file_exists = os.path.isfile(DB_FILE)
    df = pd.DataFrame([data])
    df.to_csv(DB_FILE, mode='a', index=False, header=not file_exists, encoding='utf-8-sig')

def get_all_user_ids():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        return df['ID'].tolist()
    return []

# ========================
# 🤖 AI (GROQ)
# ========================
async def get_ai_response(user_text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    payload = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "system", "content": "Siz mahalla yordamchisisiz."}, {"role": "user", "content": user_text}]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                data = await resp.json()
                return data['choices'][0]['message']['content']
    except: return "🤖 AI band."

# ========================
# ⌨️ TUGMALAR
# ========================
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🤖 AI Yordamchi", "📢 Yangiliklar")
    kb.add("📝 Murojaat", "👨‍👩‍👧‍👦 Yettilik")
    kb.add("👤 Profilim", "🆘 SOS")
    return kb

def admin_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("📊 Excel Baza", "📢 E'lon Tarqatish")
    kb.add("✍️ Yangilik Qo'shish", "📈 Statistika")
    kb.add("⬅️ Chiqish")
    return kb

# ========================
# 🚀 HANDLERLAR
# ========================

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("<b>Yangi Obod MFY</b> botiga xush kelibsiz!\nRo'yxatdan o'ting. Jinsingiz:")
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True).add("Erkak", "Ayol")
    await Registration.gender.set()
    await message.answer("Tanlang:", reply_markup=kb)

@dp.message_handler(state=Registration.gender)
async def reg_g(message: types.Message, state: FSMContext):
    await state.update_data(gender=message.text)
    await message.answer("Ism-familiyangizni kiriting:", reply_markup=types.ReplyKeyboardRemove())
    await Registration.next()

@dp.message_handler(state=Registration.full_name)
async def reg_n(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True).add("Navro'z", "Mustaqillik", "Bog'zor", "Guliston")
    await message.answer("Ko'changizni tanlang:", reply_markup=kb)
    await Registration.next()

@dp.message_handler(state=Registration.street)
async def reg_s(message: types.Message, state: FSMContext):
    await state.update_data(street=message.text)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("📞 Kontakt", request_contact=True))
    await message.answer("Telefon raqamingizni yuboring:", reply_markup=kb)
    await Registration.next()

@dp.message_handler(state=Registration.phone, content_types=['contact'])
async def reg_p(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_info = {"ID": message.from_user.id, "Ism": data['name'], "Jinsi": data['gender'], "Ko'cha": data['street'], "Tel": message.contact.phone_number, "Sana": datetime.now()}
    save_user(user_info)
    await message.answer("🎉 Registratsiya tugadi!", reply_markup=main_menu())
    await state.finish()

# --- ADMIN FUNKSIYALARI ---
@dp.message_handler(commands=['admin'], user_id=ADMIN_ID)
async def admin_start(message: types.Message):
    await message.answer("🛠 Admin Panel:", reply_markup=admin_menu())

@dp.message_handler(lambda m: m.text == "📊 Excel Baza", user_id=ADMIN_ID)
async def adm_excel(message: types.Message):
    if os.path.exists(DB_FILE):
        pd.read_csv(DB_FILE).to_excel("Mahalla.xlsx", index=False)
        with open("Mahalla.xlsx", "rb") as f: await message.answer_document(f)
        os.remove("Mahalla.xlsx")

@dp.message_handler(lambda m: m.text == "📈 Statistika", user_id=ADMIN_ID)
async def adm_stats(message: types.Message):
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        stats = f"👥 Jami: {len(df)}\n👨 Erkak: {len(df[df['Jinsi']=='Erkak'])}\n👩 Ayol: {len(df[df['Jinsi']=='Ayol'])}"
        await message.answer(stats)

@dp.message_handler(lambda m: m.text == "📢 E'lon Tarqatish", user_id=ADMIN_ID)
async def br_start(message: types.Message):
    await message.answer("Barcha foydalanuvchilarga yuboriladigan xabarni yozing:")
    await AdminStates.broadcast.set()

@dp.message_handler(state=AdminStates.broadcast, user_id=ADMIN_ID)
async def br_send(message: types.Message, state: FSMContext):
    users = get_all_user_ids()
    count = 0
    for uid in users:
        try:
            await bot.send_message(uid, f"📢 <b>MAHALLA E'LONI:</b>\n\n{message.text}")
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ {count} kishiga yuborildi.", reply_markup=admin_menu())
    await state.finish()

# --- SOS ---
@dp.message_handler(lambda m: m.text == "🆘 SOS")
async def sos_handler(message: types.Message):
    await bot.send_message(ADMIN_ID, f"🚨 <b>SOS XABARI!</b>\nFoydalanuvchi: {message.from_user.full_name}\nID: {message.from_user.id} yordam so'rayapti!")
    await message.answer("🆘 Xabar mas'ul xodimlarga yuborildi. Tez orada bog'lanishadi.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
