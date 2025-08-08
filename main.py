import logging
import psycopg2
import schedule
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
from datetime import datetime

# Mengaktifkan logging untuk debug
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Gantilah dengan ID admin dan bot token Anda
ADMIN_ID = 'YOUR_ADMIN_ID'
BOT_TOKEN = 'YOUR_BOT_TOKEN'

# Koneksi database PostgreSQL
DATABASE_URL = 'YOUR_DATABASE_URL'

# Fungsi untuk menghubungkan ke database
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# /start untuk memulai bot
def start(update, context):
    keyboard = [
        [InlineKeyboardButton("Lihat Jadwal", callback_data='listjadwal')],
        [InlineKeyboardButton("Tambah Jadwal", callback_data='jadwal')],
        [InlineKeyboardButton("Hapus Jadwal", callback_data='deljadwal')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Selamat datang! Pilih opsi berikut:", reply_markup=reply_markup)

# /jadwal untuk menambahkan jadwal baru
def jadwal(update, context):
    update.message.reply_text("Silakan kirimkan pesan jadwal Anda (format: Jadwal [Tanggal] [Waktu])")
    return 'AWAITING_SCHEDULE'

# Fungsi untuk menangani input jadwal
def handle_jadwal(update, context):
    message = update.message.text
    schedule_data = message.split(" ")

    if len(schedule_data) < 3:
        update.message.reply_text("Format tidak sesuai. Harap kirimkan dengan format: 'Jadwal [Tanggal] [Waktu]'")
        return

    jadwal = " ".join(schedule_data[1:])
    tanggal = schedule_data[0]

    # Simpan jadwal ke database
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO jadwal (jadwal, tanggal) VALUES (%s, %s)", (jadwal, tanggal))
    conn.commit()
    cur.close()
    conn.close()

    update.message.reply_text(f"Jadwal berhasil ditambahkan: {jadwal} pada {tanggal}")

# /listjadwal untuk melihat jadwal yang sudah ditambahkan
def list_jadwal(update, context):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jadwal")
    rows = cur.fetchall()

    if not rows:
        update.message.reply_text("Belum ada jadwal yang ditambahkan.")
        return

    schedule_text = "Daftar Jadwal:\n"
    for i, row in enumerate(rows, 1):
        schedule_text += f"{i}. {row[1]} pada {row[2]}\n"

    update.message.reply_text(schedule_text)
    cur.close()
    conn.close()

# /deljadwal untuk menghapus jadwal berdasarkan nomor urut
def del_jadwal(update, context):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jadwal")
    rows = cur.fetchall()

    if not rows:
        update.message.reply_text("Tidak ada jadwal yang dapat dihapus.")
        return

    schedule_text = "Daftar Jadwal:\n"
    for i, row in enumerate(rows, 1):
        schedule_text += f"{i}. {row[1]} pada {row[2]}\n"

    update.message.reply_text(schedule_text)
    update.message.reply_text("Kirimkan nomor jadwal yang ingin dihapus.")
    return 'AWAITING_DELETE'

# Menghapus jadwal yang dipilih oleh pengguna
def handle_delete(update, context):
    schedule_num = update.message.text

    try:
        schedule_num = int(schedule_num)
    except ValueError:
        update.message.reply_text("Nomor jadwal tidak valid.")
        return

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jadwal WHERE id = %s", (schedule_num,))
    row = cur.fetchone()

    if not row:
        update.message.reply_text(f"Jadwal dengan nomor {schedule_num} tidak ditemukan.")
        return

    cur.execute("DELETE FROM jadwal WHERE id = %s", (schedule_num,))
    conn.commit()
    cur.close()
    conn.close()

    update.message.reply_text(f"Jadwal {schedule_num} berhasil dihapus.")

# Menangani pesan yang tidak dikenali
def unknown(update, context):
    update.message.reply_text("Perintah tidak dikenali. Ketik /start untuk memulai.")

# Fungsi untuk menjadwalkan pengingat
def send_reminder(update, context):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jadwal")
    rows = cur.fetchall()

    if not rows:
        cur.close()
        conn.close()
        return

    for row in rows:
        jadwal, tanggal = row[1], row[2]
        if datetime.now().strftime('%Y-%m-%d') == tanggal:
            context.bot.send_message(chat_id=update.message.chat_id, text=f"Jadwal hari ini: {jadwal} pada {tanggal}")
            keyboard = [
                [InlineKeyboardButton("Terapkan", callback_data=f'accept_{row[0]}')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            context.bot.send_message(chat_id=update.message.chat_id, text="Apakah Anda ingin menerima jadwal ini?", reply_markup=reply_markup)
    cur.close()
    conn.close()

# Fungsi untuk mengonfirmasi penerimaan jadwal
def accept_jadwal(update, context):
    query = update.callback_query
    query.answer()
    query.edit_message_text(text="Jadwal diterima. Terima kasih!")

# Main function untuk setup bot
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Menambahkan handler
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('jadwal', jadwal))
    dp.add_handler(CommandHandler('listjadwal', list_jadwal))
    dp.add_handler(CommandHandler('deljadwal', del_jadwal))

    # Handling untuk mengirim jadwal
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_jadwal))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_delete))

    # Handling untuk callback query
    dp.add_handler(CallbackQueryHandler(accept_jadwal, pattern='^accept_'))

    # Set jadwal reminder setiap hari
    schedule.every().day.at("09:00").do(send_reminder, update=updater.bot, context=updater.context)

    # Mulai bot
    updater.start_polling()
    updater.idle()

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == '__main__':
    main()
