import asyncio
import logging
import os
import re
import shutil
import tempfile

import yt_dlp
from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile, Message

from common import BACK_KB, MAX_SIZE, InMode, btn, kb, mode, sem
from downloader import dl_audio

router = Router()
TXT_MUSIC = "Assalomu aleykum menga audio yoki qoshiq nomini yuboring men sizga yuklab beraman 😍😎"


def yt_search(q):
    o = {"quiet": True, "no_warnings": True, "extract_flat": True}
    with yt_dlp.YoutubeDL(o) as y:
        info = y.extract_info(f"ytsearch5:{q}", download=False)
    return [e for e in (info.get("entries") or []) if e and e.get("id")]


async def search_and_show(m: Message, query: str):
    wait = await m.answer("🔎 Qidirilmoqda...")
    try:
        res = await asyncio.to_thread(yt_search, query)
    except Exception:
        logging.exception("search")
        res = []
    try:
        await wait.delete()
    except Exception:
        pass
    if not res:
        return await m.answer("❌ Hech narsa topilmadi.")
    rows = []
    for e in res:
        d = int(e.get("duration") or 0)
        rows.append([btn(f"🎵 {e.get('title', '')[:45]} [{d // 60}:{d % 60:02d}]", f"m:{e['id']}")])
    await m.answer("Topilgan variantlar:", reply_markup=kb(rows))


@router.callback_query(F.data == "sec:music")
async def section(c: CallbackQuery):
    await c.answer()
    mode[c.from_user.id] = "music"
    await c.message.answer(TXT_MUSIC, reply_markup=BACK_KB)


@router.message(InMode("music"), F.audio)
async def on_audio(m: Message):
    a = m.audio
    q = " ".join(x for x in [a.performer, a.title] if x) or (a.file_name or "")
    if not q:
        return await m.answer("❗ Qo'shiq nomini yozib yuboring.")
    await search_and_show(m, q)


@router.message(InMode("music"), F.text)
async def on_text(m: Message):
    await search_and_show(m, m.text)


@router.callback_query(F.data.startswith("m:"))
async def pick(c: CallbackQuery):
    await c.answer("⏳ Yuklanmoqda...")
    vid = c.data[2:]
    tmp = tempfile.mkdtemp()
    try:
        async with sem:
            path, title = await asyncio.to_thread(dl_audio, f"https://www.youtube.com/watch?v={vid}", tmp)
        if not path or os.path.getsize(path) > MAX_SIZE:
            return await c.message.answer("❌ Fayl topilmadi yoki juda katta.")
        safe = re.sub(r'[\\/:*?"<>|]', "", title)[:60] or "audio"
        await c.message.answer_audio(FSInputFile(path, filename=f"{safe}.mp3"), title=title)
    except Exception:
        logging.exception("music")
        await c.message.answer("❌ Yuklab bo'lmadi.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
