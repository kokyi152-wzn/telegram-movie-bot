from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from database import db
from config import ADMIN_IDS
from keyboards.inline import main_menu_kb
from utils.formatters import get_warning_text

router = Router()


@router.message(Command("menu"))
async def menu_handler(message: Message):
    if message.from_user.id in ADMIN_IDS:
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


@router.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "📖 <b>အသုံးပြုပုံ</b>\n\n"
        "Admin များ: /menu ဖြင့် Admin Menu ထဲ ဝင်နိုင်ပါသည်။\n"
        "User များ: Channel ထဲမှ post များမှ ဇာတ်ကားရယူနိုင်ပါသည်။",
        parse_mode="HTML",
    )


@router.message(Command("cancel"))
async def cancel_command(message: Message):
    from handlers.post import POST_STATES, PHOTO_TASKS
    from handlers.admin import ADMIN_STATES
    task = PHOTO_TASKS.pop(message.from_user.id, None)
    if task and not task.done():
        task.cancel()
    POST_STATES.pop(message.from_user.id, None)
    ADMIN_STATES.pop(message.from_user.id, None)
    await message.answer(
        "❌ ပယ်ဖျက်ပြီးပါပြီ။",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data == "admin_menu")
async def admin_menu_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    await callback.message.edit_text(
        "🏠 <b>Admin Menu</b>\n\n"
        "အောက်ပါခလုတ်များကို နှိပ်ပါ။",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_post")
async def cancel_post(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    from handlers.post import POST_STATES, PHOTO_TASKS
    task = PHOTO_TASKS.pop(callback.from_user.id, None)
    if task and not task.done():
        task.cancel()
    POST_STATES.pop(callback.from_user.id, None)
    await _replace_with_menu(callback)
    await callback.answer("❌ ပယ်ဖျက်ပြီး")


async def _replace_with_menu(callback: CallbackQuery):
    """Edit the message to the admin menu (handles photo with caption)."""
    text = "🏠 <b>Admin Menu</b>\n\nအောက်ပါခလုတ်များကို နှိပ်ပါ။"
    from aiogram.exceptions import TelegramBadRequest
    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
    except TelegramBadRequest:
        try:
            await callback.message.edit_caption(
                caption=text,
                parse_mode="HTML",
                reply_markup=main_menu_kb(),
            )
        except TelegramBadRequest:
            await callback.message.answer(
                text,
                parse_mode="HTML",
                reply_markup=main_menu_kb(),
            )
