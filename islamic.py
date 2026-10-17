import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from common import BACK_KB, CITIES, btn, city_kb, http_json, kb, mode

router = Router()

DUOLAR = (
    "📿 Duolar\n\n"
    "🍽 Ovqatdan oldin:\nBismillah.\n\n"
    "🍽 Ovqatdan keyin:\nAlhamdulillahilladhi at'amana va saqona va ja'alana minal muslimin.\n\n"
    "😴 Uxlashdan oldin:\nAllohumma bismika amutu va ahya."
)


def islam_kb():
    return kb([
        [btn("🕌 Namoz vaqtlari", "isl:pt")],
        [btn("📿 Duolar", "isl:du")],
        [btn("🧭 Qibla yo'nalishi", "isl:qb")],
    ])


@router.callback_query(F.data == "sec:islam")
async def section(c: CallbackQuery):
    await c.answer()
    mode[c.from_user.id] = None
    await c.message.answer("🕌 Islomiy bo'lim", reply_markup=BACK_KB)
    await c.message.answer("Kerakli bo'limni tanlang:", reply_markup=islam_kb())


@router.callback_query(F.data.startswith("isl:"))
async def islam(c: CallbackQuery):
    act = c.data[4:]
    await c.answer()
    if act == "home":
        await c.message.answer("Kerakli bo'limni tanlang:", reply_markup=islam_kb())
    elif act == "pt":
        await c.message.answer("Shaharni tanlang:", reply_markup=city_kb("pt", "isl:home"))
    elif act == "qb":
        await c.message.answer("Shaharni tanlang:", reply_markup=city_kb("qb", "isl:home"))
    elif act == "du":
        await c.message.answer(DUOLAR)


@router.callback_query(F.data.startswith("pt:"))
async def prayer(c: CallbackQuery):
    await c.answer()
    name, api, _, _ = CITIES[int(c.data[3:])]
    try:
        d = await http_json(
            "https://api.aladhan.com/v1/timingsByCity",
            params={"city": api, "country": "Uzbekistan", "method": 3, "school": 1},
        )
        t = d["data"]["timings"]
        g = lambda k: t[k].split()[0]
        text = (
            f"🕌 {name} — {d['data']['date']['readable']}\n\n"
            f"🌙 Bomdod: {g('Fajr')}\n🌅 Quyosh: {g('Sunrise')}\n☀️ Peshin: {g('Dhuhr')}\n"
            f"🌤 Asr: {g('Asr')}\n🌇 Shom: {g('Maghrib')}\n🌃 Xufton: {g('Isha')}"
        )
    except Exception:
        logging.exception("prayer")
        text = "❌ Namoz vaqtlarini olib bo'lmadi, keyinroq urinib ko'ring."
    await c.message.answer(text)


@router.callback_query(F.data.startswith("qb:"))
async def qibla(c: CallbackQuery):
    await c.answer()
    name, _, lat, lon = CITIES[int(c.data[3:])]
    try:
        d = await http_json(f"https://api.aladhan.com/v1/qibla/{lat}/{lon}")
        text = f"🧭 {name} uchun qibla: shimoldan soat strelkasi bo'yicha {round(d['data']['direction'], 1)}°"
    except Exception:
        logging.exception("qibla")
        text = "❌ Qibla ma'lumotini olib bo'lmadi."
    await c.message.answer(text)
