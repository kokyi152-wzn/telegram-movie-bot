from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🎬 ပိုစ်အသစ်", callback_data="new_post")
    builder.button(text="🔗 Video → Deep Link", callback_data="video_deeplink")
    builder.button(text="📦 Batch Link ထုတ်ရန်", callback_data="batch_link")
    builder.button(text="📊 စာရင်းအင်း", callback_data="admin_stats")
    builder.button(text="🔄 ပြန်လွှင့်ခြင်း", callback_data="resend")
    builder.button(text="📅 Schedule ပြုလုပ်ရန်", callback_data="new_schedule")
    builder.button(text="📋 Schedule စာရင်း", callback_data="schedule_list")
    builder.button(text="🗑 Schedule ဖျက်ရန်", callback_data="delete_schedule")
    builder.button(text="🗑 ဖိုင်ဖျက်ရန် (ID)", callback_data="delete_file_id")
    builder.button(text="🗑 ဖိုင်အားလုံးဖျက်ရန်", callback_data="delete_all_files")
    builder.button(text="🔧 Maintenance mode ဖွင့်", callback_data="maintenance_on")
    builder.button(text="🔧 Maintenance mode ပိတ်", callback_data="maintenance_off")
    builder.adjust(2, 2, 2, 2, 2, 1, 1)
    return builder.as_markup()


def post_action_kb(post_id, telegraph_url="", movie_deeplink="") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if telegraph_url:
        builder.button(
            text="📝 ဇာတ်ညွှန်းအပြည့်အစုံဖတ်ရန်",
            url=telegraph_url,
        )
    if movie_deeplink:
        builder.button(
            text="🎬 ဇာတ်ကားရယူရန်",
            url=movie_deeplink,
        )
    builder.adjust(1)
    return builder.as_markup()


def post_confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ ပို့မည်", callback_data="confirm_post")
    builder.button(text="❌ ပယ်ဖျက်မည်", callback_data="cancel_post")
    builder.adjust(2)
    return builder.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ ပယ်ဖျက်မည်", callback_data="cancel_post")
    builder.adjust(1)
    return builder.as_markup()


def admin_back_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Admin Menu", callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()


def delete_confirm_kb(post_id) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ ဖျက်မည်", callback_data=f"confirm_del_post:{post_id}")
    builder.button(text="❌ မဖျက်နဲ့", callback_data="admin_menu")
    builder.adjust(2)
    return builder.as_markup()


def schedule_confirm_kb(schedule_id) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ ဖျက်မည်", callback_data=f"confirm_del_schedule:{schedule_id}")
    builder.button(text="❌ မဖျက်နဲ့", callback_data="admin_menu")
    builder.adjust(2)
    return builder.as_markup()


def back_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Menu", callback_data="admin_menu")
    return builder.as_markup()


def batch_list_kb(batches) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for b in batches:
        builder.button(
            text=f"📦 {b.get('title', 'Untitled')}",
            callback_data=f"batch_detail:{b['batch_id']}",
        )
    builder.button(text="🏠 Admin Menu", callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()


def maintenance_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔧 Maintenance mode ဖွင့်", callback_data="maintenance_on")
    builder.button(text="🔧 Maintenance mode ပိတ်", callback_data="maintenance_off")
    builder.button(text="🏠 Admin Menu", callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()


def subscribe_kb(channel_url="") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if channel_url:
        builder.button(text="📢 Channel ဝင်ရန်", url=channel_url)
    builder.button(text="✅ ဝင်ပြီးပါပြီ", callback_data="after_subscribe")
    builder.adjust(1)
    return builder.as_markup()
