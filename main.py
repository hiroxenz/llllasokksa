import os
import requests
import tempfile
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Ambil dari Railway
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Ambil dari Railway

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

waiting_for_image = set()

# ===== ADMIN CHECK =====
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# ===== HANDLERS =====
async def start_upscaler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 Anda tidak memiliki izin untuk menggunakan bot ini.")
        return

    waiting_for_image.add(update.effective_user.id)
    await update.message.reply_text("🔼 Kirim foto atau link gambar yang ingin di-upscale.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("🚫 Anda tidak memiliki izin untuk menggunakan bot ini.")
        return

    if user_id not in waiting_for_image:
        return

    # Link gambar
    if update.message.text and update.message.text.startswith("http"):
        await update.message.reply_text("⏳ Mengunduh gambar dari link...")
        try:
            img_data = requests.get(update.message.text, timeout=10).content
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(img_data)
                tmp_path = tmp.name
            await upscale_and_send(update, tmp_path)
        except Exception as e:
            await update.message.reply_text(f"❌ Gagal mengunduh gambar: {e}")

    # Gambar langsung
    elif update.message.photo:
        await update.message.reply_text("⏳ Mengunggah gambar...")
        file_id = update.message.photo[-1].file_id
        photo_file = await context.bot.get_file(file_id)
        tmp_path = tempfile.mktemp(suffix=".jpg")
        await photo_file.download_to_drive(tmp_path)
        await upscale_and_send(update, tmp_path)

    else:
        await update.message.reply_text("❌ Harap kirim foto atau link gambar yang valid.")

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
                await update.message.reply_photo(photo=result_url, caption="✅ Gambar berhasil di-upscale!")
            else:
                await update.message.reply_text("❌ Gagal mendapatkan URL hasil upscale.")
        else:
            await update.message.reply_text(f"❌ Gagal memproses gambar (status {response.status_code}).")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    finally:
        waiting_for_image.discard(update.effective_user.id)

# ===== MAIN =====
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("upscaler", start_upscaler))
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    print("🚀 Bot khusus admin berjalan...")
    app.run_polling()
