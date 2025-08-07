import os
import psycopg2
from telebot import TeleBot, types

# Ambil data dari environment Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")

bot = TeleBot(BOT_TOKEN)

# Koneksi database
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cursor = conn.cursor()

# Buat tabel jika belum ada
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tspam (
        id SERIAL PRIMARY KEY,
        nomor TEXT NOT NULL
    )
''')
conn.commit()

# ───────────────────────────────────────────────────── #

@bot.message_handler(commands=['start', 'menu'])
def menu(message):
    text = (
        "📋 *Menu Utama:*\n"
        "/tools - Lihat tools\n"
        "/swa - Menu swa\n"
        "/addn <nomor> - Tambah target (628xxx)\n"
        "/listn - Lihat nomor target\n"
        "/runs <id> - Kirim Swa ke nomor"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['tools'])
def tools(message):
    bot.send_message(message.chat.id, "🛠 Tools:\n- Under development...")

@bot.message_handler(commands=['swa'])
def swa(message):
    bot.send_message(message.chat.id, "📲 SWA Menu:\n- Gunakan /addn dan /runs")

@bot.message_handler(commands=['addn'])
def addn(message):
    args = message.text.split(" ", 1)
    if len(args) != 2 or not args[1].startswith("628") or not args[1].isdigit():
        bot.reply_to(message, "⚠️ Format salah! Contoh: /addn 6281234567890")
        return
    nomor = args[1]
    cursor.execute("INSERT INTO tspam (nomor) VALUES (%s)", (nomor,))
    conn.commit()
    bot.send_message(message.chat.id, f"✅ Nomor {nomor} berhasil ditambahkan.")

@bot.message_handler(commands=['listn'])
def listn(message):
    cursor.execute("SELECT id, nomor FROM tspam ORDER BY id")
    rows = cursor.fetchall()
    if not rows:
        bot.send_message(message.chat.id, "📭 Belum ada nomor target.")
        return
    
    text = "📋 *Daftar Nomor Target:*\n"
    for row in rows:
        idn, nomor = row
        sensor = nomor[:-5] + "*****"
        text += f"{idn}. {sensor}\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['runs'])
def runs(message):
    args = message.text.split(" ", 1)
    if len(args) != 2 or not args[1].isdigit():
        bot.reply_to(message, "⚠️ Gunakan: /runs <nomor_id>")
        return
    
    nomor_id = int(args[1])
    cursor.execute("SELECT nomor FROM tspam WHERE id = %s", (nomor_id,))
    result = cursor.fetchone()
    
    if not result:
        bot.send_message(message.chat.id, "❌ Nomor tidak ditemukan.")
        return
    
    nomor = result[0]
    sensor = nomor[:-5] + "*****"
    
    # Simulasi pengiriman
    bot.send_message(message.chat.id, f"📤 Swa berhasil terkirim ke {sensor}")

# ───────────────────────────────────────────────────── #

bot.polling()
