import logging
import psycopg2
import schedule
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from datetime import datetime, timedelta
import os

# Masukkan variabel berikut sesuai dengan konfigurasi Anda
DATABASE_URL = os.getenv("DATABASE_URL")  # Gunakan variabel env dari Railway
ADMIN_ID = os.getenv("ADMIN_ID")  # ID Admin Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Token bot Telegram

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Fungsi untuk menghubungkan ke PostgreSQL
def connect_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# Fungsi untuk membuat tabel jika belum ada
def create_table():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jadwal (
            id SERIAL PRIMARY KEY,
            jadwal TEXT,
            tanggal DATE
        );
    """)
    conn.commit()
    cursor.close()
    conn.close()

# Fungsi untuk menambah jadwal ke database
def add_jadwal(jadwal, tanggal):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO jadwal (jadwal, tanggal) VALUES (%s, %s)", (jadwal, tanggal))
    conn.commit()
    cursor.close()
    conn.close()

# Fungsi untuk mengambil semua jadwal
def get_jadwal():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, jadwal, tanggal FROM jadwal ORDER BY tanggal ASC")
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return result

# Fungsi untuk menghapus jadwal berdasarkan ID
def delete_jadwal(id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jadwal WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()

# Fungsi untuk mengirim jadwal hari ini kepada admin
def send_today_schedule(context):
    today = datetime.today().date()
    jadwal_today = get_jadwal_for_date(today)

    if jadwal_today:
        message = f"*Jadwal Hari Ini ({today}):*\n"
        for jadwal in jadwal_today:
            message += f"🗓 *{jadwal[1]}* pada *{jadwal[2]}*\n"
        context.bot.send_message(chat_id=ADMIN_ID, text=message, parse_mode=ParseMode.MARKDOWN)
        
        keyboard = [[InlineKeyboardButton("✅ Sudah Dilihat", callback_data='accept')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_message(chat_id=ADMIN_ID, text="Apakah Anda sudah melihat jadwal hari ini?", reply_markup=reply_markup)
    else:
        context.bot.send_message(chat_id=ADMIN_ID, text="📅 *Tidak ada jadwal hari ini.*", parse_mode=ParseMode.MARKDOWN)

# Fungsi untuk mendapatkan jadwal berdasarkan tanggal
def get_jadwal_for_date(date):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT jadwal, tanggal FROM jadwal WHERE tanggal = %s", (date,))
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return result

# Handler untuk /start
def start(update, context):
    update.message.reply_text(
        "*Selamat datang di Bot Jadwal!*\n\n"
        "🔹 *Perintah yang tersedia:*\n"
        "/jadwal - 🗓 Menambahkan jadwal baru\n"
        "/listjadwal - 📋 Menampilkan semua jadwal yang telah ditambahkan\n"
        "/deljadwal - ❌ Menghapus jadwal berdasarkan nomor urut\n"
        "Jadwal hari ini akan dikirimkan secara otomatis setiap pagi!"
        , parse_mode=ParseMode.MARKDOWN
    )

# Handler untuk /jadwal
def jadwal(update, context):
    update.message.reply_text("✍️ *Silakan masukkan jadwal baru dengan format berikut:* \n"
                              "Contoh: *'Meeting 2025-08-10'*\n\n"
                              "Masukkan jadwal dan tanggalnya:", parse_mode=ParseMode.MARKDOWN)

def handle_jadwal_message(update, context):
    user_input = update.message.text.split(' ')
    if len(user_input) < 2:
        update.message.reply_text("🚨 *Format tidak valid!*\n"
                                  "Gunakan format: 'Jadwal YYYY-MM-DD' (misal: *Meeting 2025-08-10*)",
                                  parse_mode=ParseMode.MARKDOWN)
        return

    jadwal = " ".join(user_input[:-1])
    tanggal = user_input[-1]

    try:
        datetime.strptime(tanggal, '%Y-%m-%d')  # Validasi format tanggal
        add_jadwal(jadwal, tanggal)
        update.message.reply_text(f"🎉 *Jadwal '{jadwal}' pada {tanggal} berhasil ditambahkan!*",
                                  parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        update.message.reply_text("❌ *Format tanggal tidak valid!*\n"
                                  "Pastikan formatnya adalah YYYY-MM-DD (misal: *2025-08-10*).",
                                  parse_mode=ParseMode.MARKDOWN)

# Handler untuk /listjadwal
def list_jadwal(update, context):
    jadwals = get_jadwal()
    if jadwals:
        message = "*Daftar Jadwal:*\n"
        for idx, jadwal in enumerate(jadwals, start=1):
            message += f"🔢 {idx}. {jadwal[1]} pada {jadwal[2]}\n"
        update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    else:
        update.message.reply_text("📅 *Tidak ada jadwal yang tersedia.*", parse_mode=ParseMode.MARKDOWN)

# Handler untuk /deljadwal
def del_jadwal(update, context):
    try:
        jadwal_id = int(update.message.text.split(' ')[1])
        jadwals = get_jadwal()

        if 1 <= jadwal_id <= len(jadwals):
            delete_jadwal(jadwal_id)
            update.message.reply_text(f"✅ *Jadwal nomor {jadwal_id} telah berhasil dihapus.*",
                                      parse_mode=ParseMode.MARKDOWN)
        else:
            update.message.reply_text("🚨 *Nomor jadwal tidak valid.*", parse_mode=ParseMode.MARKDOWN)
    except (IndexError, ValueError):
        update.message.reply_text("❌ *Silakan masukkan nomor jadwal yang ingin dihapus.*",
                                  parse_mode=ParseMode.MARKDOWN)

# Fungsi untuk menangani callback button
def button(update, context):
    query = update.callback_query
    if query.data == "accept":
        query.answer()
        context.bot.send_message(chat_id=ADMIN_ID, text="👍 *Terima kasih, jadwal sudah dilihat!*", parse_mode=ParseMode.MARKDOWN)

# Setup scheduler untuk mengirimkan jadwal setiap hari
def setup_scheduler(dispatcher):
    schedule.every().day.at("08:00").do(send_today_schedule, context=dispatcher)
    while True:
        schedule.run_pending()
        time.sleep(1)

def main():
    # Inisialisasi bot
    updater = Updater(BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Membuat tabel jadwal jika belum ada
    create_table()

    # Menambahkan handler untuk perintah
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("jadwal", jadwal))
    dispatcher.add_handler(CommandHandler("listjadwal", list_jadwal))
    dispatcher.add_handler(CommandHandler("deljadwal", del_jadwal))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_jadwal_message))
    dispatcher.add_handler(CallbackQueryHandler(button))

    # Mulai bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
