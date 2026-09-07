import asyncio
import html
import logging
import uuid
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_IDS
from database import db
from keyboards.inline import main_menu_kb, admin_back_kb, delete_confirm_kb, schedule_confirm_kb, batch_list_kb, back_main_kb
from utils.formatters import format_admin_stats, format_post_list, format_schedule_list

router = Router()

ADMIN_STATES = {}

STATE_IDLE = "idle"
STATE_BATCH_COLLECT = "batch_collect"
STATE_BATCH_TITLE = "batch_title"
STATE_DELETE_FILE = "delete_file"
STATE_SCHEDULE_TIME = "schedule_time"
STATE_SCHEDULE_DELETE = "schedule_delete"


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    stats = await db.get_stats()
    text = format_admin_stats(**stats)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_kb())
    await callback.answer("📊 စာရင်းအင်း")


@router.callback_query(F.data == "resend")
async def resend_posts(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    posts = await db.get_all_posts(20)
    if not posts:
        await callback.message.edit_text(
            "📭 <b>ပြန်လွှင့်ရန် ပိုစ် မရှိပါ။</b>",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
        await callback.answer()
        return
    builder = InlineKeyboardBuilder()
    for p in posts:
        builder.button(
            text=f"🔄 {p['title'][:40]}",
            callback_data=f"resend_post:{p['post_id']}",
        )
    builder.button(text="🏠 Admin Menu", callback_data="admin_menu")
    builder.adjust(1)
    await callback.message.edit_text(
        "🔄 <b>ပြန်လွှင့်လိုသော ပိုစ် ရွေးပါ:</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer("🔄 ပြန်လွှင့်ခြင်း")


@router.callback_query(F.data.startswith("resend_post:"))
async def resend_post(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    post_id = callback.data.split(":")[1]
    post = await db.get_post(post_id)
    if not post:
        await callback.answer("❌ Post မတွေ့ပါ!", show_alert=True)
        return

    from handlers.post import _send_post_to_channel, format_post_caption
    from config import CHANNEL_ID

    post_id_str = str(uuid.uuid4())[:8]
    deep_link = f"https://t.me/{callback.bot.username}?start=movie_{post_id_str}"

    await _send_post_to_channel(
        callback.bot,
        post["title"],
        post.get("poster_file_ids", []),
        post.get("telegraph_url", ""),
        deep_link,
    )
    await callback.answer("✅ ပြန်လွှင့်ပြီးပါပြီ!", show_alert=True)


@router.callback_query(F.data == "delete_all_files")
async def delete_all_files(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    posts = await db.get_all_posts()
    for p in posts:
        await db.delete_post(p["post_id"])
    await callback.message.edit_text(
        "🗑 <b>ဖိုင်အားလုံး ဖျက်ပြီးပါပြီ!</b>\n\n"
        f"စုစုပေါင်း {len(posts)} ခု ဖျက်လိုက်သည်။",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )
    await callback.answer("🗑 ဖျက်ပြီး")


@router.callback_query(F.data == "delete_file_id")
async def delete_file_id(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    posts = await db.get_all_posts()
    if not posts:
        await callback.message.edit_text(
            "📭 <b>ဖျက်ရန် ပိုစ် မရှိပါ။</b>",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
        await callback.answer()
        return
    builder = InlineKeyboardBuilder()
    for p in posts:
        builder.button(
            text=f"🗑 {p['title'][:40]}",
            callback_data=f"del_post:{p['post_id']}",
        )
    builder.button(text="🏠 Admin Menu", callback_data="admin_menu")
    builder.adjust(1)
    await callback.message.edit_text(
        "🗑 <b>ဖျက်လိုသော ပိုစ် ရွေးပါ:</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer("🗑 ဖိုင်ဖျက်ရန် (ID)")


@router.callback_query(F.data.startswith("del_post:"))
async def del_post(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    post_id = callback.data.split(":")[1]
    post = await db.get_post(post_id)
    if not post:
        await callback.answer("❌ Post မတွေ့ပါ!", show_alert=True)
        return
    await callback.message.edit_text(
        f"⚠️ <b>{html.escape(post['title'])}</b> ကို ဖျက်မှာလား?",
        parse_mode="HTML",
        reply_markup=delete_confirm_kb(post_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del_post:"))
async def confirm_del_post(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    post_id = callback.data.split(":")[1]
    post = await db.get_post(post_id)
    if post:
        await db.delete_post(post_id)
        await callback.message.edit_text(
            f"✅ <b>{html.escape(post['title'])}</b> ကို ဖျက်ပြီးပါပြီ။",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
    else:
        await callback.message.edit_text(
            "❌ Post မတွေ့ပါ။",
            reply_markup=main_menu_kb(),
        )
    await callback.answer("✅ ဖျက်ပြီး")


# ---------------- Batch Link ----------------

@router.callback_query(F.data == "batch_link")
async def batch_link(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    state = {
        "admin_id": callback.from_user.id,
        "state": STATE_BATCH_COLLECT,
        "file_ids": [],
        "file_names": [],
        "title": None,
    }
    ADMIN_STATES[callback.from_user.id] = state
    await callback.message.answer(
        "📦 <b>Batch Link ထုတ်ရန်</b>\n\n"
        "ဖိုင်များ <b>အများအပြား</b> ပို့ပါ\n"
        "(Video, Document, Photo အားလုံး)\n\n"
        "ပို့ပြီးပါက <b>/done</b> ရိုက်ပါ\n"
        "ပယ်ဖျက်ရန်က <b>/cancel</b>",
        parse_mode="HTML",
    )
    await callback.answer("📦 Batch Link")


@router.message(F.photo | F.document | F.video, lambda m: m.from_user and m.from_user.id in ADMIN_STATES)
async def collect_batch_files(message: Message):
    state = ADMIN_STATES.get(message.from_user.id)
    if not state or state["state"] != STATE_BATCH_COLLECT:
        return

    file_id = None
    file_name = ""
    if message.photo:
        file_id = message.photo[-1].file_id
        file_name = "photo.jpg"
    elif message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or "document"
    elif message.video:
        file_id = message.video.file_id
        file_name = message.video.file_name or "video.mp4"

    if not file_id:
        return

    state["file_ids"].append(file_id)
    state["file_names"].append(file_name)
    await message.answer(
        f"✅ ဖိုင် {len(state['file_ids'])} ခု လက်ခံပြီးပါပြီ။\n"
        f"/done ရိုက်ပြီး ဆက်လုပ်ပါ",
    )


@router.message(lambda m: m.from_user and m.from_user.id in ADMIN_STATES and m.text == "/done")
async def batch_done(message: Message):
    state = ADMIN_STATES.get(message.from_user.id)
    if not state or state["state"] != STATE_BATCH_COLLECT:
        return
    if not state["file_ids"]:
        await message.answer("⚠️ ဖိုင်များ မပို့ရသေးပါ!")
        return
    state["state"] = STATE_BATCH_TITLE
    await message.answer(
        "📝 <b>Batch အတွက် နာမည် ရိုက်ထည့်ပါ:</b>",
        parse_mode="HTML",
    )


@router.message(lambda m: m.from_user and m.from_user.id in ADMIN_STATES and m.text)
async def batch_title_handler(message: Message):
    state = ADMIN_STATES.get(message.from_user.id)
    if not state:
        return
    if state["state"] != STATE_BATCH_TITLE:
        return
    if message.text.startswith("/"):
        return

    state["title"] = message.text.strip()
    batch_id = str(uuid.uuid4())[:8]
    await db.save_batch(batch_id, state["title"], state["file_ids"], state["file_names"])

    deep_link = f"https://t.me/{message.bot.username}?start=batch_{batch_id}"
    link_msg = f"✅ <b>Batch Link ရပြီ!</b>\n\n"
    link_msg += f"📦 <b>{html.escape(state['title'])}</b>\n"
    link_msg += f"📄 ဖိုင်: {len(state['file_ids'])} ခု\n\n"
    link_msg += f"🔗 <b>Link:</b>\n<code>{deep_link}</code>"

    ADMIN_STATES.pop(message.from_user.id, None)
    await message.answer(link_msg, parse_mode="HTML", reply_markup=main_menu_kb())


# ---------------- Schedule ----------------

@router.callback_query(F.data == "new_schedule")
async def new_schedule(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    posts = await db.get_all_posts(20)
    if not posts:
        await callback.message.edit_text(
            "📭 <b>Schedule လုပ်ရန် ပိုစ် မရှိပါ။\n\n"
            "အရင်ဆုံး ပိုစ်အသစ် ဖန်တီးပါ။</b>",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
        await callback.answer()
        return
    builder = InlineKeyboardBuilder()
    for p in posts:
        builder.button(
            text=f"📅 {p['title'][:40]}",
            callback_data=f"sch_post:{p['post_id']}",
        )
    builder.button(text="🏠 Admin Menu", callback_data="admin_menu")
    builder.adjust(1)
    await callback.message.edit_text(
        "📅 <b>Schedule လုပ်လိုသော ပိုစ် ရွေးပါ:</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer("📅 Schedule")


@router.callback_query(F.data.startswith("sch_post:"))
async def sch_post(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    post_id = callback.data.split(":")[1]
    post = await db.get_post(post_id)
    if not post:
        await callback.answer("❌ Post မတွေ့ပါ!", show_alert=True)
        return
    ADMIN_STATES[callback.from_user.id] = {
        "admin_id": callback.from_user.id,
        "state": STATE_SCHEDULE_TIME,
        "post": post,
    }
    now = datetime.utcnow() + timedelta(hours=7)
    await callback.message.answer(
        f"📅 <b>Schedule ပို့မည့်အချိန် ရိုက်ထည့်ပါ:</b>\n\n"
        f"🎬 {html.escape(post['title'])}\n\n"
        f"အချိန် format: <code>YYYY-MM-DD HH:MM</code>\n"
        f"ဥပမာ: <code>2026-09-08 20:30</code> (မြန်မာစံတော်ချိန်)\n\n"
        f"လက်ရှိအချိန်: {now.strftime('%Y-%m-%d %H:%M')}",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(lambda m: m.from_user and m.from_user.id in ADMIN_STATES and m.text and not m.text.startswith("/"))
async def schedule_time_handler(message: Message):
    state = ADMIN_STATES.get(message.from_user.id)
    if not state or state["state"] != STATE_SCHEDULE_TIME:
        return

    text = message.text.strip()
    try:
        # Parse in Myanmar time (UTC+7)
        naive = datetime.strptime(text, "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer(
            "❌ <b>Format မှားသည်။</b>\n"
            "ဥပမာ: <code>2026-09-08 20:30</code>",
            parse_mode="HTML",
        )
        return

    # Convert Myanmar time (UTC+7) to UTC
    utc_send_at = naive - timedelta(hours=7)

    schedule_id = str(uuid.uuid4())[:8]
    post = state["post"]

    post_data = {
        "post_id": post["post_id"],
        "title": post["title"],
        "poster_file_ids": post.get("poster_file_ids", []),
        "telegraph_url": post.get("telegraph_url", ""),
        "movie_file_id": post.get("movie_file_id", ""),
    }

    await db.save_schedule(schedule_id, post["title"], post_data, utc_send_at)
    ADMIN_STATES.pop(message.from_user.id, None)

    await message.answer(
        f"✅ <b>Schedule ပြုလုပ်ပြီးပါပြီ!</b>\n\n"
        f"🎬 <b>{html.escape(post['title'])}</b>\n"
        f"📅 ပို့မည့်အချိန်: <code>{text}</code> (မြန်မာစံတော်ချိန်)",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data == "schedule_list")
async def schedule_list(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    schedules = await db.get_all_schedules()
    text = format_schedule_list(schedules)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_kb())
    await callback.answer("📋 Schedule စာရင်း")


@router.callback_query(F.data == "delete_schedule")
async def delete_schedule(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    schedules = await db.get_all_schedules()
    if not schedules:
        await callback.message.edit_text(
            "📭 <b>Schedule မရှိပါ။</b>",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
        await callback.answer()
        return
    builder = InlineKeyboardBuilder()
    for s in schedules:
        send_at = s.get("send_at", "")
        if isinstance(send_at, datetime):
            send_at = (send_at + timedelta(hours=7)).strftime("%m-%d %H:%M")
        status = "✅" if s.get("sent") else "⏳"
        builder.button(
            text=f"🗑 {status} {s['title'][:30]} [{send_at}]",
            callback_data=f"del_schedule:{s['schedule_id']}",
        )
    builder.button(text="🏠 Admin Menu", callback_data="admin_menu")
    builder.adjust(1)
    await callback.message.edit_text(
        "🗑 <b>ဖျက်လိုသော Schedule ရွေးပါ:</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer("🗑 Schedule ဖျက်ရန်")


@router.callback_query(F.data.startswith("del_schedule:"))
async def del_schedule(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    schedule_id = callback.data.split(":")[1]
    await callback.message.edit_text(
        f"⚠️ ဒီ Schedule ကို ဖျက်မှာလား? (<code>{schedule_id}</code>)",
        parse_mode="HTML",
        reply_markup=schedule_confirm_kb(schedule_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del_schedule:"))
async def confirm_del_schedule(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    schedule_id = callback.data.split(":")[1]
    await db.delete_schedule(schedule_id)
    await callback.message.edit_text(
        "✅ <b>Schedule ဖျက်ပြီးပါပြီ။</b>",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )
    await callback.answer("✅ ဖျက်ပြီး")


# ---------------- Maintenance ----------------

@router.callback_query(F.data == "maintenance_on")
async def maintenance_on(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    await db.set_maintenance(True)
    await callback.message.edit_text(
        "🔧 <b>Maintenance mode ဖွင့်ပြီးပါပြီ။</b>\n\n"
        "Users များသည် bot ကို အသုံးပြုနိုင်တော့မည်မဟုတ်ပါ။",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )
    await callback.answer("🔧 Maintenance ON")


@router.callback_query(F.data == "maintenance_off")
async def maintenance_off(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    await db.set_maintenance(False)
    await callback.message.edit_text(
        "✅ <b>Maintenance mode ပိတ်ပြီးပါပြီ။</b>\n\n"
        "Users များ အသုံးပြုနိုင်ပါပြီ။",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )
    await callback.answer("🔧 Maintenance OFF")
