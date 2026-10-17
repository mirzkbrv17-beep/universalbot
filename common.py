import asyncio
import os
import re

import aiohttp
from aiogram.filters import BaseFilter
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MONGO_URL = os.getenv("MONGO_URL", "")
ADMIN_IDS = {int(x) for x in re.split(r"[,\s]+", os.getenv("ADMIN_IDS", "")) if x.isdigit()}
COOKIES_FILE = "cookies.txt"
MAX_SIZE = 50 * 1024 * 1024  # Telegram bot limiti

# foydalanuvchi qaysi bo'limda ekanligi
mode: dict[int, str | None] = {}
# bo'limdan chiqilganda chaqiriladigan funksiyalar: async def hook(uid, bot)
leave_hooks: list = []
# og'ir yuklashlar bir vaqtda 2 tadan oshmasin
sem = asyncio.Semaphore(2)


class InMode(BaseFilter):
    """Faqat shaxsiy chatda, foydalanuvchi ko'rsatilgan bo'limda bo'lsa o'tadi."""

    def __init__(self, *names):
        self.names = names

    async def __call__(self, message) -> bool:
        u = getattr(message, "from_user", None)
        if not u or message.chat.type != "private":
            return False
        return mode.get(u.id) in self.names


def btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


MAIN_KB = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📋 Menyu")]], resize_keyboard=True)
BACK_KB = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Orqaga")]], resize_keyboard=True)


def menu_kb():
    return kb([
        [btn("📥 Yuklovchi", "sec:dl"), btn("🎵 Musiqa", "sec:music")],
        [btn("🕌 Islamic", "sec:islam"), btn("📚 Testlar", "sec:tests")],
        [btn("🧰 Asboblar", "sec:tools"), btn("🎮 O'yinlar", "sec:games")],
        [btn("💬 Anonim chat", "sec:anon"), btn("💞 Tanishuv", "sec:date")],
        [btn("📊 Statistika", "sec:stats")],
    ])


# Shahar: (ko'rsatiladigan nom, namoz API nomi, lat, lon)
CITIES = [
    ("Toshkent", "Tashkent", 41.2995, 69.2401),
    ("Samarqand", "Samarkand", 39.6270, 66.9750),
    ("Buxoro", "Bukhara", 39.7747, 64.4286),
    ("Andijon", "Andijan", 40.7821, 72.3442),
    ("Namangan", "Namangan", 41.0011, 71.6683),
    ("Farg'ona", "Fergana", 40.3842, 71.7843),
    ("Nukus", "Nukus", 42.4531, 59.6103),
    ("Urganch", "Urgench", 41.5500, 60.6333),
]


def city_kb(prefix, back="sec:menu"):
    rows, row = [], []
    for i, c in enumerate(CITIES):
        row.append(btn(c[0], f"{prefix}:{i}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([btn("⬅️ Orqaga", back)])
    return kb(rows)


async def http_json(url: str, **kw):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as s:
        async with s.get(url, **kw) as r:
            return await r.json(content_type=None)


async def send_long(msg, text: str):
    for i in range(0, len(text), 4000):
        await msg.answer(text[i:i + 4000])
