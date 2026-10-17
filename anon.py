import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from common import BACK_KB, InMode, btn, kb, leave_hooks, mode

router = Router()
waiting: list[int] = []
pair: dict[int, int] = {}

TXT = ("💬 Anonim chat\n\nSizga tasodifiy suhbatdosh topiladi. Ismingiz va username'ingiz ko'rinmaydi.\n"
       "Shaxsiy ma'lumot (telefon, karta) yubormang va odob saqlang.")
FIND_KB = kb([[btn("🔎 Suhbatdosh qidirish", "an:find")]])
STOP_KB = kb([[btn("❌ Suhbatni tugatish", "an:stop")]])


async def end_chat(uid, bot, notify=True):
    if uid in waiting:
        waiting.remove(uid)
    p = pair.pop(uid, None)
    if p is not None:
        pair.pop(p, None)
        if notify:
            try:
                await bot.send_message(p, "😕 Suhbatdosh chiqib ketdi.", reply_markup=FIND_KB)
            except Exception:
                pass


async def hook(uid, bot):
    await end_chat(uid, bot)


leave_hooks.append(hook)


@router.callback_query(F.data == "sec:anon")
async def section(c: CallbackQuery):
    await c.answer()
    mode[c.from_user.id] = "anon"
    await c.message.answer(TXT, reply_markup=BACK_KB)
    await c.message.answer("Boshlaymizmi?", reply_markup=FIND_KB)


@router.callback_query(F.data == "an:find")
async def find(c: CallbackQuery):
    uid = c.from_user.id
    await c.answer()
    mode[uid] = "anon"
    if uid in pair:
        return await c.message.answer("Siz allaqachon suhbatdasiz.")
    if uid in waiting:
        return await c.message.answer("⏳ Qidirilmoqda...")
    others = [w for w in waiting if w != uid]
    if others:
        p = others[0]
        waiting.remove(p)
        pair[uid], pair[p] = p, uid
        for x in (uid, p):
            try:
                await c.bot.send_message(x, "✅ Suhbatdosh topildi! Yozishingiz mumkin.", reply_markup=STOP_KB)
            except Exception:
                logging.exception("anon notify")
    else:
        waiting.append(uid)
        await c.message.answer("⏳ Suhbatdosh qidirilmoqda... Topilganda xabar beraman.")


@router.callback_query(F.data == "an:stop")
async def stop(c: CallbackQuery):
    await c.answer()
    await end_chat(c.from_user.id, c.bot)
    await c.message.answer("Suhbat tugadi.", reply_markup=FIND_KB)


@router.message(InMode("anon"))
async def relay(m: Message):
    uid = m.from_user.id
    p = pair.get(uid)
    if p is None:
        return await m.answer("Avval suhbatdosh qidiring 👇", reply_markup=FIND_KB)
    try:
        await m.copy_to(p)
    except Exception:
        await end_chat(uid, m.bot, notify=False)
        await m.answer("😕 Suhbatdoshga xabar yetmadi, suhbat tugadi.", reply_markup=FIND_KB)
