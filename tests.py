import logging
import re
import secrets
import time

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

import db
from common import ADMIN_IDS, BACK_KB, InMode, btn, kb, leave_hooks, mode, send_long

router = Router()
progress: dict[int, dict] = {}

HELP_NEW = (
    "➕ Yangi test. Quyidagi shaklda bitta xabarda yuboring (to'g'ri javob oxiriga * qo'ying):\n\n"
    "Nomi: Matematika 1\n"
    "Savol: 2+2 nechaga teng?\n"
    "A: 3\n"
    "B: 4*\n"
    "C: 5\n"
    "Savol: 10-3 nechaga teng?\n"
    "A: 7*\n"
    "B: 6\n\n"
    "Har savolda 2 dan 6 gacha variant (A-F) bo'ladi."
)


def parse_test(text: str):
    title, qs, cur = None, [], None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("nomi:"):
            title = line[5:].strip()
            continue
        if low.startswith("savol:"):
            cur = {"q": line[6:].strip(), "options": [], "correct": None}
            qs.append(cur)
            continue
        mt = re.match(r"^([A-Fa-f])\s*[:.)]\s*(.+)$", line)
        if mt and cur is not None:
            opt = mt.group(2).strip()
            ok = opt.endswith("*")
            if ok:
                opt = opt[:-1].strip()
            cur["options"].append(opt)
            if ok:
                cur["correct"] = len(cur["options"]) - 1
            continue
        raise ValueError(f"Tushunarsiz qator: {line}")
    if not title:
        raise ValueError("«Nomi:» qatori yo'q")
    if not qs:
        raise ValueError("Birorta ham «Savol:» yo'q")
    for i, q in enumerate(qs, 1):
        if not q["q"]:
            raise ValueError(f"{i}-savol matni bo'sh")
        if not 2 <= len(q["options"]) <= 6:
            raise ValueError(f"{i}-savolda 2 dan 6 gacha variant bo'lishi kerak")
        if q["correct"] is None:
            raise ValueError(f"{i}-savolda to'g'ri javob (*) belgilanmagan")
    return title, qs


def tests_kb(uid):
    rows = [[btn("▶️ Test topshirish", "ts:take")]]
    if uid in ADMIN_IDS:
        rows.append([btn("➕ Test yaratish", "ts:new"), btn("📊 Natijalar", "ts:res")])
    return kb(rows)


@router.callback_query(F.data == "sec:tests")
async def section(c: CallbackQuery):
    await c.answer()
    mode[c.from_user.id] = None
    await c.message.answer("📚 Testlar", reply_markup=BACK_KB)
    await c.message.answer("Tanlang:", reply_markup=tests_kb(c.from_user.id))


@router.callback_query(F.data.startswith("ts:"))
async def pick(c: CallbackQuery):
    act, uid = c.data[3:], c.from_user.id
    await c.answer()
    if act == "take":
        mode[uid] = "t_code"
        return await c.message.answer("Ustoz bergan test kodini yuboring:")
    if uid not in ADMIN_IDS:
        return await c.message.answer("❌ Bu bo'lim faqat ustozlar uchun.")
    if act == "new":
        mode[uid] = "t_new"
        return await c.message.answer(HELP_NEW)
    if act == "res":
        lst = await db.store.tests_by_owner(uid)
        if not lst:
            return await c.message.answer("Sizda hali test yo'q.")
        rows = [[btn(f"{t['title']} ({t['_id']})", f"tr:{t['_id']}")] for t in lst[:30]]
        return await c.message.answer("Qaysi test natijasi?", reply_markup=kb(rows))


@router.callback_query(F.data.startswith("tr:"))
async def results(c: CallbackQuery):
    await c.answer()
    code = c.data[3:]
    t = await db.store.get_test(code)
    if not t or t["owner"] != c.from_user.id:
        return await c.message.answer("❌ Topilmadi.")
    rs = await db.store.results_for(code)
    if not rs:
        return await c.message.answer("Hali hech kim topshirmagan.")
    rs.sort(key=lambda r: (-r["score"], r["name"]))
    lines = [f"📊 {t['title']} ({code}) — {len(rs)} ta natija\n"]
    for i, r in enumerate(rs, 1):
        tag = " ⛔ chiqib ketgan" if r.get("disq") else ""
        lines.append(f"{i}. {r['name']} — {r['score']}/{r['total']}{tag}")
    await send_long(c.message, "\n".join(lines))


@router.message(InMode("t_new"), F.text)
async def create(m: Message):
    try:
        title, qs = parse_test(m.text)
    except ValueError as e:
        return await m.answer(f"❌ {e}\n\nQayta yuboring yoki «⬅️ Orqaga» bosing.")
    code = secrets.token_hex(3).upper()
    await db.store.put_test({"_id": code, "title": title, "questions": qs,
                             "owner": m.from_user.id, "created": time.time()})
    mode[m.from_user.id] = None
    await m.answer(f"✅ Test yaratildi: {title}\nSavollar: {len(qs)} ta\n\n🔑 Kod: {code}\n\n"
                   "Talabalarga shu kodni bering: ular «📚 Testlar → Test topshirish» orqali kiradi.")


@router.message(InMode("t_code"), F.text)
async def enter_code(m: Message):
    uid, code = m.from_user.id, m.text.strip().upper()
    t = await db.store.get_test(code)
    if not t:
        return await m.answer("❌ Bunday kod topilmadi. Qayta yuboring:")
    old = await db.store.get_result(code, uid)
    if old:
        mode[uid] = None
        why = " (testdan chiqib ketgansiz)" if old.get("disq") else ""
        return await m.answer(f"Siz bu testni allaqachon topshirgansiz{why}: {old['score']}/{old['total']}\nQayta topshirib bo'lmaydi.")
    progress[uid] = {"code": code, "i": 0, "score": 0}
    mode[uid] = "t_run"
    await m.answer(f"📝 {t['title']}\nSavollar: {len(t['questions'])} ta.\n\n"
                   "⚠️ Test davomida «Orqaga» yoki «Menyu» bosib chiqsangiz, test tugatilgan hisoblanadi va qayta kira olmaysiz.")
    await show_q(m, t, 0)


def q_text(t, i):
    return f"❓ {i + 1}/{len(t['questions'])}\n\n{t['questions'][i]['q']}"


def q_kb(t, i):
    q = t["questions"][i]
    return kb([[btn(f"{'ABCDEF'[k]}) {o}"[:60], f"ta:{i}:{k}")] for k, o in enumerate(q["options"])])


async def show_q(m: Message, t, i):
    await m.answer(q_text(t, i), reply_markup=q_kb(t, i))


@router.message(InMode("t_run"))
async def during(m: Message):
    await m.answer("Javobni savol ostidagi tugmalar orqali tanlang 👆")


async def finish(uid, name, bot, disq=False):
    p = progress.pop(uid, None)
    if not p:
        return None
    t = await db.store.get_test(p["code"])
    total = len(t["questions"])
    await db.store.put_result({"_id": f"{p['code']}:{uid}", "code": p["code"], "uid": uid, "name": name,
                               "score": p["score"], "total": total, "disq": disq, "at": time.time()})
    mode[uid] = None
    try:
        tag = " ⛔ (testdan chiqib ketdi)" if disq else ""
        await bot.send_message(t["owner"], f"📥 {name} — «{t['title']}» ({p['code']}): {p['score']}/{total}{tag}")
    except Exception:
        pass
    return p["score"], total


@router.callback_query(F.data.startswith("ta:"))
async def answer(c: CallbackQuery):
    uid = c.from_user.id
    _, i, k = c.data.split(":")
    i, k = int(i), int(k)
    p = progress.get(uid)
    if not p or p["i"] != i:
        return await c.answer("Bu savol eskirgan.", show_alert=False)
    t = await db.store.get_test(p["code"])
    if k == t["questions"][i]["correct"]:
        p["score"] += 1
    p["i"] += 1
    await c.answer()
    if p["i"] < len(t["questions"]):
        await c.message.edit_text(q_text(t, p["i"]), reply_markup=q_kb(t, p["i"]))
    else:
        res = await finish(uid, c.from_user.full_name, c.bot)
        await c.message.edit_text(f"🏁 Test tugadi!\n\nNatija: {res[0]}/{res[1]}")


async def hook(uid, bot):
    if uid in progress:
        try:
            u = await bot.get_chat(uid)
            name = u.full_name
        except Exception:
            name = str(uid)
        res = await finish(uid, name, bot, disq=True)
        if res:
            try:
                await bot.send_message(uid, f"⛔ Test yakunlandi (chiqib ketdingiz). Natija: {res[0]}/{res[1]}")
            except Exception:
                logging.exception("disq notify")


leave_hooks.append(hook)
