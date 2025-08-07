import os
import psycopg2
from telebot import TeleBot, types

# Load environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")

# Inisialisasi bot
bot = TeleBot(BOT_TOKEN)

# Koneksi ke database PostgreSQL
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cursor = conn.cursor()

# Membuat tabel jika belum ada
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tspam (
        id SERIAL PRIMARY KEY,
        nomor TEXT NOT NULL
    )
''')
conn.commit()

# ──────────────── COMMANDS ──────────────── #

@bot.message_handler(commands=['start', 'menu'])
def menu(message):
    text = (
        "📋 *Menu Utama:*\n"
        "/tools - Buka menu tools"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['tools'])
def tools(message):
    text = (
        "🛠 *Tools Menu:*\n"
        "/swa - Buka menu swa\n"
        "/addn <nomor> - Tambah target (628xxx)\n"
        "/listn - Lihat nomor target\n"
        "/runs <id> - Kirim Swa ke nomor target"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['swa'])
def swa(message):
    bot.send_message(message.chat.id, "📲 SWA Menu:\nGunakan /addn dan /runs untuk mengelola target.")

@bot.message_handler(commands=['addn'])
def addn(message):
    args = message.text.split(" ", 1)
    if len(args) != 2 or not args[1].startswith("628") or not args[1].isdigit():
        bot.reply_to(message, "⚠️ Format salah! Contoh: /addn 6281234567890")
        return
    nomor = args[1]
    try:
        cursor.execute("INSERT INTO tspam (nomor) VALUES (%s)", (nomor,))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ Nomor {nomor} berhasil ditambahkan.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Gagal menambahkan nomor: {e}")

@bot.message_handler(commands=['listn'])
def listn(message):
    try:
        cursor.execute("SELECT id, nomor FROM tspam ORDER BY id")
        rows = cursor.fetchall()

        if not rows:
            bot.send_message(message.chat.id, "📭 Belum ada nomor yang ditambahkan.")
            return

        text = "📋 *Daftar Nomor Target:*\n"
        for row in rows:
            idn = row[0]
            nomor = row[1]
            sensor = nomor[:-5] + "*****" if len(nomor) > 5 else "*****"
            text += f"{idn}. {sensor}\n"

        bot.send_message(message.chat.id, text, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Terjadi kesalahan: {e}")

@bot.message_handler(commands=['runs'])
def runs(message):
    args = message.text.split(" ", 1)
    if len(args) != 2 or not args[1].isdigit():
        bot.reply_to(message, "⚠️ Gunakan: /runs <id>")
        return

    nomor_id = int(args[1])
    try:
        cursor.execute("SELECT nomor FROM tspam WHERE id = %s", (nomor_id,))
        result = cursor.fetchone()

        if not result:
            bot.send_message(message.chat.id, "❌ Nomor tidak ditemukan.")
            return

        nomor = result[0]
        sensor = nomor[:-5] + "*****" if len(nomor) > 5 else "*****"

        # Simulasi pengiriman swa (replace dengan real API logic jika ada)
        bot.send_message(message.chat.id, f"📤 SWA berhasil terkirim ke {sensor}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Terjadi kesalahan: {e}")

# ──────────────── RUN BOT ──────────────── #
bot.polling()
