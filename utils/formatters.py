import html
from datetime import datetime


def format_post_caption(title, script_summary="", genres="", year="", rating=""):
    title_line = f"🎬 <b>{html.escape(title)}</b>"

    meta = []
    if year:
        meta.append(f"📅 <b>နှစ်:</b> {year}")
    if genres:
        meta.append(f"🎭 <b>အမျိုးအစား:</b> {genres}")
    if rating:
        meta.append(f"⭐ <b>အဆင့်:</b> {rating}")

    sections = ["📝 <b>ဇာတ်ကားအကြောင်း</b>", title_line]
    if meta:
        sections.append("\n".join(meta))
    if script_summary:
        summary = html.escape(script_summary[:500])
        if len(script_summary) > 500:
            summary += "..."
        sections.append(summary)
    return "\n\n".join(sections)


def get_warning_text():
    return (
        "⚠️ <b>⚠️ ⚠️ အရေးကြီးပါတယ် ⚠️ ⚠️ ⚠️</b>\n\n"
        "ဤ<b>ရုပ်ရှင်ဖိုင်များ/ဗီဒီယိုများ</b>ကို "
        "<b>5 မိနစ်</b>အတွင်း "
        "(<b>မူပိုင်ခွင့်ပြဿနာများကြောင့်</b>) ဖျက်ပါမည်။\n\n"
        "ကျေးဇူးပြု၍ ဤဖိုင်များ/ဗီဒီယိုများအားလုံးကို "
        "သင်၏ <b>Saved Messages</b> များသို့ "
        "<b>Forward လုပ်ပြီး</b> "
        "ထိုနေရာတွင် ဇာတ်ကားအား ကြည့်ရှုပါ။\n\n"
        "ကျွန်ုပ်၏ Channel ကို လာရောက်အားပေးမှုအတွက် "
        "ကျေးဇူးအထူးတင်ပါတယ် 🙏🙏🙏!!"
    )


def get_deletion_warning_text(title=""):
    return (
        f"⚠️ <b>⚠️ ⚠️ အရေးကြီးပါတယ် ⚠️ ⚠️ ⚠️</b>\n\n"
        f"🎬 <b>{html.escape(title)}</b> ဇာတ်ကားဖိုင်ကို "
        f"<b>ဖျက်ပြီးပါပြီ။</b>\n\n"
        f"ဤဖိုင်များ/ဗီဒီယိုများကို "
        f"<b>5 မိနစ်</b>အတွင်း "
        f"(<b>မူပိုင်ခွင့်ပြဿနာများကြောင့်</b>) "
        f"ဖျက်ပါမည်။\n\n"
        f"ကျေးဇူးပြု၍ ဤဖိုင်များ/ဗီဒီယိုများအားလုံးကို "
        f"သင်၏ <b>Saved Messages</b> များသို့ "
        f"<b>Forward လုပ်ပြီး</b> "
        f"ထိုနေရာတွင် ဇာတ်ကားအား ကြည့်ရှုပါ။\n\n"
        f"🔁 <b>ဇာတ်ကားဖိုင်ကို ပြန်လည်ရယူနိုင်ပါသည်</b> —\n"
        f"အောက်ပါ ခလုတ်ကို နှိပ်ပါ 👇\n\n"
        f"ကျွန်ုပ်၏ Channel ကို လာရောက်အားပေးမှုအတွက် "
        f"ကျေးဇူးအထူးတင်ပါတယ် 🙏🙏🙏!!"
    )


def format_admin_stats(posts=0, users=0, scheduled=0, batch_links=0):
    return (
        f"📊 <b>Bot Statistics</b>\n\n"
        f"🎬 Posts: {posts}\n"
        f"👥 Users: {users}\n"
        f"📅 Scheduled: {scheduled}\n"
        f"🔗 Batch Links: {batch_links}"
    )


def format_post_list(posts):
    if not posts:
        return "📭 ပိုစ် မရှိသေးပါ။"
    text = "📋 <b>ပိုစ်စာရင်း:</b>\n\n"
    for i, p in enumerate(posts, 1):
        title = p.get("title", "Untitled")
        created = p.get("created_at", "")
        if isinstance(created, datetime):
            created = created.strftime("%Y-%m-%d %H:%M")
        text += f"{i}. 🎬 {title}\n   📅 {created}\n\n"
    return text


def format_schedule_list(schedules):
    if not schedules:
        return "📭 Schedule မရှိသေးပါ။"
    text = "📅 <b>Schedule စာရင်း:</b>\n\n"
    for i, s in enumerate(schedules, 1):
        title = s.get("title", "Untitled")
        send_at = s.get("send_at", "")
        if isinstance(send_at, datetime):
            send_at = send_at.strftime("%Y-%m-%d %H:%M")
        status = "✅ ပို့ပြီး" if s.get("sent") else "⏳ စောင့်ဆိုင်း"
        text += f"{i}. 🎬 {title}\n   📅 {send_at} | {status}\n\n"
    return text
