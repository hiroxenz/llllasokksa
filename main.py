import os
import requests
import tempfile
from datetime import datetime
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

PIXELCUT_URL = "https://api2.pixelcut.app/image/upscale/v1"
HEADERS = {
    'authority': 'api2.pixelcut.app',
    'accept': 'application/json',
    'origin': 'https://www.pixelcut.ai',
    'referer': 'https://www.pixelcut.ai/',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
    'x-client-version': 'web',
    'x-locale': 'en',
}

MENU_IMAGE_URL = "https://raw.githubusercontent.com/hiroxenz/llllasokksa/refs/heads/main/photo_2025-08-14_15-26-37.jpg"

waiting_for_image = set()

# ===== ADMIN CHECK =====
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# ===== COMMAND HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 Anda tidak memiliki izin untuk menggunakan bot ini.")
        return
    await menu(update, context)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 Anda tidak memiliki izin untuk menggunakan bot ini.")
        return

    caption = (
        "╭━━━『 📜 *Main Menu* 』━━━╮\n"
        "┣ 🎯 /upscaling — *Perbesar & tingkatkan kualitas gambar*\n"
        "┣ 📌 /menu — *Tampilkan menu ini*\n"
        "┣ 🏁 /start — *Mulai bot*\n"
        "╰━━━━━━━━━━━━━━━━━━╯"
    )

    await update.message.reply_photo(photo=MENU_IMAGE_URL, caption=caption, parse_mode=ParseMode.MARKDOWN)

async def start_upscaling(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 Anda tidak memiliki izin untuk menggunakan bot ini.")
        return
    waiting_for_image.add(update.effective_user.id)
    await update.message.reply_text("🔼 *Kirim foto atau link gambar yang ingin di-upscale.*", parse_mode=ParseMode.MARKDOWN)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("🚫 Anda tidak memiliki izin untuk menggunakan bot ini.")
        return

    if user_id not in waiting_for_image:
        return

    if update.message.text and update.message.text.startswith("http"):
        await update.message.reply_text("⏳ *Mengunduh gambar dari link...*", parse_mode=ParseMode.MARKDOWN)
        try:
            img_data = requests.get(update.message.text, timeout=10).content
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(img_data)
                tmp_path = tmp.name
            await upscale_and_send(update, tmp_path)
        except Exception as e:
            await update.message.reply_text(f"❌ *Gagal mengunduh gambar:* `{e}`", parse_mode=ParseMode.MARKDOWN)

    elif update.message.photo:
        await update.message.reply_text("⏳ *Mengunggah gambar...*", parse_mode=ParseMode.MARKDOWN)
        file_id = update.message.photo[-1].file_id
        photo_file = await context.bot.get_file(file_id)
        tmp_path = tempfile.mktemp(suffix=".jpg")
        await photo_file.download_to_drive(tmp_path)
        await upscale_and_send(update, tmp_path)

    else:
        await update.message.reply_text("❌ *Harap kirim foto atau link gambar yang valid.*", parse_mode=ParseMode.MARKDOWN)

async def upscale_and_send(update: Update, file_path: str):
    try:
        files = {
            'image': ('myimage.png', open(file_path, 'rb'), 'image/png'),
            'scale': (None, '2'),
        }
        response = requests.post(PIXELCUT_URL, headers=HEADERS, files=files)
        if response.status_code == 200:
            result_url = response.json().get('result_url')
            if result_url:
                await update.message.reply_photo(photo=result_url, caption="✅ *Gambar berhasil di-upscale!*", parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text("❌ *Gagal mendapatkan URL hasil upscale.*", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(f"❌ *Gagal memproses gambar (status {response.status_code}).*", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ *Error:* `{e}`", parse_mode=ParseMode.MARKDOWN)
    finally:
        waiting_for_image.discard(update.effective_user.id)

# ===== AUTO MESSAGE MORNING & EVENING =====
async def auto_message(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    if now.hour == 7:
        text = "🌅 *Selamat Pagi!* Semoga harimu penuh semangat 🚀"
        await context.bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode=ParseMode.MARKDOWN)
    elif now.hour == 17:
        text = "🌇 *Selamat Sore!* Waktunya istirahat ✨"
        await context.bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode=ParseMode.MARKDOWN)

# ===== MAIN =====
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("upscaling", start_upscaling))
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    app.job_queue.run_repeating(auto_message, interval=3600, first=0)

    print("🚀 Bot berjalan...")
    app.run_polling()
