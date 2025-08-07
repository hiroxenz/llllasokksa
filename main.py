import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2
import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = os.getenv("ADMIN_ID")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")

bot = telebot.TeleBot(BOT_TOKEN)

# DB Connection
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cur = conn.cursor()

# Create tables
cur.execute("""
CREATE TABLE IF NOT EXISTS registrations (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    status TEXT
);
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS premium_users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    expired TIMESTAMP
);
""")
conn.commit()

# /start command
@bot.message_handler(commands=['start'])
def start_handler(message):
    text = "👋 Selamat datang! Gunakan perintah berikut:\n\n/regis - Daftar\n/lregis - Lihat yang diterima"
    bot.send_message(message.chat.id, text)

# /regis command
@bot.message_handler(commands=['regis'])
def regis_user(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Cek jika sudah daftar
    cur.execute("SELECT status FROM registrations WHERE user_id = %s", (user_id,))
    result = cur.fetchone()
    if result:
        bot.send_message(message.chat.id, f"📌 Kamu sudah terdaftar dengan status: {result[0]}")
        return

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Accept", callback_data=f"accept_{user_id}"),
        InlineKeyboardButton("❌ Not Accept", callback_data=f"reject_{user_id}")
    )

    msg = f"📝 Pendaftaran:\n👤 Username: @{username}\n🆔 ID: {user_id}\n\nPilih:"
    bot.send_message(message.chat.id, msg, reply_markup=markup)

# Handle accept/reject
@bot.callback_query_handler(func=lambda call: call.data.startswith("accept_") or call.data.startswith("reject_"))
def handle_callback(call):
    action, uid = call.data.split("_")
    uid = int(uid)
    username = call.from_user.username or call.from_user.first_name
    status = "Accepted" if action == "accept" else "Rejected"

    cur.execute(
        "INSERT INTO registrations (user_id, username, status) VALUES (%s, %s, %s) "
        "ON CONFLICT (user_id) DO UPDATE SET status = %s;",
        (uid, username, status, status)
    )
    conn.commit()

    bot.answer_callback_query(call.id, f"Kamu memilih: {status}")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    bot.send_message(call.message.chat.id, f"✅ Status pendaftaran: {status}")

# /lregis command
@bot.message_handler(commands=['lregis'])
def list_accepted(message):
    cur.execute("SELECT username FROM registrations WHERE status = 'Accepted'")
    users = cur.fetchall()
    if users:
        daftar = "\n".join([f"- @{u[0]}" for u in users])
        bot.send_message(message.chat.id, f"✅ Pendaftar yang diterima:\n{daftar}")
    else:
        bot.send_message(message.chat.id, "Belum ada yang diterima.")

# /admin command (khusus admin)
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if str(message.from_user.id) == ADMIN_ID and message.from_user.username == ADMIN_USERNAME:
        bot.send_message(message.chat.id, "🔐 Admin Command:\n/addprem\n/deletprem")
    else:
        pass  # Hidden

# /addprem interactive
user_add_steps = {}

@bot.message_handler(commands=['addprem'])
def start_addprem(message):
    if str(message.from_user.id) != ADMIN_ID:
        return
    msg = bot.send_message(message.chat.id, "Masukkan username yang ingin diberi premium:")
    bot.register_next_step_handler(msg, get_username)

def get_username(message):
    user_add_steps[message.chat.id] = {"username": message.text}
    msg = bot.send_message(message.chat.id, f"Masukkan jumlah hari expired untuk @{message.text}:")
    bot.register_next_step_handler(msg, get_expired_days)

def get_expired_days(message):
    try:
        days = int(message.text)
        data = user_add_steps.get(message.chat.id, {})
        username = data.get("username")

        cur.execute("SELECT user_id FROM registrations WHERE username = %s AND status = 'Accepted'", (username,))
        result = cur.fetchone()

        if not result:
            bot.send_message(message.chat.id, f"❌ User @{username} tidak ditemukan atau belum diterima.")
            return

        user_id = result[0]
        expired_date = datetime.now() + timedelta(days=days)

        cur.execute("""
            INSERT INTO premium_users (user_id, username, expired)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET expired = %s;
        """, (user_id, username, expired_date, expired_date))
        conn.commit()

        bot.send_message(message.chat.id, f"✅ @{username} berhasil diberi premium selama {days} hari (sampai {expired_date.date()}).")
        user_add_steps.pop(message.chat.id, None)

    except Exception as e:
        bot.send_message(message.chat.id, f"Terjadi kesalahan: {str(e)}")

# /deletprem command
@bot.message_handler(commands=['deletprem'])
def delete_prem(message):
    if str(message.from_user.id) != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) != 2:
        bot.send_message(message.chat.id, "Format: /deletprem [username]")
        return
    username = args[1]
    cur.execute("DELETE FROM premium_users WHERE username = %s", (username,))
    conn.commit()
    bot.send_message(message.chat.id, f"✅ Premium user @{username} telah dihapus.")

# Start polling
bot.infinity_polling()
