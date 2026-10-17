import ast
import logging
import operator
from urllib.parse import quote

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from common import BACK_KB, CITIES, InMode, btn, city_kb, http_json, kb, mode

router = Router()

OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}


def safe_eval(expr: str):
    expr = expr.replace(",", ".").replace("^", "**").replace("×", "*").replace("÷", "/")

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in OPS:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and (abs(b) > 100 or abs(a) > 1e6):
                raise ValueError("juda katta")
            return OPS[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        raise ValueError("noto'g'ri ifoda")

    return ev(ast.parse(expr.strip(), mode="eval"))


def weather_text(code: int) -> str:
    if code == 0:
        return "☀️ Ochiq"
    if code in (1, 2, 3):
        return "⛅ Qisman bulutli"
    if code in (45, 48):
        return "🌫 Tuman"
    if 51 <= code <= 57:
        return "🌦 Mayda yomg'ir"
    if 61 <= code <= 67 or 80 <= code <= 82:
        return "🌧 Yomg'ir"
    if 71 <= code <= 77 or code in (85, 86):
        return "❄️ Qor"
    if code >= 95:
        return "⛈ Momaqaldiroq"
    return "☁️ Bulutli"


def tools_kb():
    return kb([
        [btn("💵 Valyuta kursi", "tl:rate"), btn("🌤 Ob-havo", "tl:wx")],
        [btn("🔳 QR kod", "tl:qr"), btn("🧮 Kalkulyator", "tl:calc")],
        [btn("🔗 Qisqa havola", "tl:short")],
    ])


@router.callback_query(F.data == "sec:tools")
async def section(c: CallbackQuery):
    await c.answer()
    mode[c.from_user.id] = None
    await c.message.answer("🧰 Asboblar", reply_markup=BACK_KB)
    await c.message.answer("Kerakli asbobni tanlang:", reply_markup=tools_kb())


@router.callback_query(F.data.startswith("tl:"))
async def tool_pick(c: CallbackQuery):
    act, uid = c.data[3:], c.from_user.id
    await c.answer()
    if act == "home":
        mode[uid] = None
        return await c.message.answer("Kerakli asbobni tanlang:", reply_markup=tools_kb())
    if act == "rate":
        try:
            data = await http_json("https://cbu.uz/oz/arkhiv-kursov-valyut/json/")
            want = ["USD", "EUR", "RUB", "GBP", "KZT", "CNY", "TRY"]
            rows = [d for d in data if d.get("Ccy") in want]
            rows.sort(key=lambda d: want.index(d["Ccy"]))
            lines = [f"{d['Nominal']} {d['Ccy']} = {d['Rate']} so'm" for d in rows]
            return await c.message.answer(f"💵 Markaziy bank kursi ({data[0].get('Date', '')})\n\n" + "\n".join(lines))
        except Exception:
            logging.exception("rate")
            return await c.message.answer("❌ Kursni olib bo'lmadi.")
    if act == "wx":
        return await c.message.answer("Shaharni tanlang:", reply_markup=city_kb("wx", "tl:home"))
    if act == "qr":
        mode[uid] = "qr"
        return await c.message.answer("🔳 QR kodga aylantirish uchun matn yoki havola yuboring:")
    if act == "calc":
        mode[uid] = "calc"
        return await c.message.answer("🧮 Misol yozing, masalan: (12+8)*3/4  yoki  2^10")
    if act == "short":
        mode[uid] = "short"
        return await c.message.answer("🔗 Qisqartiriladigan havolani yuboring (https://...):")


@router.callback_query(F.data.startswith("wx:"))
async def weather(c: CallbackQuery):
    await c.answer()
    name, _, lat, lon = CITIES[int(c.data[3:])]
    try:
        d = await http_json(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "timezone": "auto",
                    "current": "temperature_2m,apparent_temperature,wind_speed_10m,relative_humidity_2m,weather_code"},
        )
        cur = d["current"]
        text = (
            f"🌤 {name}\n\n{weather_text(int(cur['weather_code']))}\n"
            f"🌡 Harorat: {cur['temperature_2m']}°C (his etiladi: {cur['apparent_temperature']}°C)\n"
            f"💧 Namlik: {cur['relative_humidity_2m']}%\n💨 Shamol: {cur['wind_speed_10m']} km/soat"
        )
    except Exception:
        logging.exception("weather")
        text = "❌ Ob-havoni olib bo'lmadi."
    await c.message.answer(text)


@router.message(InMode("qr"), F.text)
async def qr(m: Message):
    url = "https://api.qrserver.com/v1/create-qr-code/?size=600x600&data=" + quote(m.text)
    try:
        await m.answer_photo(url, caption="✅ QR kod tayyor")
    except Exception:
        logging.exception("qr")
        await m.answer("❌ QR kod yaratib bo'lmadi.")


@router.message(InMode("calc"), F.text)
async def calc(m: Message):
    try:
        r = safe_eval(m.text)
        r = int(r) if isinstance(r, float) and r.is_integer() else round(r, 8)
        await m.answer(f"🧮 {m.text} = {r}")
    except ZeroDivisionError:
        await m.answer("❌ 0 ga bo'lib bo'lmaydi.")
    except Exception:
        await m.answer("❌ Misolni tushunmadim. Masalan: (12+8)*3/4")


@router.message(InMode("short"), F.text)
async def short(m: Message):
    url = m.text.strip()
    if not url.startswith(("http://", "https://")):
        return await m.answer("❗ Havola https:// bilan boshlanishi kerak.")
    try:
        d = await http_json("https://is.gd/create.php", params={"format": "json", "url": url})
        if "shorturl" in d:
            await m.answer(f"🔗 {d['shorturl']}")
        else:
            await m.answer("❌ Qisqartirib bo'lmadi.")
    except Exception:
        logging.exception("short")
        await m.answer("❌ Qisqartirib bo'lmadi.")
