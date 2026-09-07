import asyncio
import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from config import ADMIN_IDS, DELETE_AFTER, CHANNEL_ID
from database import db
from utils.formatters import get_warning_text, get_deletion_warning_text

router = Router()

# Track pending deletions by message to avoid duplicates and let users manage
DELETION_TASKS = {}


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
        if movie_file_name.lower().endswith((".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v")):
            file_msg = await message.answer_video(
                video=movie_file_id,
                caption=f"🎬 <b>{title}</b>",
                parse_mode="HTML",
            )
        else:
            file_msg = await message.answer_document(
                document=movie_file_id,
                caption=f"🎬 <b>{title}</b>",
                parse_mode="HTML",
            )
        sent_ids.append(file_msg.message_id)
    except Exception as e:
        logging.exception("Failed to send movie file")
        await message.answer(
            f"❌ Movie ဖိုင် ပို့ရန် မအောင်မြင်ပါ:\n{e}",
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
            if name.lower().endswith((".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v")):
                msg = await message.answer_video(
                    video=fid,
                    caption=f"🎬 <b>{title}</b>\n📦 ဖိုင် {i+1}/{len(file_ids)}",
                    parse_mode="HTML",
                )
            else:
                msg = await message.answer_document(
                    document=fid,
                    caption=f"📦 <b>{title}</b>\n📄 ဖိုင် {i+1}/{len(file_ids)}",
                    parse_mode="HTML",
                )
            sent_ids.append(msg.message_id)
        except Exception as e:
            logging.exception("Failed to send batch file %s", i)
            try:
                await message.answer(f"❌ ဖိုင် {i+1} ပို့ရန် မအောင်မြင်ပါ")
            except Exception:
                pass

    task = asyncio.create_task(_auto_delete(message.bot, message.chat.id, sent_ids, title))
    DELETION_TASKS[message.chat.id] = task

    await message.answer(
        f"⏳ <b>ဤဖိုင်များကို {DELETE_AFTER // 60} မိနစ်အကြာတွင် အလိုအလျောက် ဖျက်ပါမည်။</b>\n\n"
        f"🔄 သိမ်းရန်: ဤဖိုင်ခဲ့အား <b>Saved Messages</b> သို့ Forward လုပ်ပါ။",
        parse_mode="HTML",
    )
