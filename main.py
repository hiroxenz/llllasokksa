import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")  # From Railway PostgreSQL

bot = telebot.TeleBot(BOT_TOKEN)

# Connect to PostgreSQL
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cur = conn.cursor()

# Buat table jika belum ada
cur.execute("""
CREATE TABLE IF NOT EXISTS registrations (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    status TEXT
);
""")
conn.commit()

# /regis command
@bot.message_handler(commands=['regis'])
def regis_user(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("✅ Accept", callback_data=f"accept_{user_id}"),
        InlineKeyboardButton("❌ Not Accept", callback_data=f"reject_{user_id}")
    )

    msg = f"📝 Pendaftaran:\n👤 Username: @{username}\n🆔 ID: {user_id}\n\nPilih:"
    bot.send_message(message.chat.id, msg, reply_markup=markup)

# Tombol callback
@bot.callback_query_handler(func=lambda call: call.data.startswith("accept_") or call.data.startswith("reject_"))
def handle_callback(call):
    action, uid = call.data.split("_")
    uid = int(uid)
    username = call.from_user.username or call.from_user.first_name

    status = "Accepted" if action == "accept" else "Rejected"

    # Simpan ke DB
    cur.execute("INSERT INTO registrations (user_id, username, status) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET status = %s;",
                (uid, username, status, status))
    conn.commit()

    bot.answer_callback_query(call.id, f"Kamu memilih: {status}")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

