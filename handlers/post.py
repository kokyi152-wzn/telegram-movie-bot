import asyncio
import html
import logging
import uuid

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_IDS, CHANNEL_ID, CHANNEL2_ID, CHANNEL_URL, CHANNEL2_URL
from database import db
from utils import telegraph
from utils.formatters import format_post_caption
from keyboards.inline import post_action_kb, photo_prompt_kb

router = Router()

POST_STATES = {}

# Restarting debounce tasks: photo -> refresh count on the prompt message
PHOTO_TASKS = {}

STATE_IDLE = "idle"
STATE_COLLECT_MEDIA = "collect_media"   # waiting for photos
STATE_COLLECT_SCRIPT = "collect_script"  # waiting for script (any number of parts)
STATE_COLLECT_MOVIE = "collect_movie"    # waiting for movie file
PHOTO_QUIET_SECONDS = 1.5


def _new_state(admin_id):
    return {
        "admin_id": admin_id,
        "poster_file_ids": [],
        "movie_file_id": None,
        "movie_title": None,
        "movie_caption": "",
        "movie_file_name": "",
        "script_parts": [],
        "telegraph_url": "",
        "state": STATE_IDLE,
        "_bot": None,
        "prompt_msg_id": None,
        "prompt_chat_id": None,
    }


def _clean_movie_title(raw: str) -> str:
    """Extract a clean original movie title from a caption/filename."""
    if not raw:
        return ""
    import re
    # Remove video extensions at the end
    clean = re.sub(r"\.(mp4|mkv|avi|mov|webm|m4v|3gp|mpeg)$", "", raw, flags=re.I)
    # Remove URLs and site handles
    clean = re.sub(r"https?://\S+|www\.\S+|t\.me/\S+|@\w+", " ", clean, flags=re.I)
    # Remove emojis / symbols (keep letters, digits, spaces, Burmese script)
    clean = re.sub(r"[^\w\s\u1000-\u109f\-\.]", " ", clean, flags=re.U)
    # Remove bracket/paren content and common tool/site tags (never common title words)
    for token in [r"\[[^\]]*\]", r"\([^)]*\)",
                  r"\b(1080p|720p|4k|bluray|x264|x265|webrip|hdtv|hdrip)\b",
                  r"\b(?:official|full|watch|online|download|free)\b",
                  r"\b\d{4}\b"]:
        clean = re.sub(token, " ", clean, flags=re.I)
    # For filenames: split on separators, drop empty/garbage segments
    parts = [p for p in re.split(r"[_.\-]+", clean) if p and not re.fullmatch(r"[_\-\.\s]+", p)]
    if parts:
        clean = " ".join(parts)
    clean = re.sub(r"\s+", " ", clean).strip(" .-")
    # Collapse repeated adjacent words (e.g. "Movie Movie")
    clean = re.sub(r"\b(\w+)\s+\1\b", r"\1", clean, flags=re.I)
    if len(clean) > 60:
        clean = clean[:60].strip()
    return clean if clean else raw.strip()


@router.message(lambda msg: msg.from_user and msg.from_user.id in ADMIN_IDS and msg.text == "/post")
async def start_post(message: Message):
    await _begin_post(message)


@router.callback_query(F.data == "new_post")
async def new_post_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    await _begin_post(callback)
    await callback.answer("🎬 ပိုစ်အသစ်")


async def _begin_post(event):
    state = _new_state(event.from_user.id)
    state["state"] = STATE_COLLECT_MEDIA
    state["_bot"] = getattr(event, "bot", None) or getattr(event.from_user, "bot", None)
    POST_STATES[event.from_user.id] = state
    send = event.message.answer if isinstance(event, CallbackQuery) else event.answer
    msg = await send(
        "🖼 <b>ပိုစ်အသစ် — အဆင့် 1/3</b>\n\n"
        "ဇာတ်ကားရဲ့ <b>ပုံ(များ)</b> ပို့ပါ။\n"
        "ပုံများများ ပို့လေ post ထဲမှာ အားလုံး ပါလေပါတယ်။\n"
        "တစ်ပုံချင်း သို့မဟုတ် album အဖြစ် ပို့လို့ရပါတယ်။\n\n"
        "ပုံအားလုံး ပို့ပြီးပါက အောက်ပါ\n"
        "\"✅ ပုံများပြီးပါပြီ\" ခလုတ်ကို နှိပ်ပါ:",
        parse_mode="HTML",
        reply_markup=photo_prompt_kb(),
    )
    state["prompt_msg_id"] = msg.message_id
    state["prompt_chat_id"] = msg.chat.id


# ---------------- PHOTOS ----------------

@router.message(F.photo, lambda m: m.from_user and m.from_user.id in POST_STATES)
async def collect_photo(message: Message):
    admin_id = message.from_user.id
    state = POST_STATES.get(admin_id)
    if not state or state["state"] != STATE_COLLECT_MEDIA:
        return

    state["poster_file_ids"].append(message.photo[-1].file_id)

    # Restart the quiet-timer: each new photo updates the count after a pause
    task = PHOTO_TASKS.get(admin_id)
    if task and not task.done():
        task.cancel()
    PHOTO_TASKS[admin_id] = asyncio.create_task(_update_photo_status(admin_id))


async def _update_photo_status(admin_id):
    try:
        await asyncio.sleep(PHOTO_QUIET_SECONDS)
    except asyncio.CancelledError:
        return

    state = POST_STATES.get(admin_id)
    if not state or state["state"] != STATE_COLLECT_MEDIA:
        return

    # Only update if this is still the active task
    task = PHOTO_TASKS.get(admin_id)
    if task is not asyncio.current_task():
        return

    bot = state["_bot"]
    if not bot or not state.get("prompt_msg_id"):
        return

    count = len(state["poster_file_ids"])
    try:
        await bot.edit_message_text(
            chat_id=state["prompt_chat_id"],
            message_id=state["prompt_msg_id"],
            text=(
                "🖼 <b>ပုံလက်ခံရရှိပါပြီ — "
                f"{count} ခု</b>\n\n"
                "ထပ်ပို့လိုပါက ဆက်ပို့ပါ။\n"
                "ပုံအားလုံး ပို့ပြီးပါက\n"
                "\"✅ ပုံများပြီးပါပြီ\" ခလုတ်ကို နှိပ်ပါ:"
            ),
            parse_mode="HTML",
            reply_markup=photo_prompt_kb(),
        )
    except Exception:
        logging.exception("Failed to update photo status")


@router.callback_query(F.data == "photos_done")
async def photos_done(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return

    state = POST_STATES.get(callback.from_user.id)
    if not state or state["state"] != STATE_COLLECT_MEDIA:
        await callback.answer("⚠️ State မရှိပါ! /post ဖြင့် ပြန်စပါ", show_alert=True)
        return

    if not state["poster_file_ids"]:
        await callback.answer("⚠️ ပုံ တစ်ပုံမှ မရသေးပါ!", show_alert=True)
        return

    task = PHOTO_TASKS.get(callback.from_user.id)
    if task and not task.done():
        task.cancel()

    state["state"] = STATE_COLLECT_SCRIPT
    await callback.message.answer(
        "✅ <b>ပုံလက်ခံရရှိပါပြီ!</b>\n\n"
        f"🖼 ပုံ <b>{len(state['poster_file_ids'])}</b> ခု ရပြီ။\n\n"
        "📝 <b>ဇာတ်ညွှန်း ပို့ပါ</b>\n\n"
        "ဇာတ်ညွှန်း ရှည်ရင် ရှည်သလို ပို့လို့ရပါတယ်\n"
        "(post ထဲမှာ စာလုံး 500 လုံးသာ ပြမည်၊\n"
        "အပြည့်အစုံကို Telegraph မှာ တင်ထားမည်)။\n\n"
        "ပို့ပြီးပါက <b>/scriptdone</b> ရိုက်ပါ\n"
        "(သို့) တိုက်ရိုက် ဇာတ်ကားဖိုင် ပို့လိုက်ပါ။",
        parse_mode="HTML",
    )
    await callback.answer()


# ---------------- SCRIPT (can be multiple messages) ----------------

@router.message(lambda m: m.from_user and m.from_user.id in POST_STATES and m.text and not m.text.startswith("/") and m.text.strip())
async def collect_script(message: Message):
    state = POST_STATES.get(message.from_user.id)
    if not state:
        return

    text = message.text.strip()
    if text.startswith("/"):
        return

    if state["state"] == STATE_COLLECT_SCRIPT:
        state["script_parts"].append(text)
        total_len = sum(len(p) for p in state["script_parts"])
        await message.answer(
            f"✅ <b>ဇာတ်ညွှန်း အပိုင်း {len(state['script_parts'])} လက်ခံရရှိပြီ</b> "
            f"(စုစုပေါင်း {total_len} လုံး).\n\n"
            "ဆက်ရေးလိုပါက ဆက်ပို့ပါ။\n"
            "ပြီးပါက <b>/scriptdone</b> ရိုက်ပါ\n"
            "(သို့) ဇာတ်ကားဖိုင် တိုက်ရိုက် ပို့ပါ။",
            parse_mode="HTML",
        )
        return

    if state["state"] == STATE_COLLECT_MOVIE:
        # Admin typed something instead of sending movie; just remind
        await message.answer(
            "🎬 <b>ဇာတ်ကားဖိုင်</b> ပို့ပါ (.mp4/.mkv/.avi စသည်).",
            parse_mode="HTML",
        )
        return

    # Still in photo phase
    await message.answer(
        "🖼 ဦးစွာ <b>ပုံများ</b> ပို့ပါ၊ ပြီးမှ ဇာတ်ညွှန်း ပို့ပါ။",
        parse_mode="HTML",
    )


@router.message(lambda m: m.from_user and m.from_user.id in POST_STATES and m.text == "/scriptdone")
async def script_done(message: Message):
    state = POST_STATES.get(message.from_user.id)
    if not state or state["state"] != STATE_COLLECT_SCRIPT:
        return
    state["state"] = STATE_COLLECT_MOVIE
    await message.answer(
        "✅ <b>ဇာတ်ညွှန်း လက်ခံရရှိပါပြီ!</b>\n\n"
        "🎬 <b>ဇာတ်ကားဖိုင် ပို့ပါ</b> (.mp4/.mkv/.avi)\n"
        "ဖိုင်နဲ့အတူ ဇာတ်ကားနာမည် caption အနေနဲ့ ထည့်ပို့လည်း ရပါတယ်။",
        parse_mode="HTML",
    )


# ---------------- MOVIE FILE ----------------

@router.message(F.video | F.document, lambda m: m.from_user and m.from_user.id in POST_STATES)
async def collect_movie(message: Message):
    state = POST_STATES.get(message.from_user.id)
    if not state:
        return

    file_id = None
    file_name = ""
    if message.video:
        file_id = message.video.file_id
        file_name = getattr(message.video, "file_name", None) or "video.mp4"
    elif message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or "document"

    if not file_id:
        return

    is_movie = file_name.lower().endswith((".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".3gp", ".mpeg"))

    # If still collecting photos, a video could be a clip; ignore unless movie
    if state["state"] == STATE_COLLECT_MEDIA:
        if is_movie:
            # Move along: movie arrived during photo phase
            if not state["poster_file_ids"]:
                await message.answer("⚠️ ပုံမပို့ရသေးပါ။ ပုံ ဦးစွာ ပို့ပါ။")
                return
            state["state"] = STATE_COLLECT_MOVIE
        else:
            return

    if state["state"] in (STATE_COLLECT_MOVIE, STATE_COLLECT_SCRIPT):
        if not is_movie:
            # If script not done and it's a movie, ok; otherwise ignore non-movie
            if state["state"] == STATE_COLLECT_MOVIE:
                await message.answer("⚠️ ဒါက ဇာတ်ကားဖိုင်မဟုတ်ပါ (.mp4/.mkv ဖြစ်ရပါမည်).")
                return
            # During script, non-movie file = ignore
            return

        # It's the movie file
        state["movie_file_id"] = file_id
        state["movie_file_name"] = file_name
        # Original movie name: prefer caption, else extract from filename
        caption = (message.caption or "").strip()
        raw_title = _clean_movie_title(caption) if caption else _clean_movie_title(file_name)
        state["movie_caption"] = caption
        state["movie_title"] = raw_title if raw_title else (caption or file_name)

        # Ensure script phase finalized
        if state["state"] != STATE_COLLECT_MOVIE:
            state["state"] = STATE_COLLECT_MOVIE

        # Stop any pending photo-status refresh
        task = PHOTO_TASKS.get(message.from_user.id)
        if task and not task.done():
            task.cancel()

        # Also, both script AND movie are done now -> show preview
        await _show_preview(message, state)
        return


async def _show_preview(message: Message, state):
    title = state["movie_title"] or "Movie"
    script_text = "\n\n".join(state["script_parts"]) if state["script_parts"] else ""

    kb = InlineKeyboardBuilder()
    kb.button(text="📝 ဇာတ်ညွှန်းလင့် ထည့်မည်", callback_data="add_telegraph")
    kb.button(text="✅ Post ပို့မည်", callback_data="confirm_post")
    kb.button(text="❌ ပယ်ဖျက်မည်", callback_data="cancel_post")
    kb.adjust(1)

    preview = (
        f"🎬 <b>Post အကြိုကြည့် (Preview)</b>\n\n"
        f"🏷 <b>ဇာတ်ကားနာမည်:</b> {html.escape(title)}\n"
        f"🖼 <b>ပုံ:</b> {len(state['poster_file_ids'])} ခု\n"
        f"📝 <b>ဇာတ်ညွှန်း:</b> {'ရှိပြီ (' + str(len(script_text)) + ' လုံး)' if script_text else '❌ မရှိသေး'}\n"
        f"🎬 <b>Movie:</b> {html.escape(state['movie_file_name'] or '')}\n\n"
        f"ဇာတ်ညွှန်းကို Telegraph ဖြစ်စေ၊ မရှိဘဲဖြစ်စေ ရွေးပါ:"
    )
    try:
        # preview with first photo inline
        if state["poster_file_ids"]:
            await message.answer_photo(
                photo=state["poster_file_ids"][0],
                caption=preview,
                parse_mode="HTML",
                reply_markup=kb.as_markup(),
            )
        else:
            await message.answer(preview, parse_mode="HTML", reply_markup=kb.as_markup())
    except Exception as e:
        logging.exception("Preview failed")
        await message.answer(preview, parse_mode="HTML", reply_markup=kb.as_markup())


@router.callback_query(F.data == "add_telegraph")
async def add_telegraph(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    state = POST_STATES.get(callback.from_user.id)
    if not state:
        await callback.answer("❌ State မရှိပါ!", show_alert=True)
        return

    script_text = "\n\n".join(state["script_parts"]) if state["script_parts"] else ""
    if not script_text:
        await callback.answer("⚠️ ဇာတ်ညွှန်း မရှိသေးပါ!", show_alert=True)
        return

    await callback.answer("⏳ Telegraph မှာ တင်နေသည်...")
    title = state["movie_title"] or "Movie"
    telegraph_url = await telegraph.create_page(
        title, telegraph.text_to_content(script_text)
    )
    state["telegraph_url"] = telegraph_url or ""
    if telegraph_url:
        await callback.message.answer(
            f"✅ <b>Telegraph လင့် ရပြီ!</b>\n{telegraph_url}\n\n"
            f"ခု \"✅ Post ပို့မည်\" နှိပ်ပါ",
            parse_mode="HTML",
        )
    else:
        await callback.answer("❌ Telegraph တင်ရန် မအောင်မြင်ပါ (token စစ်ပါ)", show_alert=True)


# ---------------- CONFIRM & POST ----------------

@router.callback_query(F.data == "confirm_post")
async def confirm_post(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    state = POST_STATES.get(callback.from_user.id)
    if not state:
        await callback.answer("❌ State မရှိပါ!", show_alert=True)
        return

    if not state.get("movie_file_id"):
        await callback.answer("⚠️ Movie ဖိုင် မရှိသေးပါ!", show_alert=True)
        return

    # The preview may be a photo message, so we never edit it — just answer.
    await callback.message.answer("⏳ <b>Post တည်ဆောက်နေသည်...</b>", parse_mode="HTML")

    task = PHOTO_TASKS.get(callback.from_user.id)
    if task and not task.done():
        task.cancel()

    title = state.get("movie_title") or "Movie"
    script_text = "\n\n".join(state["script_parts"]) if state["script_parts"] else ""
    telegraph_url = state.get("telegraph_url", "")

    # If script exists but no telegraph url built yet, build now
    if script_text and not telegraph_url:
        telegraph_url = await telegraph.create_page(
            title, telegraph.text_to_content(script_text)
        ) or ""

    post_id = str(uuid.uuid4())[:8]
    deep_link = f"https://t.me/{callback.bot.username}?start=movie_{post_id}"

    await db.save_post(
        post_id=post_id,
        title=title,
        script_text=script_text,
        telegraph_url=telegraph_url,
        poster_file_ids=list(state["poster_file_ids"]),
        movie_file_id=state["movie_file_id"],
        movie_file_name=state.get("movie_file_name", "movie"),
    )

    try:
        await _send_post_to_channel(callback.bot, title, state["poster_file_ids"], telegraph_url, deep_link, script_text)
        await callback.message.answer(
            f"✅ <b>Post တင်ပြီးပါပြီ!</b>\n\n"
            f"🎬 <b>{html.escape(title)}</b>\n\n"
            f"🖼 ပုံ {len(state['poster_file_ids'])} ခု | "
            f"📝 ဇာတ်ညွှန်း {len(script_text)} လုံး\n"
            f"ချန်နယ် 2 ခုလုံးမှာ တင်ပြီးပါပြီ။\n\n"
            f"သင့် private deep link ကို ရှေ့ message မှာ ပို့ပေးမည်။",
            parse_mode="HTML",
        )
        # Dedicated private deep link message for the admin
        deeplink_kb = InlineKeyboardBuilder()
        deeplink_kb.button(text="🎬 ဇာတ်ကားရယူရန်", url=deep_link)
        deeplink_kb.button(text="🏠 Admin Menu", callback_data="admin_menu")
        deeplink_kb.adjust(1)
        await callback.message.answer(
            f"🔗 <b>သင့် Deep Link (သီးသန့်)</b>\n\n"
            f"<code>{deep_link}</code>\n\n"
            f"👉 ဤ link ကို ဘယ်နေရာမှာမဆို တွဲသုံးပါ —\n"
            f"နှိပ်လိုက်တာနဲ့ user ဆီ bot က ဇာတ်ကား ပို့ပေးမယ်။\n"
            f"သို့မဟုတ် အောက်ပါ ခလုတ်ကို နှိပ်ပါ:",
            parse_mode="HTML",
            reply_markup=deeplink_kb.as_markup(),
        )
    except Exception as e:
        logging.exception("Failed to send post to channel")
        await callback.message.answer(
            f"❌ <b>Post ပို့ရန် မအောင်မြင်ပါ:</b>\n{html.escape(str(e))}\n\n"
            f"CHANNEL_ID / CHANNEL2_ID မှန်ကန်ကြောင်းနဲ့ bot က channel များထဲ admin ဖြစ်ကြောင်း စစ်ပါ။",
            parse_mode="HTML",
        )

    POST_STATES.pop(callback.from_user.id, None)


async def _send_post_to_one_channel(bot: Bot, chat_id, poster_file_ids, caption, kb):
    if not poster_file_ids:
        msg = await bot.send_message(chat_id, caption, parse_mode="HTML", reply_markup=kb)
        return [msg.message_id]
    try:
        if len(poster_file_ids) == 1:
            msg = await bot.send_photo(
                chat_id, photo=poster_file_ids[0],
                caption=caption, parse_mode="HTML", reply_markup=kb,
            )
            return [msg.message_id]
        # Album: photos without captions + separate caption message with buttons
        media = [InputMediaPhoto(media=fid) for fid in poster_file_ids]
        group = await bot.send_media_group(chat_id, media)
        text_msg = await bot.send_message(chat_id, caption, parse_mode="HTML", reply_markup=kb)
        return [m.message_id for m in group] + [text_msg.message_id]
    except Exception:
        logging.exception("Photo send failed, falling back to text (chat=%s)", chat_id)
        msg = await bot.send_message(chat_id, caption, parse_mode="HTML", reply_markup=kb)
        return [msg.message_id]


async def _send_post_to_channel(bot: Bot, title, poster_file_ids, telegraph_url, deep_link, script_text=""):
    channel_ids = [cid for cid in (CHANNEL_ID, CHANNEL2_ID) if cid]
    if not channel_ids:
        logging.warning("No channel IDs configured, skipping channel post")
        return []

    caption = format_post_caption(title, script_summary=script_text) if title else ""
    kb = post_action_kb(None, telegraph_url, deep_link, CHANNEL_URL, CHANNEL2_URL)

    all_ids = []
    for cid in channel_ids:
        try:
            all_ids += await _send_post_to_one_channel(bot, cid, poster_file_ids, caption, kb)
        except Exception as e:
            logging.warning("Failed to post to channel %s: %s", cid, e)
    return all_ids
