import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2
import os
import logging
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO)

# Load ENV
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")

bot = telebot.TeleBot(BOT_TOKEN)

# PostgreSQL Connection
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cur = conn.cursor()

# Setup Tables
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
    expired DATE,
    status TEXT
);
""")
conn.commit()

# /start and /menu
@bot.message_handler(commands=['start', 'menu'])
def menu(message):
    text = "\n".join([
        "\U0001F4AC *Menu Bot*:",
        "/regis - Daftar pengguna",
        "/lregis - Lihat yang sudah daftar",
        "/mprem - Lihat user premium (valid)",
    ])
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# /regis
@bot.message_handler(commands=['regis'])
def regis_user(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    cur.execute("SELECT * FROM registrations WHERE user_id = %s", (user_id,))
    if cur.fetchone():
        bot.reply_to(message, "\u274C Kamu sudah terdaftar!")
        return

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("\u2705 Accept", callback_data=f"accept_{user_id}"),
        InlineKeyboardButton("\u274C Not Accept", callback_data=f"reject_{user_id}")
    )
    bot.send_message(message.chat.id, f"\U0001F4DD Pendaftaran:\nUsername: @{username}\nID: {user_id}", reply_markup=markup)

# /lregis
@bot.message_handler(commands=['lregis'])
def list_regis(message):
    cur.execute("SELECT username, status FROM registrations WHERE status = 'Accepted'")
    rows = cur.fetchall()
    if not rows:
        bot.reply_to(message, "Belum ada yang daftar.")
        return
    daftar = "\n".join([f"@{r[0]} - {r[1]}" for r in rows])
    bot.reply_to(message, f"\U0001F465 Yang sudah daftar:\n{daftar}")

# /mprem
@bot.message_handler(commands=['mprem'])
def list_premium(message):
    now = datetime.now().date()
    cur.execute("SELECT user_id, username, expired FROM premium_users WHERE status = 'Premium'")
    rows = cur.fetchall()
    if not rows:
        bot.reply_to(message, "Tidak ada user premium.")
        return

    valid_users = []
    for uid, uname, expired in rows:
        if expired < now:
            cur.execute("UPDATE premium_users SET status = 'Tidak Premium' WHERE user_id = %s", (uid,))
            cur.execute("UPDATE registrations SET status = 'Tidak Premium' WHERE user_id = %s", (uid,))
        else:
            valid_users.append(f"@{uname} - Exp: {expired}")
    conn.commit()

    if not valid_users:
        bot.reply_to(message, "Tidak ada user premium aktif.")
    else:
        bot.reply_to(message, "\U0001F3C6 User Premium Aktif:\n" + "\n".join(valid_users))

# Inline button callback
@bot.callback_query_handler(func=lambda call: call.data.startswith("accept_") or call.data.startswith("reject_"))
def handle_callback(call):
    action, uid = call.data.split("_")
    uid = int(uid)
    username = call.from_user.username or call.from_user.first_name
    status = "Accepted" if action == "accept" else "Rejected"

    cur.execute("""
        INSERT INTO registrations (user_id, username, status)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET status = %s;
    """, (uid, username, status, status))
    conn.commit()

    bot.answer_callback_query(call.id, f"Kamu memilih: {status}")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    bot.send_message(call.message.chat.id, f"\u2709️ Status user @{username} diperbarui menjadi: {status}")

# Admin command
@bot.message_handler(commands=['admin'])
def admin_cmd(message):
    if message.from_user.id != ADMIN_ID or message.from_user.username != ADMIN_USERNAME:
        return
    bot.reply_to(message, "\U0001F511 Menu Admin:\n/addprem\n/deletprem")

# Premium logic states
user_states = {}

@bot.message_handler(commands=['addprem'])
def addprem_start(message):
    if message.from_user.id != ADMIN_ID:
        return
    user_states[message.from_user.id] = {'step': 'await_username'}
    bot.reply_to(message, "Masukkan username yang ingin di-premium-kan:")

@bot.message_handler(commands=['deletprem'])
def delprem_start(message):
    if message.from_user.id != ADMIN_ID:
        return
    user_states[message.from_user.id] = {'step': 'await_delusername'}
    bot.reply_to(message, "Masukkan username yang ingin dihapus dari premium:")

@bot.message_handler(func=lambda m: m.from_user.id in user_states)
def handle_state(message):
    state = user_states[message.from_user.id]

    if state['step'] == 'await_username':
        state['username'] = message.text.strip().lstrip('@')
        state['step'] = 'await_days'
        bot.reply_to(message, "Masukkan berapa hari premium aktif:")

    elif state['step'] == 'await_days':
        try:
            days = int(message.text.strip())
            expired = datetime.now().date() + timedelta(days=days)
            username = state['username']

            cur.execute("SELECT user_id FROM registrations WHERE username = %s", (username,))
            row = cur.fetchone()
            if not row:
                bot.reply_to(message, "User belum terdaftar.")
            else:
                user_id = row[0]
                cur.execute("""
                    INSERT INTO premium_users (user_id, username, expired, status)
                    VALUES (%s, %s, %s, 'Premium')
                    ON CONFLICT (user_id) DO UPDATE SET expired = %s, status = 'Premium';
                """, (user_id, username, expired, expired))
                cur.execute("UPDATE registrations SET status = 'Premium' WHERE user_id = %s", (user_id,))
                conn.commit()
                bot.reply_to(message, f"User @{username} telah menjadi premium sampai {expired}")
        except ValueError:
            bot.reply_to(message, "Masukkan jumlah hari yang valid.")
        user_states.pop(message.from_user.id)

    elif state['step'] == 'await_delusername':
        username = message.text.strip().lstrip('@')
        cur.execute("SELECT user_id FROM premium_users WHERE username = %s", (username,))
        row = cur.fetchone()
        if not row:
            bot.reply_to(message, "User premium tidak ditemukan.")
        else:
            user_id = row[0]
            cur.execute("DELETE FROM premium_users WHERE user_id = %s", (user_id,))
            cur.execute("UPDATE registrations SET status = 'Tidak Premium' WHERE user_id = %s", (user_id,))
            conn.commit()
            bot.reply_to(message, f"User @{username} telah dihapus dari premium.")
        user_states.pop(message.from_user.id)

bot.infinity_polling()
