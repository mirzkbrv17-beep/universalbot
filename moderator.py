import asyncio
import re
import time
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import ChatPermissions, Message

router = Router()
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

LINK_RE = re.compile(r"(https?://|www\.|t\.me/|telegram\.me/)", re.I)
admins_cache: dict[int, tuple] = {}
warns: dict[tuple, int] = {}


async def is_admin(bot, chat_id, uid) -> bool:
    ent = admins_cache.get(chat_id)
    if not ent or time.time() - ent[0] > 300:
        try:
            ids = {a.user.id for a in await bot.get_chat_administrators(chat_id)}
        except Exception:
            ids = set()
        admins_cache[chat_id] = (time.time(), ids)
    return uid in admins_cache[chat_id][1]


async def later_delete(msg: Message, sec=20):
    await asyncio.sleep(sec)
    try:
        await msg.delete()
    except Exception:
        pass


@router.message(F.new_chat_members)
async def welcome(m: Message):
    try:
        await m.delete()
    except Exception:
        pass
    for u in m.new_chat_members:
        if u.is_bot:
            continue
        w = await m.answer(f"👋 Xush kelibsiz, {u.full_name}!\nGuruh qoidalariga rioya qiling.")
        asyncio.create_task(later_delete(w, 30))


@router.message(F.left_chat_member)
async def left(m: Message):
    try:
        await m.delete()
    except Exception:
        pass


@router.message(Command("ban"))
async def ban(m: Message):
    if not await is_admin(m.bot, m.chat.id, m.from_user.id) or not m.reply_to_message:
        return
    try:
        await m.bot.ban_chat_member(m.chat.id, m.reply_to_message.from_user.id)
        await m.answer(f"🚫 {m.reply_to_message.from_user.full_name} guruhdan chiqarildi.")
    except Exception:
        await m.answer("❌ Bajarib bo'lmadi (botga admin huquqi kerak).")


@router.message(Command("mute"))
async def mute(m: Message):
    if not await is_admin(m.bot, m.chat.id, m.from_user.id) or not m.reply_to_message:
        return
    try:
        until = datetime.now(timezone.utc) + timedelta(hours=1)
        await m.bot.restrict_chat_member(m.chat.id, m.reply_to_message.from_user.id,
                                         ChatPermissions(can_send_messages=False), until_date=until)
        await m.answer(f"🔇 {m.reply_to_message.from_user.full_name} 1 soatga ovozsiz qilindi.")
    except Exception:
        await m.answer("❌ Bajarib bo'lmadi (botga admin huquqi kerak).")


@router.message(F.text | F.caption)
async def no_links(m: Message):
    text = m.text or m.caption or ""
    if not m.from_user or not LINK_RE.search(text):
        return
    if m.sender_chat or await is_admin(m.bot, m.chat.id, m.from_user.id):
        return
    try:
        await m.delete()
    except Exception:
        return
    key = (m.chat.id, m.from_user.id)
    warns[key] = warns.get(key, 0) + 1
    if warns[key] >= 3:
        warns[key] = 0
        try:
            until = datetime.now(timezone.utc) + timedelta(hours=1)
            await m.bot.restrict_chat_member(m.chat.id, m.from_user.id,
                                             ChatPermissions(can_send_messages=False), until_date=until)
            w = await m.answer(f"🔇 {m.from_user.full_name} 3 marta havola yuborgani uchun 1 soatga ovozsiz qilindi.")
        except Exception:
            return
    else:
        w = await m.answer(f"⚠️ {m.from_user.full_name}, guruhda havola yuborish mumkin emas ({warns[key]}/3).")
    asyncio.create_task(later_delete(w))
