import os
import logging
import telebot
import psycopg2
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Setup logging
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = telebot.TeleBot(BOT_TOKEN)

# Connect to PostgreSQL
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cursor = conn.cursor()

# Create table if not exists
cursor.execute('''
CREATE TABLE IF NOT EXISTS premium_users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    status TEXT,
    expired DATE
)
''')
conn.commit()

# ======================= HANDLERS ==========================

@bot.message_handler(commands=['start', 'menu'])
def start_handler(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("/regis", callback_data="regis"))
    markup.add(InlineKeyboardButton("/lregis", callback_data="lregis"))
    markup.add(InlineKeyboardButton("/mprem", callback_data="mprem"))
    bot.send_message(message.chat.id, "Selamat datang! Pilih menu:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "regis")
def regis_callback(call):
    user_id = call.from_user.id
    username = call.from_user.username
    cursor.execute("SELECT * FROM premium_users WHERE user_id = %s", (user_id,))
    if cursor.fetchone():
        bot.answer_callback_query(call.id, "Kamu sudah terdaftar.")
    else:
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("Accept", callback_data=f"accept_{user_id}"),
            InlineKeyboardButton("Not Accept", callback_data=f"reject_{user_id}")
        )
        bot.send_message(call.message.chat.id, f"Konfirmasi pendaftaran:
Username: @{username}\nUser ID: {user_id}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("accept_"))
def accept_user(call):
    user_id = int(call.data.split("_")[1])
    username = call.from_user.username
    cursor.execute("SELECT * FROM premium_users WHERE user_id = %s", (user_id,))
    if cursor.fetchone():
        bot.edit_message_text("Kamu sudah terdaftar sebelumnya.", call.message.chat.id, call.message.message_id)
    else:
        cursor.execute("INSERT INTO premium_users (user_id, username, status, expired) VALUES (%s, %s, %s, %s)",
                       (user_id, username, 'Tidak Premium', None))
        conn.commit()
        bot.edit_message_text("Pendaftaran berhasil. Status: Tidak Premium", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("reject_"))
def reject_user(call):
    bot.edit_message_text("Pendaftaran dibatalkan.", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "lregis")
def list_regis(call):
    cursor.execute("SELECT username, status FROM premium_users")
    users = cursor.fetchall()
    if users:
        result = "Daftar user terdaftar:\n"
        for user in users:
            result += f"@{user[0]} - {user[1]}\n"
    else:
        result = "Belum ada user yang terdaftar."
    bot.send_message(call.message.chat.id, result)

@bot.callback_query_handler(func=lambda call: call.data == "mprem")
def list_premium(call):
    cursor.execute("SELECT user_id, username, expired FROM premium_users WHERE status = 'Premium'")
    users = cursor.fetchall()
    now = datetime.now().date()
    active_users = []
    for user_id, username, expired in users:
        if expired and expired >= now:
            active_users.append(f"@{username} (exp: {expired})")
        else:
            cursor.execute("UPDATE premium_users SET status = %s, expired = %s WHERE user_id = %s", ('Tidak Premium', None, user_id))
            conn.commit()
    if active_users:
        bot.send_message(call.message.chat.id, "User Premium aktif:\n" + "\n".join(active_users))
    else:
        bot.send_message(call.message.chat.id, "Tidak ada user premium aktif.")

# ================ ADMIN COMMANDS ===================

admin_states = {}

@bot.message_handler(commands=['admin'])
def admin_cmd(message):
    if message.from_user.id != ADMIN_ID or message.from_user.username != ADMIN_USERNAME:
        return
    bot.send_message(message.chat.id, "Ketik perintah admin:")

@bot.message_handler(commands=['addprem'])
def addprem_start(message):
    if message.from_user.id != ADMIN_ID:
        return
    admin_states[message.chat.id] = 'add_username'
    bot.send_message(message.chat.id, "Masukkan username yang ingin di-premium-kan:")

@bot.message_handler(commands=['deletprem'])
def delprem_start(message):
    if message.from_user.id != ADMIN_ID:
        return
    admin_states[message.chat.id] = 'delete_username'
    bot.send_message(message.chat.id, "Masukkan username yang ingin dihapus dari premium:")

@bot.message_handler(func=lambda m: m.chat.id in admin_states)
def handle_admin_input(message):
    state = admin_states[message.chat.id]
    if state == 'add_username':
        admin_states[message.chat.id] = {'username': message.text}
        bot.send_message(message.chat.id, "Masukkan jumlah hari expired:")
    elif isinstance(state, dict) and 'username' in state:
        try:
            days = int(message.text)
            expired_date = datetime.now().date() + timedelta(days=days)
            cursor.execute("UPDATE premium_users SET status = %s, expired = %s WHERE username = %s", ('Premium', expired_date, state['username']))
            conn.commit()
            bot.send_message(message.chat.id, f"User {state['username']} sekarang Premium hingga {expired_date}")
        except:
            bot.send_message(message.chat.id, "Terjadi kesalahan saat menambahkan premium.")
        admin_states.pop(message.chat.id)
    elif state == 'delete_username':
        cursor.execute("UPDATE premium_users SET status = %s, expired = %s WHERE username = %s", ('Tidak Premium', None, message.text))
        conn.commit()
        bot.send_message(message.chat.id, f"User {message.text} telah dihapus dari premium.")
        admin_states.pop(message.chat.id)

# ======================= START BOT ==========================

bot.infinity_polling()
