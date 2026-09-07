import asyncio
import html
import logging
import uuid

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_IDS, CHANNEL_ID, DELETE_AFTER
from database import db
from utils import telegraph
from utils.formatters import format_post_caption, get_warning_text, get_deletion_warning_text
from keyboards.inline import post_action_kb, post_confirm_kb, cancel_kb, main_menu_kb

router = Router()

POST_STATES = {}

STATE_IDLE = "idle"
STATE_COLLECT_MEDIA = "collect_media"
STATE_SCRIPT = "collect_script"
STATE_TITLE = "collect_title"
STATE_CONFIRM = "confirm"


def _confirm_full_kb():
    return post_confirm_kb()


def _confirm_script_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ ပုံများ ပြီးပါပြီ → ဇာတ်ကားအမည် ထည့်မည်", callback_data="got_all_media")
    builder.button(text="❌ ပယ်ဖျက်မည်", callback_data="cancel_post")
    builder.adjust(1)
    return builder.as_markup()


def _new_state(admin_id):
    return {
        "admin_id": admin_id,
        "media_group_id": None,
        "poster_file_ids": [],
        "movie_file_id": None,
        "movie_file_name": None,
        "script_text": None,
        "title": None,
        "genres": "",
        "year": "",
        "rating": "",
        "state": STATE_IDLE,
        "media_lock": asyncio.Lock(),
        "pending_media": [],
    }


# ---------- MESSAGE HANDLING ----------

@router.message(lambda msg: msg.from_user and msg.from_user.id in ADMIN_IDS and msg.text == "/post")
async def start_post(message: Message):
    await _start_new_post(message)


@router.callback_query(F.data == "new_post")
async def new_post_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    await _start_new_post(callback)
    await callback.answer("🎬 ပိုစ်အသစ်")


async def _start_new_post(event):
    state = _new_state(event.from_user.id)
    state["state"] = STATE_COLLECT_MEDIA
    POST_STATES[event.from_user.id] = state
    if isinstance(event, CallbackQuery):
        await event.message.answer(
            "🎬 <b>ပိုစ်အသစ် တည်ဆောက်ရန်</b>\n\n"
            "1️⃣ <b>ပုံများ</b> ပို့ပါ (တစ်ပုံချင်း သို့မဟုတ် အများအပြား)\n"
            "2️⃣ <b>ဇာတ်ညွှန်း</b> ပို့ပါ\n"
            "3️⃣ <b>Movie ဖိုင်</b> ပို့ပါ\n\n"
            "ပုံပြီးရင် ဇာတ်ညွှန်း ပို့လို့ရပြီ။\n"
            "Movie ဖိုင် ပို့ပြီးရင် post ပြီးပါပြီ။\n\n"
            "❌ ပယ်ဖျက်ရန်: <b>/cancel</b>",
            parse_mode="HTML",
            reply_markup=cancel_kb(),
        )
    else:
        await event.answer(
            "🎬 <b>ပိုစ်အသစ် တည်ဆောက်ရန်</b>\n\n"
            "1️⃣ <b>ပုံများ</b> ပို့ပါ (တစ်ပုံချင်း သို့မဟုတ် အများအပြား)\n"
            "2️⃣ <b>ဇာတ်ညွှန်း</b> ပို့ပါ\n"
            "3️⃣ <b>Movie ဖိုင်</b> ပို့ပါ\n\n"
            "ပုံပြီးရင် ဇာတ်ညွှန်း ပို့လို့ရပြီ။\n"
            "Movie ဖိုင် ပို့ပြီးရင် post ပြီးပါပြီ။\n\n"
            "❌ ပယ်ဖျက်ရန်: <b>/cancel</b>",
            parse_mode="HTML",
            reply_markup=cancel_kb(),
        )


@router.message(F.photo | F.document | F.video, lambda msg: msg.from_user and msg.from_user.id in POST_STATES)
async def collect_media(message: Message):
    state = POST_STATES.get(message.from_user.id)
    if not state:
        return

    file_id = None
    file_name = ""
    if message.photo:
        file_id = message.photo[-1].file_id
        file_name = "photo"
    elif message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or "document"
    elif message.video:
        file_id = message.video.file_id
        file_name = getattr(message.video, "file_name", None) or "video.mp4"

    if not file_id:
        return

    is_movie = file_name.lower().endswith((".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".3gp", ".mpeg"))

    if is_movie:
        # Movie file captured at any stage
        state["movie_file_id"] = file_id
        state["movie_file_name"] = file_name
        await message.answer(
            f"🎬 <b>Movie ဖိုင် ရပြီ:</b> <code>{html.escape(file_name)}</code>\n\n"
            "📝 <b>ဇာတ်ညွှန်း ပို့ပါ</b> (သို့မဟုတ် အောက်က ခလုတ်နှိပ်ပါ):",
            parse_mode="HTML",
            reply_markup=_confirm_script_kb(),
        )
        return

    # Non-movie media (photos) - only during collection phase
    if state["state"] != STATE_COLLECT_MEDIA:
        return

    state["poster_file_ids"].append(file_id)

    await asyncio.sleep(0.5)
    if not message.media_group_id:
        await message.answer(
            f"🖼 <b>ပုံ:</b> {len(state['poster_file_ids'])} ခု ရပြီ\n\n"
            "📝 <b>ဇာတ်ညွှန်း ပို့ပါ</b> (သို့မဟုတ် အောက်က ခလုတ်နှိပ်ပါ):",
            parse_mode="HTML",
            reply_markup=_confirm_script_kb(),
        )


@router.callback_query(F.data == "got_all_media")
async def got_all_media(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    state = POST_STATES.get(callback.from_user.id)
    if not state:
        await callback.answer("❌ State မရှိပါ!", show_alert=True)
        return

    if not state["poster_file_ids"]:
        await callback.answer("⚠️ ပုံမရှိသေးပါ!", show_alert=True)
        return

    state["state"] = STATE_TITLE
    await callback.message.edit_text(
        "🎬 <b>ဇာတ်ကားအမည် ရိုက်ထည့်ပါ:</b>\n\n"
        "(Post ပေါ်မှာ ပြမယ့် နာမည် — ဥပမာ: <code>ဆင်ဖြူတော</code>)",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )
    await callback.answer("🎬 ဇာတ်ကားအမည် ရိုက်ပါ")


@router.callback_query(F.data == "add_more_movie")
async def add_more_movie(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    state = POST_STATES.get(callback.from_user.id)
    if not state:
        await callback.answer("❌ State မရှိပါ!", show_alert=True)
        return
    await callback.message.answer(
        "🎬 <b>Movie ဖိုင် ပို့ပါ</b>\n"
        "(.mp4, .mkv, .avi စသည်)",
        parse_mode="HTML",
    )
    await callback.answer("🎬 Movie ဖိုင် ပို့ပါ")


@router.message(lambda m: m.from_user and m.from_user.id in POST_STATES and m.text)
async def collect_text(message: Message):
    state = POST_STATES.get(message.from_user.id)
    if not state:
        return

    if message.text.startswith("/"):
        return

    if state["state"] == STATE_TITLE:
        state["title"] = message.text.strip()
        state["state"] = STATE_SCRIPT
        await message.answer(
            f"🎬 <b>ဇာတ်ကားအမည်:</b> {html.escape(state['title'])}\n\n"
            "📝 <b>ဇာတ်ညွှန်း ပို့ပါ</b>\n\n"
            "မင်းရဲ့ ဇာတ်ညွှန်းကို text message အနေနဲ့ ပို့ပါ။\n"
            "ဒီ text ကို Telegraph မှာ တင်ပြီး \n"
            "'📝 ဇာတ်ညွှန်းအပြည့်အစုံဖတ်ရန်' button ထဲကို link ထည့်ပေးမယ်။",
            parse_mode="HTML",
            reply_markup=cancel_kb(),
        )
        return

    if state["state"] == STATE_SCRIPT:
        state["script_text"] = message.text.strip()
        state["state"] = STATE_CONFIRM
        await message.answer(
            "✅ <b>ဇာတ်ညွှန်း ရပြီ</b>\n\n"
            "🔁 Movie ဖိုင် ပို့လိုပါက ပို့ပါ။\n"
            "ပြီးပြီဆိုရင် အောက်က ခလုတ်နှိပ်ပါ:",
            parse_mode="HTML",
            reply_markup=_confirm_full_kb(),
        )
        return

    if state["state"] == STATE_CONFIRM:
        await message.answer(
            "⬇️ အောက်က ခလုတ်နှိပ်ပြီး post ပို့ပါ။",
            parse_mode="HTML",
            reply_markup=_confirm_full_kb(),
        )
        return


@router.callback_query(F.data == "confirm_post")
async def confirm_post(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    state = POST_STATES.get(callback.from_user.id)
    if not state:
        await callback.answer("❌ State မရှိပါ!", show_alert=True)
        return

    # Set default title from movie file name if not set
    if not state["title"]:
        state["title"] = state["movie_file_name"] or "Movie"

    original_media = list(state["poster_file_ids"])
    movie_file_id = state["movie_file_id"]
    script_text = state["script_text"]

    if not movie_file_id:
        await callback.answer("⚠️ Movie ဖိုင် မရှိသေးပါ!", show_alert=True)
        return

    await callback.message.edit_text("⏳ <b>Post တည်ဆောက်နေသည်...</b>", parse_mode="HTML")

    telegraph_url = None
    if script_text:
        telegraph_url = await telegraph.create_page(
            state["title"],
            str(telegraph.text_to_content(script_text)),
        )

    if not movie_file_id:
        await callback.message.answer("⚠️ Movie ဖိုင်မရှိပါ!", parse_mode="HTML")
        POST_STATES.pop(callback.from_user.id, None)
        return

    # Build deep link
    post_id = str(uuid.uuid4())[:8]
    deep_link = f"https://t.me/{callback.bot.username}?start=movie_{post_id}"

    await db.save_post(
        post_id=post_id,
        title=state["title"],
        script_text=script_text,
        telegraph_url=telegraph_url,
        poster_file_ids=original_media,
        movie_file_id=movie_file_id,
        movie_file_name=state["movie_file_name"],
        genres=state["genres"],
        year=state["year"],
        rating=state["rating"],
    )

    try:
        await _send_post_to_channel(
            callback.bot,
            state["title"],
            original_media,
            telegraph_url,
            deep_link,
        )
        await callback.message.answer(
            f"✅ <b>Post ပို့ပြီးပါပြီ!</b>\n\n"
            f"🎬 <b>{html.escape(state['title'])}</b>\n"
            f"🔗 Deep Link: <code>{deep_link}</code>",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
    except Exception as e:
        logging.exception("Failed to send post to channel")
        await callback.message.answer(
            f"❌ <b>Post ပို့ရန် မအောင်မြင်ပါ:</b>\n{html.escape(str(e))}\n\n"
            f"CHANNEL_ID မှန်ကန်ကြောင်း စစ်ပါ။",
            parse_mode="HTML",
        )

    POST_STATES.pop(callback.from_user.id, None)


async def _send_post_to_channel(bot: Bot, title, poster_file_ids, telegraph_url, deep_link):
    if not CHANNEL_ID:
        return

    caption = format_post_caption(title)
    kb = post_action_kb(None, telegraph_url, deep_link)

    if len(poster_file_ids) == 1:
        await bot.send_photo(
            CHANNEL_ID,
            photo=poster_file_ids[0],
            caption=caption,
            parse_mode="HTML",
            reply_markup=kb,
        )
    elif len(poster_file_ids) > 1:
        # Media group
        media = []
        from aiogram.types import InputMediaPhoto
        for i, fid in enumerate(poster_file_ids):
            if i == 0:
                media.append(InputMediaPhoto(media=fid, caption=caption, parse_mode="HTML"))
            else:
                media.append(InputMediaPhoto(media=fid))
        # Send media group without buttons (can't attach buttons to album first photo reliably)
        await bot.send_media_group(CHANNEL_ID, media)
        # Send caption with buttons as separate message
        await bot.send_message(
            CHANNEL_ID,
            caption,
            parse_mode="HTML",
            reply_markup=kb,
        )
    else:
        await bot.send_message(
            CHANNEL_ID,
            caption,
            parse_mode="HTML",
            reply_markup=kb,
        )
