import asyncio
import glob
import logging
import os
import re
import shutil
import tempfile

import yt_dlp
from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile, Message

from common import BACK_KB, COOKIES_FILE, MAX_SIZE, InMode, btn, kb, mode, send_long, sem

router = Router()
cache: dict[tuple, dict] = {}
audio_counter: dict[int, int] = {}
URL_RE = re.compile(r"https?://\S+")

TXT_DL = ("Assalomu aleykum iltimos instagram youtube va pinterestdan havola yuboring "
          "men sizga video media fayl va captionni yuklab beraman 🥹🦋")


def base_opts(outdir):
    o = {"outtmpl": f"{outdir}/%(id)s.%(ext)s", "noplaylist": True, "quiet": True, "no_warnings": True}
    if os.path.exists(COOKIES_FILE):
        o["cookiefile"] = COOKIES_FILE
    return o


def dl_video(url, outdir):
    caption, path = "", None
    for h in (720, 480, 360):
        for f in glob.glob(f"{outdir}/*"):
            os.remove(f)
        o = base_opts(outdir)
        o["format"] = f"best[height<={h}][ext=mp4]/bv*[height<={h}]+ba/best[height<={h}]/best"
        o["merge_output_format"] = "mp4"
        with yt_dlp.YoutubeDL(o) as y:
            info = y.extract_info(url, download=True)
        caption = (info.get("description") or info.get("title") or "").strip()
        files = [f for f in glob.glob(f"{outdir}/*") if not f.endswith((".part", ".ytdl"))]
        path = max(files, key=os.path.getsize) if files else None
        if path and os.path.getsize(path) <= MAX_SIZE:
            break
    return path, caption


def dl_audio(url, outdir):
    o = base_opts(outdir)
    o["format"] = "bestaudio/best"
    o["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
    with yt_dlp.YoutubeDL(o) as y:
        info = y.extract_info(url, download=True)
    files = glob.glob(f"{outdir}/*.mp3")
    return (files[0] if files else None), info.get("title") or "audio"


def extract_hashtags(caption: str):
    return list(dict.fromkeys(re.findall(r"#\w+", caption or "", re.UNICODE)))


@router.callback_query(F.data == "sec:dl")
async def section(c: CallbackQuery):
    await c.answer()
    mode[c.from_user.id] = "dl"
    await c.message.answer(TXT_DL, reply_markup=BACK_KB)


@router.message(InMode("dl"), F.text)
async def on_link(m: Message):
    mt = URL_RE.search(m.text or "")
    if not mt:
        return await m.answer("❗ Iltimos, havola (link) yuboring.")
    url = mt.group(0)
    wait = await m.answer("⏳ Yuklanmoqda...")
    tmp = tempfile.mkdtemp()
    try:
        async with sem:
            path, caption = await asyncio.to_thread(dl_video, url, tmp)
        if not path:
            return await m.answer("❌ Video yuklanmadi (fayl hosil bo'lmadi).")
        if os.path.getsize(path) > MAX_SIZE:
            return await m.answer("❌ Video 360p da ham 50 MB dan katta, Telegram yubora olmaydi.")
        keys = kb([[btn("#️⃣ Hesh teg", "h"), btn("🎵 Audio", "a")]])
        sent = await m.answer_video(FSInputFile(path), reply_markup=keys)
        cache[(m.chat.id, sent.message_id)] = {"url": url, "caption": caption}
        if len(cache) > 500:
            cache.pop(next(iter(cache)))
    except Exception:
        logging.exception("dl")
        await m.answer("❌ Yuklab bo'lmadi. Havolani tekshiring (rasmli postlar qo'llanmaydi) yoki keyinroq urinib ko'ring.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            await wait.delete()
        except Exception:
            pass


@router.callback_query(F.data == "h")
async def cb_hashtag(c: CallbackQuery):
    await c.answer()
    item = cache.get((c.message.chat.id, c.message.message_id))
    if not item:
        return await c.message.answer("❌ Ma'lumot eskirgan, havolani qayta yuboring.")
    cap = item["caption"]
    if not cap:
        return await c.message.answer("Bu postda caption yo'q.")
    tags = extract_hashtags(cap)
    text = ("#️⃣ Hesh teglar:\n" + " ".join(tags) + "\n\n") if tags else "#️⃣ Hesh teg topilmadi.\n\n"
    await send_long(c.message, text + "📝 Caption:\n" + cap)


@router.callback_query(F.data == "a")
async def cb_audio(c: CallbackQuery):
    await c.answer("⏳ Audio tayyorlanmoqda...")
    item = cache.get((c.message.chat.id, c.message.message_id))
    if not item:
        return await c.message.answer("❌ Ma'lumot eskirgan, havolani qayta yuboring.")
    tmp = tempfile.mkdtemp()
    try:
        async with sem:
            path, _ = await asyncio.to_thread(dl_audio, item["url"], tmp)
        if not path or os.path.getsize(path) > MAX_SIZE:
            return await c.message.answer("❌ Audio topilmadi yoki juda katta.")
        uid = c.from_user.id
        audio_counter[uid] = audio_counter.get(uid, 0) + 1
        name = f"Abu.{audio_counter[uid]}.mp3"
        await c.message.answer_audio(FSInputFile(path, filename=name), title=name)
    except Exception:
        logging.exception("audio")
        await c.message.answer("❌ Audioni yuklab bo'lmadi.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
