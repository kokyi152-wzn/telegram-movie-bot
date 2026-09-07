import asyncio
import logging
import uuid

from aiogram import Bot
from config import CHANNEL_ID, BOT_TOKEN
from database import db
from utils.formatters import format_post_caption
from keyboards.inline import post_action_kb


async def _build_and_send_post(bot: Bot, post_data):
    title = post_data.get("title", "Movie")
    poster_file_ids = post_data.get("poster_file_ids", [])
    telegraph_url = post_data.get("telegraph_url", "")
    script_text = post_data.get("script_text", "")
    movie_file_id = post_data.get("movie_file_id", "")
    movie_file_name = post_data.get("movie_file_name", "movie.mp4")

    post_id = str(uuid.uuid4())[:8]

    # Persist the post so its deep link works
    await db.save_post(
        post_id=post_id,
        title=title,
        script_text=script_text,
        telegraph_url=telegraph_url,
        poster_file_ids=poster_file_ids,
        movie_file_id=movie_file_id,
        movie_file_name=movie_file_name,
    )

    deep_link = f"https://t.me/{bot.username}?start=movie_{post_id}"

    caption = format_post_caption(title, script_summary=script_text)
    kb = post_action_kb(None, telegraph_url, deep_link)

    from aiogram.types import InputMediaPhoto
    try:
        if len(poster_file_ids) == 1:
            await bot.send_photo(
                CHANNEL_ID,
                photo=poster_file_ids[0],
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
        elif len(poster_file_ids) > 1:
            media = []
            for i, fid in enumerate(poster_file_ids):
                if i == 0:
                    media.append(InputMediaPhoto(media=fid, caption=caption, parse_mode="HTML"))
                else:
                    media.append(InputMediaPhoto(media=fid))
            await bot.send_media_group(CHANNEL_ID, media)
            await bot.send_message(CHANNEL_ID, caption, parse_mode="HTML", reply_markup=kb)
        else:
            await bot.send_message(CHANNEL_ID, caption, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logging.exception("Failed to send scheduled post: %s", title)
        raise

    return deep_link


async def schedule_worker(bot: Bot):
    """Runs periodically, sends due scheduled posts."""
    while True:
        try:
            pending = await db.get_pending_schedules()
            for sched in pending:
                try:
                    await _build_and_send_post(bot, sched.get("post_data", {}))
                    await db.mark_schedule_sent(sched["schedule_id"])
                    logging.info("Scheduled post sent: %s", sched.get("title"))
                except Exception as e:
                    logging.warning("Failed schedule send %s: %s", sched.get("title"), e)
                    # Don't mark as sent to retry next cycle
        except Exception as e:
            logging.exception("Schedule worker error: %s", e)

        await asyncio.sleep(30)
