# bot.py
import os
import json
import uuid
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

DATA_FILE = "reminders.json"

# ---------- Helpers: load/save ----------
def load_reminders():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def save_reminders(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_reminder(chat_id: int, remind_time: datetime, message: str):
    data = load_reminders()
    r = {
        "id": str(uuid.uuid4()),
        "chat_id": chat_id,
        "time": remind_time.strftime("%Y-%m-%d %H:%M"),
        "message": message
    }
    data.append(r)
    save_reminders(data)
    return r

def remove_reminder_by_id(rem_id: str):
    data = load_reminders()
    data = [r for r in data if r["id"] != rem_id]
    save_reminders(data)

# ---------- Async wait-and-send ----------
async def wait_and_send(app, r):
    try:
        remind_time = datetime.strptime(r["time"], "%Y-%m-%d %H:%M")
    except Exception:
        # invalid format -> remove
        remove_reminder_by_id(r["id"])
        return

    now = datetime.now()
    delay = (remind_time - now).total_seconds()
    if delay <= 0:
        # time passed -> remove without sending
        remove_reminder_by_id(r["id"])
        return

    await asyncio.sleep(delay)
    try:
        await app.bot.send_message(chat_id=r["chat_id"], text=f"🔔 Nhắc nè: {r['message']}")
    except Exception as e:
        # gửi lỗi thì vẫn xóa để tránh lặp vô hạn
        pass
    remove_reminder_by_id(r["id"])

# ---------- Command handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hey! Tớ là Text2 Reminder 💫\n"
        "Dùng /noti YYYY-MM-DD HH:MM nội_dung để tạo nhắc 1 lần.\n"
        "Ví dụ: /noti 2025-11-05 14:30 họp nhóm")
    
async def noti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # cú pháp: /noti YYYY-MM-DD HH:MM nội_dung...
    try:
        if len(context.args) < 3:
            raise ValueError("Thiếu tham số")
        date_str = context.args[0]
        time_str = context.args[1]
        message = " ".join(context.args[2:])
        remind_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        now = datetime.now()
        delay = (remind_time - now).total_seconds()
        if delay <= 0:
            await update.message.reply_text("⏰ Thời gian đã qua rồi. Vui lòng chọn thời gian tương lai.")
            return

        r = add_reminder(update.effective_chat.id, remind_time, message)
        # Tạo task để chờ và gửi ngay (khi bot đang chạy)
        asyncio.create_task(wait_and_send(context.application, r))
        await update.message.reply_text(f"✅ Đã lưu nhắc: \"{message}\" lúc {remind_time.strftime('%H:%M %d/%m/%Y')}\nID: {r['id']}")
    except Exception:
        await update.message.reply_text("Sai cú pháp! Dùng: /noti YYYY-MM-DD HH:MM nội_dung\nVí dụ: /noti 2025-11-05 14:30 họp nhóm")

async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_reminders()
    chat_id = update.effective_chat.id
    user_rem = [r for r in data if r["chat_id"] == chat_id]
    if not user_rem:
        await update.message.reply_text("Bạn không có nhắc hẹn nào đang chờ.")
        return
    lines = []
    for r in user_rem:
        lines.append(f"ID: {r['id']}\n⏰ {r['time']}\n🔹 {r['message']}\n")
    await update.message.reply_text("\n".join(lines))

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /cancel <id>
    try:
        rem_id = context.args[0]
        data = load_reminders()
        existed = any(r for r in data if r["id"] == rem_id and r["chat_id"] == update.effective_chat.id)
        if not existed:
            await update.message.reply_text("Không tìm thấy ID tương ứng trong nhắc hẹn của bạn.")
            return
        remove_reminder_by_id(rem_id)
        await update.message.reply_text("Đã huỷ nhắc hẹn.")
    except Exception:
        await update.message.reply_text("Dùng: /cancel ID (ví dụ: /cancel 123e4567-...)")

# ---------- On startup: khôi phục các reminders ----------
async def recover_reminders(app):
    data = load_reminders()
    now = datetime.now()
    for r in data:
        try:
            remind_time = datetime.strptime(r["time"], "%Y-%m-%d %H:%M")
        except:
            # if invalid, drop it
            remove_reminder_by_id(r["id"])
            continue
        delay = (remind_time - now).total_seconds()
        if delay > 0:
            asyncio.create_task(wait_and_send(app, r))
        else:
            # quá hạn -> xóa
            remove_reminder_by_id(r["id"])

# ---------- Main ----------
async def main():
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("ERROR: BOT_TOKEN không được tìm thấy trong biến môi trường.")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("noti", noti))
    app.add_handler(CommandHandler("list", list_reminders))
    app.add_handler(CommandHandler("cancel", cancel))

    # recover trước khi chạy polling
    await recover_reminders(app)
    print("✅ Bot đang chạy và đã khôi phục nhắc hẹn cũ (nếu có).")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
