import asyncio
import html
import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramBadRequest
from config import ADMIN_IDS, DELETE_AFTER, CHANNEL_ID, CHANNEL_URL
from database import db
from utils.formatters import get_warning_text, get_deletion_warning_text
from keyboards.inline import subscribe_kb

router = Router()

# Track pending deletions by message to avoid duplicates and let users manage
DELETION_TASKS = {}

# Track pending requests waiting for channel subscription
PENDING_REQUESTS = {}


async def _send_media_file(message: Message, file_id: str, name: str, caption: str):
    """Send a file, trying video first for video-like names, falling back to document."""
    video_exts = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v")
    video_first = name.lower().endswith(video_exts)
    last_err = None

    if video_first:
        try:
            return await message.answer_video(video=file_id, caption=caption, parse_mode="HTML")
        except Exception as e:
            last_err = e
            logging.warning("answer_video failed for %s -> trying document: %s", name, e)
    else:
        try:
            return await message.answer_document(document=file_id, caption=caption, parse_mode="HTML")
        except Exception as e:
            last_err = e
            logging.warning("answer_document failed for %s -> trying video: %s", name, e)

    if video_first:
        return await message.answer_document(document=file_id, caption=caption, parse_mode="HTML")
    try:
        return await message.answer_video(video=file_id, caption=caption, parse_mode="HTML")
    except Exception as e:
        if last_err is not None:
            raise last_err
        raise e


async def _is_subscribed(bot, user_id) -> bool:
    if not CHANNEL_ID:
        return True
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator")
    except TelegramBadRequest:
        return False
    except Exception as e:
        logging.warning("Channel check failed for %s: %s", user_id, e)
        return False


async def _require_subscription(message: Message, request_key: str):
    # Admins are always allowed (they test links without joining the channel)
    if message.from_user.id in ADMIN_IDS:
        return True
    if await _is_subscribed(message.bot, message.from_user.id):
        return True
    PENDING_REQUESTS[message.from_user.id] = request_key
    await message.answer(
        "⚠️ <b>Channel ထဲ ဝင်ထားမှသာ ဇာတ်ကားရယူလို့ရပါမည်!</b>\n\n"
        "📢 အောက်ပါ Channel ကို ဝင်ပြီး\n"
        "\"✅ ဝင်ပြီးပါပြီ\" ခလုတ်ကို နှိပ်ပါ:",
        parse_mode="HTML",
        reply_markup=subscribe_kb(CHANNEL_URL),
    )
    return False


async def _auto_delete(bot, chat_id, message_ids, title):
    """Wait DELETE_AFTER seconds then delete all files and send warning."""
    await asyncio.sleep(DELETE_AFTER)
    for mid in message_ids:
        try:
            await bot.delete_message(chat_id, mid)
        except Exception as e:
            logging.warning("Failed to delete message %s: %s", mid, e)
    try:
        await bot.send_message(
            chat_id,
            get_deletion_warning_text(title),
            parse_mode="HTML",
        )
    except Exception as e:
        logging.warning("Failed to send deletion warning: %s", e)


@router.message(CommandStart())
async def start_with_deep_link(message: Message):
    args = message.text.split(maxsplit=1)
    payload = ""
    if len(args) > 1:
        payload = args[1].strip().split()[0] if args[1].strip() else ""

    await db.add_user(
        message.from_user.id,
        message.from_user.username or "",
        message.from_user.first_name,
    )

    maintenance = await db.get_maintenance()
    if maintenance and message.from_user.id not in ADMIN_IDS:
        await message.answer(
            "🔧 <b>BOT ပြုပြင်နေပါသည်။</b>\n\n"
            "ကျေးဇူးပြု၍ နောက်မှ ထပ်ကြိုးစားကြည့်ပါ။",
            parse_mode="HTML",
        )
        return

    if payload.startswith("movie_"):
        post_id = payload.replace("movie_", "")
        await _handle_movie_request(message, post_id)
        return

    if payload.startswith("batch_"):
        batch_id = payload.replace("batch_", "")
        await _handle_batch_request(message, batch_id)
        return

    # Regular start
    if message.from_user.id in ADMIN_IDS:
        from handlers.start import menu_handler
        from keyboards.inline import main_menu_kb
        await message.answer(
            "🏠 <b>Admin Menu</b>\n\n"
            "အောက်ပါခလုတ်များကို နှိပ်ပါ။",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
    else:
        await message.answer(
            get_warning_text(),
            parse_mode="HTML",
        )


async def _handle_movie_request(message: Message, post_id: str):
    if not await _require_subscription(message, f"movie_{post_id}"):
        return

    post = await db.get_post(post_id)
    if not post:
        await message.answer(
            "❌ <b>Post မတွေ့ပါ။</b>\n"
            "Link မှားနေနိုင်ပါသည်။",
            parse_mode="HTML",
        )
        return

    if not post.get("movie_file_id"):
        await message.answer(
            "❌ Movie ဖိုင် မရှိပါ။",
            parse_mode="HTML",
        )
        return

    title = post.get("title", "Movie")
    movie_file_id = post["movie_file_id"]
    movie_file_name = post.get("movie_file_name", "movie.mp4")

    await db.increment_user_downloads(message.from_user.id)

    sent_ids = []

    # Send warning first
    warning_msg = await message.answer(
        get_warning_text(),
        parse_mode="HTML",
    )
    sent_ids.append(warning_msg.message_id)

    # Send the movie file
    try:
        file_msg = await _send_media_file(
            message,
            movie_file_id,
            movie_file_name,
            f"🎬 <b>{title}</b>",
        )
        sent_ids.append(file_msg.message_id)
    except Exception as e:
        logging.exception("Failed to send movie file")
        await message.answer(
            f"❌ Movie ဖိုင် ပို့ရန် မအောင်မြင်ပါ:\n{html.escape(str(e))}",
            parse_mode="HTML",
        )
        try:
            await message.bot.delete_message(message.chat.id, warning_msg.message_id)
        except Exception:
            pass
        return

    # Schedule auto-delete (5 min)
    task = asyncio.create_task(_auto_delete(message.bot, message.chat.id, sent_ids, title))
    DELETION_TASKS[message.chat.id] = task

    await message.answer(
        f"⏳ <b>ဤဇာတ်ကားဖိုင်ကို {DELETE_AFTER // 60} မိနစ်အကြာတွင် အလိုအလျောက် ဖျက်ပါမည်။</b>\n\n"
        f"🔄 သိမ်းရန်: ဤဖိုင်ခဲ့အား <b>Saved Messages</b> သို့ Forward လုပ်ပါ။",
        parse_mode="HTML",
    )


async def _handle_batch_request(message: Message, batch_id: str):
    if not await _require_subscription(message, f"batch_{batch_id}"):
        return

    batch = await db.get_batch(batch_id)
    if not batch:
        await message.answer(
            "❌ <b>Batch Link မတွေ့ပါ။</b>\n"
            "Link မှားနေနိုင်ပါသည်။",
            parse_mode="HTML",
        )
        return

    file_ids = batch.get("file_ids", [])
    file_names = batch.get("file_names", [])
    title = batch.get("title", "Batch Files")

    if not file_ids:
        await message.answer(
            "❌ ဖိုင်များ မရှိပါ။",
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"📦 <b>{title}</b>\n\n"
        f"ဖိုင် {len(file_ids)} ခု ပို့နေပါသည်...",
        parse_mode="HTML",
    )

    sent_ids = []
    warning_msg = await message.answer(get_warning_text(), parse_mode="HTML")
    sent_ids.append(warning_msg.message_id)

    for i, fid in enumerate(file_ids):
        try:
            name = file_names[i] if i < len(file_names) else "file"
            msg = await _send_media_file(
                message,
                fid,
                name,
                f"📦 <b>{title}</b>\n📄 ဖိုင် {i+1}/{len(file_ids)}",
            )
            sent_ids.append(msg.message_id)
        except Exception as e:
            logging.exception("Failed to send batch file %s", i)
            try:
                await message.answer(
                    f"❌ ဖိုင် {i+1} <b>{html.escape(name)}</b> ပို့ရန် မအောင်မြင်ပါ:\n"
                    f"{html.escape(str(e))}",
                    parse_mode="HTML",
                )
            except Exception:
                pass

    task = asyncio.create_task(_auto_delete(message.bot, message.chat.id, sent_ids, title))
    DELETION_TASKS[message.chat.id] = task

    await message.answer(
        f"⏳ <b>ဤဖိုင်များကို {DELETE_AFTER // 60} မိနစ်အကြာတွင် အလိုအလျောက် ဖျက်ပါမည်။</b>\n\n"
        f"🔄 သိမ်းရန်: ဤဖိုင်ခဲ့အား <b>Saved Messages</b> သို့ Forward လုပ်ပါ။",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "after_subscribe")
async def after_subscribe(callback: CallbackQuery):
    pending_key = PENDING_REQUESTS.pop(callback.from_user.id, None)
    if not pending_key:
        await callback.answer("✅ Channel ဝင်ပြီးဖြစ်ပါတယ်!")
        return

    request_type = None
    request_id = ""
    if pending_key.startswith("movie_"):
        request_type = "movie"
        request_id = pending_key.replace("movie_", "")
    elif pending_key.startswith("batch_"):
        request_type = "batch"
        request_id = pending_key.replace("batch_", "")

    if request_type == "movie":
        await _handle_movie_request(callback.message, request_id)
    elif request_type == "batch":
        await _handle_batch_request(callback.message, request_id)
    else:
        await callback.answer("❌ မေးခွန်းမှားနေသည်!")
