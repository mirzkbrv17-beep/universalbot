import asyncio
import logging
import os

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message
from aiohttp import web

import anon
import db
import downloader
import games
import islamic
import moderator
import music
import subscribe
import tests
import tools
from common import (ADMIN_IDS, BACK_KB, BOT_TOKEN, MAIN_KB, MONGO_URL, leave_hooks, menu_kb, mode)

logging.basicConfig(level=logging.INFO)

TXT_START = ("Assalomu alaykum! 👋\nUniversal botimizga xush kelibsiz.\n"
             "Bo'limlarni ochish uchun «📋 Menyu» tugmasini bosing 👇")
TXT_DATE = (
    "Assalomu aleykum sz bu guruhga qoshilib dostlar ortdirishingiz mumkin va agar taqdir bolsa "
    "taqdirdagi juftligingiz bilan tanishishingiz mumkin sizga omad: ❤️❤️\n\n"
    "Guruh silkasi: https://t.me/o11jannah"
)

router = Router()
router.message.filter(F.chat.type == "private")
last = Router()
last.message.filter(F.chat.type == "private")


async def reset(uid, bot):
    for h in leave_hooks:
        try:
            await h(uid, bot)
        except Exception:
            logging.exception("leave hook")
    mode.pop(uid, None)


async def stats_text(uid):
    s = await db.store.stats()
    text = (
        "📊 Statistika\n\n"
        f"👥 Foydalanuvchilar: {s['total']}\n"
        f"▶️ /start bosgan odamlar: {s['started']}\n"
        f"🔁 Jami /start bosishlar: {s['starts']}\n"
        f"🟢 So'nggi 24 soatda faol: {s['active24']}"
    )
    if uid in ADMIN_IDS and not MONGO_URL:
        text += "\n\n⚠️ Baza (MONGO_URL) ulanmagan: bot qayta ishga tushganda statistika o'chadi."
    return text


class Track(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u, chat = data.get("event_from_user"), data.get("event_chat")
        if u and not u.is_bot and chat and chat.type == "private" and db.store:
            try:
                await db.store.touch(u.id, u.full_name, u.username)
            except Exception:
                logging.exception("touch")
        return await handler(event, data)


@router.message(CommandStart())
async def start(m: Message):
    await reset(m.from_user.id, m.bot)
    try:
        await db.store.touch(m.from_user.id, m.from_user.full_name, m.from_user.username, start=True)
    except Exception:
        logging.exception("start touch")
    await m.answer(TXT_START, reply_markup=MAIN_KB)


@router.message(F.text == "📋 Menyu")
async def menu_btn(m: Message):
    await reset(m.from_user.id, m.bot)
    await m.answer("Bo'limni tanlang 👇", reply_markup=menu_kb())


@router.message(F.text == "⬅️ Orqaga")
async def back_btn(m: Message):
    await reset(m.from_user.id, m.bot)
    await m.answer("🏠 Bosh sahifa", reply_markup=MAIN_KB)
    await m.answer("Bo'limni tanlang 👇", reply_markup=menu_kb())


@router.message(Command("stats"))
async def stats_cmd(m: Message):
    await m.answer(await stats_text(m.from_user.id))


@router.callback_query(F.data == "sec:stats")
async def stats_cb(c: CallbackQuery):
    await c.answer()
    await c.message.answer(await stats_text(c.from_user.id))


@router.callback_query(F.data == "sec:date")
async def dating(c: CallbackQuery):
    await c.answer()
    mode[c.from_user.id] = None
    await c.message.answer(TXT_DATE, reply_markup=BACK_KB)


@router.callback_query(F.data == "sec:menu")
async def to_menu(c: CallbackQuery):
    await c.answer()
    await reset(c.from_user.id, c.bot)
    await c.message.answer("Bo'limni tanlang 👇", reply_markup=menu_kb())


@router.message(Command("admin"), F.from_user.id.in_(ADMIN_IDS))
async def admin(m: Message):
    await m.answer(await stats_text(m.from_user.id) +
                   "\n\n📣 Hammaga xabar: /xabar matn\n(yoki biror xabarga javob qilib /xabar yozing)")


@router.message(Command("xabar"), F.from_user.id.in_(ADMIN_IDS))
async def broadcast(m: Message, command: CommandObject):
    src, text = m.reply_to_message, command.args
    if not src and not text:
        return await m.answer("Foydalanish: /xabar matn  yoki xabarga javob qilib /xabar")
    ids = await db.store.user_ids()
    await m.answer(f"📣 Yuborilmoqda: {len(ids)} ta foydalanuvchi...")
    ok = bad = 0
    for uid in ids:
        try:
            if src:
                await src.copy_to(uid)
            else:
                await m.bot.send_message(uid, text)
            ok += 1
        except Exception:
            bad += 1
        await asyncio.sleep(0.05)
    await m.answer(f"✅ Yetkazildi: {ok}\n❌ Yetmadi: {bad}")


@last.message()
async def fallback(m: Message):
    await m.answer("Bo'limlarni ochish uchun «📋 Menyu» tugmasini bosing 👇", reply_markup=MAIN_KB)


async def health(_):
    return web.Response(text="OK")


async def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN o'rnatilmagan")
    if MONGO_URL:
        db.store = db.MongoDB(MONGO_URL)
    else:
        logging.warning("MONGO_URL yo'q: ma'lumotlar vaqtinchalik saqlanadi")
        db.store = db.MemDB()

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    dp.update.outer_middleware(Track())
    dp.message.outer_middleware(subscribe.SubCheck())
    dp.callback_query.outer_middleware(subscribe.SubCheck())
    for r in (subscribe.router, router, moderator.router, downloader.router, music.router, islamic.router,
              tests.router, tools.router, games.router, anon.router, last):
        dp.include_router(r)
    await bot.delete_webhook(drop_pending_updates=True)

    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "10000"))).start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
