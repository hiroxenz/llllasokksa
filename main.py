import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

# Load env variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Check env var
if not BOT_TOKEN or not DATABASE_URL:
    raise Exception("BOT_TOKEN dan DATABASE_URL harus diatur di environment variables.")

bot = telebot.TeleBot(BOT_TOKEN)

# Function to get DB cursor
def get_db():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn, conn.cursor()

# Inisialisasi database: buat tabel jika belum ada
def init_db():
    try:
        conn, cur = get_db()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            status TEXT
        );
        """)
        conn.commit()
        cur.close()
        conn.close()
        logging.info("Database berhasil diinisialisasi.")
    except Exception as e:
        logging.error(f"Gagal inisialisasi database: {e}")

init_db()

# Handler /regis
@bot.message_handler(commands=['regis'])
def regis_user(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ Accept", callback_data=f"accept_{user_id}"),
        InlineKeyboardButton("❌ Not Accept", callback_data=f"reject_{user_id}")
    )

    msg = f"📝 Pendaftaran:\n👤 Username: @{username}\n🆔 ID: {user_id}\n\nPilih:"
    bot.send_message(message.chat.id, msg, reply_markup=markup)

# Handler tombol callback
@bot.callback_query_handler(func=lambda call: call.data.startswith("accept_") or call.data.startswith("reject_"))
def handle_callback(call):
    try:
        action, uid = call.data.split("_")
        uid = int(uid)
        username = call.from_user.username or call.from_user.first_name
        status = "Accepted" if action == "accept" else "Rejected"

        conn, cur = get_db()
        cur.execute("""
            INSERT INTO registrations (user_id, username, status)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET status = EXCLUDED.status;
        """, (uid, username, status))
        conn.commit()
        cur.close()
        conn.close()

        bot.answer_callback_query(call.id, f"Kamu memilih: {status}")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

    except Exception as e:
        logging.error(f"Callback error: {e}")
        bot.answer_callback_query(call.id, "Terjadi kesalahan.")

# Jalankan bot polling
if __name__ == "__main__":
    logging.info("Bot is running...")
    bot.infinity_polling()
