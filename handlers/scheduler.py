import asyncio
import logging
import uuid

from aiogram import Bot
from database import db
from handlers.post import _send_post_to_channel


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

    await _send_post_to_channel(bot, title, poster_file_ids, telegraph_url, deep_link, script_text)

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