import logging
import os
import time

from aiogram import BaseMiddleware, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from common import ADMIN_IDS, MAIN_KB, menu_kb

# Kanallar Render'dagi REQUIRED_CHANNELS o'zgaruvchisidan olinadi (vergul bilan: @kanal1,@kanal2)
CHANNELS = [c.strip() for c in os.getenv("REQUIRED_CHANNELS", "@o11abu").split(",") if c.strip()]

router = Router()
_ok_cache: dict[int, float] = {}  # uid -> a'zo bo'lgan vaqt (10 daqiqa eslab qolamiz)


async def is_subscribed(bot, uid: int) -> bool:
    if not CHANNELS or uid in ADMIN_IDS:
        return True
    if time.time() - _ok_cache.get(uid, 0) < 600:
        return True
    for ch in CHANNELS:
        try:
            mb = await bot.get_chat_member(ch, uid)
        except Exception as e:
            # bot kanalda admin emas yoki kanal nomi xato: foydalanuvchilarni qulflab qo'ymaymiz
            logging.error("Obuna tekshirib bo'lmadi (%s): %s", ch, e)
            continue
        joined = mb.status in ("member", "administrator", "creator") or (
            mb.status == "restricted" and getattr(mb, "is_member", False)
        )
        if not joined:
            return False
    _ok_cache[uid] = time.time()
    return True


def prompt_kb():
    rows = [[InlineKeyboardButton(text=f"📢 {c}", url=f"https://t.me/{c.lstrip('@')}")] for c in CHANNELS]
    rows.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="sub:check")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


PROMPT = "❗ Botdan foydalanish uchun avval quyidagi kanalga a'zo bo'ling, so'ng «✅ Tekshirish» tugmasini bosing 👇"


class SubCheck(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u, chat = data.get("event_from_user"), data.get("event_chat")
        if not u or u.is_bot or not chat or chat.type != "private":
            return await handler(event, data)
        if isinstance(event, CallbackQuery) and event.data == "sub:check":
            return await handler(event, data)
        bot = data["bot"]
        if await is_subscribed(bot, u.id):
            return await handler(event, data)

        # a'zo emas: /start bosganini statistikaga yozamiz, qolganini to'xtatamiz
        if isinstance(event, Message):
            if (event.text or "").startswith("/start") and db.store:
                try:
                    await db.store.touch(u.id, u.full_name, u.username, start=True)
                except Exception:
                    logging.exception("start touch")
            await event.answer(PROMPT, reply_markup=prompt_kb())
        elif isinstance(event, CallbackQuery):
            await event.answer("Avval kanalga a'zo bo'ling!", show_alert=True)
            if event.message:
                await event.message.answer(PROMPT, reply_markup=prompt_kb())
        return None


@router.callback_query(F.data == "sub:check")
async def check(c: CallbackQuery):
    _ok_cache.pop(c.from_user.id, None)
    if await is_subscribed(c.bot, c.from_user.id):
        await c.answer("✅ Rahmat!")
        try:
            await c.message.delete()
        except Exception:
            pass
        await c.message.answer("✅ A'zo bo'ldingiz. Botdan foydalanishingiz mumkin!", reply_markup=MAIN_KB)
        await c.message.answer("Bo'limni tanlang 👇", reply_markup=menu_kb())
    else:
        await c.answer("❌ Siz hali a'zo bo'lmadingiz.", show_alert=True)
