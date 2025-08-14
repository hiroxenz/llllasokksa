import os
import asyncio
import requests
from datetime import datetime, timedelta
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler

# Ambil dari Railway env
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

PIXELCUT_URL = "https://api2.pixelcut.app/image/upscale/v1"
PIXELCUT_HEADERS = {
    'authority': 'api2.pixelcut.app',
    'accept': 'application/json',
    'origin': 'https://www.pixelcut.ai',
    'referer': 'https://www.pixelcut.ai/',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
    'x-client-version': 'web',
    'x-locale': 'en',
}

WAITING_IMAGE = 1

# ===============================
# COMMAND START
# ===============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("✨ Selamat datang! Ketik /menu untuk melihat fitur bot ini.")

# ===============================
# COMMAND MENU
# ===============================
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    menu_text = (
        "📜 *Daftar Menu Bot:*\n\n"
        "1️⃣ /upscaling – Upscale foto hingga 2x kualitas aslinya\n"
        "2️⃣ (fitur lainnya bisa ditambahkan di sini)\n\n"
        "💡 *Tips:* Gunakan menu dengan bijak."
    )
    photo_url = "https://raw.githubusercontent.com/hiroxenz/llllasokksa/refs/heads/main/photo_2025-08-14_15-26-37.jpg"
    await update.message.reply_photo(photo=photo_url, caption=menu_text, parse_mode="Markdown")

# ===============================
# COMMAND UPSCALING
# ===============================
async def upscaling(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("📤 Silakan kirim foto atau link foto yang ingin di-*upscale*.")
    return WAITING_IMAGE

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    image_url = None
    file_data = None

    if update.message.photo:  # Jika user kirim gambar langsung
        file_id = update.message.photo[-1].file_id
        new_file = await context.bot.get_file(file_id)
        file_data = requests.get(new_file.file_path).content
    elif update.message.text and update.message.text.startswith("http"):
        image_url = update.message.text
        file_data = requests.get(image_url).content

    if not file_data:
        await update.message.reply_text("❌ Gagal membaca gambar. Pastikan kirim foto atau link yang valid.")
        return ConversationHandler.END

    # Kirim ke Pixelcut API
    files = {
        'image': ('image.png', file_data, 'image/png'),
        'scale': (None, '2'),
    }
    await update.message.reply_text("⏳ Memproses *upscaling*, mohon tunggu...", parse_mode="Markdown")
    resp = requests.post(PIXELCUT_URL, headers=PIXELCUT_HEADERS, files=files)
    try:
        url_image = resp.json()['result_url']
        await update.message.reply_photo(photo=url_image, caption="✅ *Upscaling selesai!*", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Gagal memproses gambar.\nError: {e}")

    return ConversationHandler.END

# ===============================
# AUTO MESSAGE TANPA JOB_QUEUE
# ===============================
async def auto_message_task(application):
    while True:
        now = datetime.now()
        target_times = [
            now.replace(hour=7, minute=0, second=0, microsecond=0),  # Pagi
            now.replace(hour=17, minute=0, second=0, microsecond=0)  # Sore
        ]

        for target_time in target_times:
            if now > target_time:
                target_time += timedelta(days=1)
            wait_seconds = (target_time - datetime.now()).total_seconds()
            await asyncio.sleep(wait_seconds)

            # Kirim pesan otomatis
            try:
                await application.bot.send_message(
                    chat_id=ADMIN_ID,
                    text="🌅 Selamat pagi! Semoga harimu menyenangkan." if target_time.hour == 7 else "🌇 Selamat sore! Jangan lupa istirahat."
                )
            except Exception as e:
                print(f"Gagal kirim auto message: {e}")

# ===============================
# MAIN
# ===============================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("upscaling", upscaling)],
        states={WAITING_IMAGE: [MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, handle_image)]},
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(conv_handler)

    loop = asyncio.get_event_loop()
    loop.create_task(auto_message_task(app))

    app.run_polling()

if __name__ == "__main__":
    main()
