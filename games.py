import random

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from common import BACK_KB, InMode, btn, kb, mode

router = Router()
targets: dict[int, int] = {}

QUIZ = [
    ("O'zbekiston poytaxti qaysi shahar?", ["Samarqand", "Toshkent", "Buxoro", "Andijon"], 1),
    ("Mustaqillik e'lon qilingan yil?", ["1989", "1990", "1991", "1992"], 2),
    ("Quyosh tizimidagi eng katta sayyora?", ["Yer", "Saturn", "Mars", "Yupiter"], 3),
    ("Suv necha daraja Selsiyda qaynaydi (normal bosimda)?", ["90", "100", "110", "120"], 1),
    ("Eng katta okean qaysi?", ["Atlantika", "Hind", "Tinch", "Shimoliy Muz"], 2),
    ("Yilda necha oy bor?", ["10", "11", "12", "13"], 2),
    ("Qur'onda nechta sura bor?", ["99", "110", "114", "120"], 2),
    ("Ramazon hijriy yilning nechanchi oyi?", ["7", "8", "9", "10"], 2),
    ("Dunyodagi eng baland tog' cho'qqisi?", ["Elbrus", "Everest", "Mont-Blan", "Kilimanjaro"], 1),
    ("Alisher Navoiy qaysi shaharda tug'ilgan?", ["Hirot", "Samarqand", "Toshkent", "Buxoro"], 0),
    ("Amir Temur qaysi shaharda tug'ilgan?", ["Buxoro", "Xiva", "Kesh (Shahrisabz)", "Termiz"], 2),
    ("Insonning nechta barmog'i bor (ikki qo'lda)?", ["8", "10", "12", "20"], 1),
]
RPS = {"r": "✊ Tosh", "p": "✋ Qog'oz", "s": "✌️ Qaychi"}
BEATS = {"r": "s", "s": "p", "p": "r"}


def games_kb():
    return kb([
        [btn("✊ Tosh-qaychi-qog'oz", "gm:rps"), btn("🔢 Sonni top", "gm:guess")],
        [btn("🎲 Kubik/Zar", "gm:dice"), btn("❓ Viktorina", "gm:quiz")],
    ])


@router.callback_query(F.data == "sec:games")
async def section(c: CallbackQuery):
    await c.answer()
    mode[c.from_user.id] = None
    await c.message.answer("🎮 O'yinlar", reply_markup=BACK_KB)
    await c.message.answer("O'yinni tanlang:", reply_markup=games_kb())


@router.callback_query(F.data.startswith("gm:"))
async def pick(c: CallbackQuery):
    act, uid = c.data[3:], c.from_user.id
    await c.answer()
    if act == "rps":
        mode[uid] = None
        return await c.message.answer("Tanlang:", reply_markup=kb([[btn("✊", "rp:r"), btn("✋", "rp:p"), btn("✌️", "rp:s")]]))
    if act == "guess":
        mode[uid] = "guess"
        targets[uid] = random.randint(1, 100)
        return await c.message.answer("🔢 Men 1 dan 100 gacha son o'yladim. Toping! Sonni yozing:")
    if act == "dice":
        mode[uid] = None
        rows = [[btn(e, f"dc:{e}") for e in ("🎲", "🎯", "🏀", "⚽", "🎰")]]
        return await c.message.answer("Qaysi birini tashlaymiz?", reply_markup=kb(rows))
    if act == "quiz":
        mode[uid] = None
        q, opts, ans = random.choice(QUIZ)
        await c.message.answer_poll(q, opts, type="quiz", correct_option_id=ans, is_anonymous=False)
        return await c.message.answer("Yana savol kerakmi?", reply_markup=kb([[btn("🔁 Yana savol", "gm:quiz")]]))


@router.callback_query(F.data.startswith("rp:"))
async def rps(c: CallbackQuery):
    await c.answer()
    me, bot_ = c.data[3:], random.choice("rps")
    if me == bot_:
        res = "🤝 Durang!"
    elif BEATS[me] == bot_:
        res = "🎉 Siz yutdingiz!"
    else:
        res = "😎 Men yutdim!"
    await c.message.answer(f"Siz: {RPS[me]}\nMen: {RPS[bot_]}\n\n{res}",
                           reply_markup=kb([[btn("🔁 Yana", "gm:rps")]]))


@router.callback_query(F.data.startswith("dc:"))
async def dice(c: CallbackQuery):
    await c.answer()
    await c.message.answer_dice(emoji=c.data[3:])


@router.message(InMode("guess"), F.text)
async def guess(m: Message):
    uid = m.from_user.id
    if not m.text.strip().isdigit():
        return await m.answer("❗ Faqat son yozing (1-100).")
    n, t = int(m.text), targets.get(uid)
    if t is None:
        mode[uid] = None
        return
    if n < t:
        await m.answer("⬆️ Kattaroq son")
    elif n > t:
        await m.answer("⬇️ Kichikroq son")
    else:
        mode[uid] = None
        targets.pop(uid, None)
        await m.answer("🎉 To'g'ri topdingiz!", reply_markup=kb([[btn("🔁 Yana o'ynash", "gm:guess")]]))
