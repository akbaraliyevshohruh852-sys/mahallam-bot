import logging
import asyncio
from io import BytesIO
import pandas as pd
import aiohttp
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup

# ========================
# ⚙️ CONFIGURATION
# ========================
# Render-da ishlashi uchun Portni 10000 qilib belgilaymiz
PORT = 10000 
BOT_TOKEN = "8535307553:AAGnsB0qowUeUaGuVvSBWiOwPEuGY2132rg"
ADMIN_ID = 5200168486
GROQ_API_KEY = "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"

logging.basicConfig(level=logging.INFO)

# Ma'lumotlarni vaqtincha saqlash uchun lug'atlar (Baza o'rniga)
users_db = {}
problems_db = []
market_items = []

# ========================
# 🤖 AI HELPER
# ========================
async def analyze_with_ai(prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
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

class ProblemReport(StatesGroup):
    desc = State()

class MarketPost(StatesGroup):
    title = State()
    price = State()
    desc = State()

# ========================
# ⌨️ KEYBOARDS
# ========================
def get_main_kb(user_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🆘 SOS", "📝 Muammo yo'llash")
    kb.add("🏗 Mahalla Bozori", "🤖 AI Yordamchi")
    if user_id == ADMIN_ID:
        kb.add("⚙️ Admin Panel")
    return kb

# ========================
# 🚀 HANDLERS
# ========================
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if user_id in users_db:
        await message.answer(f"Xush kelibsiz, <b>{users_db[user_id]['name']}</b>!", reply_markup=get_main_kb(user_id))
    else:
        await message.answer("Salom! Yangi Obod MFY botiga xush kelibsiz.\n\n👤 <b>Ism-sharifingizni kiriting:</b>")
        await Registration.full_name.set()

@dp.message_handler(state=Registration.full_name)
async def reg_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📞 Telefon raqamingizni kiriting:")
    await Registration.phone.set()

@dp.message_handler(state=Registration.phone)
async def reg_done(message: types.Message, state: FSMContext):
    data = await state.get_data()
    users_db[message.from_user.id] = {'name': data['name'], 'phone': message.text}
    await message.answer("🎉 Ro'yxatdan o'tdingiz!", reply_markup=get_main_kb(message.from_user.id))
    await state.finish()

@dp.message_handler(Text(equals="🤖 AI Yordamchi"))
async def ai_menu(message: types.Message):
    await message.answer("🤖 Menga savol bering (masalan: 'Mahalla nima?')")

@dp.message_handler(lambda m: m.text and not m.text.startswith('/'))
async def ai_query_handler(message: types.Message):
    if message.text in ["🆘 SOS", "📝 Muammo yo'llash", "🏗 Mahalla Bozori", "🤖 AI Yordamchi", "⚙️ Admin Panel"]:
        return
    wait = await message.answer("🔍 O'ylayapman...")
    response = await analyze_with_ai(message.text)
    await wait.edit_text(f"🤖 <b>AI javobi:</b>\n\n{response}")

# SOS Handler
@dp.message_handler(Text(equals="🆘 SOS"))
async def sos_call(message: types.Message):
    await message.answer("🚀 SOS xabari yuborildi! (Vaqtincha demo rejimida)")
    await bot.send_message(ADMIN_ID, f"‼️ <b>SHOSHILINCH SOS!</b>\n👤 Kimdan: {message.from_user.full_name}")

if __name__ == '__main__':
    # Render uchun polling ishlatamiz (webhook-siz osonroq)
    executor.start_polling(dp, skip_updates=True)
