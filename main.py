import os
import telebot
from telebot import types
import psycopg2
from datetime import datetime, timedelta

# Load environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7649560763"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "xenzi_xn1")

bot = telebot.TeleBot(BOT_TOKEN)
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cur = conn.cursor()

# Create table if not exists
cur.execute("""
CREATE TABLE IF NOT EXISTS premium_users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    expired DATE
);
""")
conn.commit()

# Track admin state
admin_state = {}

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add('/regis', '/lregis')
    bot.send_message(message.chat.id, "Selamat datang! Pilih menu:", reply_markup=markup)

@bot.message_handler(commands=['regis'])
def regis(message):
    user_id = message.from_user.id
    username = message.from_user.username or "no_username"
    cur.execute("SELECT * FROM premium_users WHERE user_id = %s", (user_id,))
    if cur.fetchone():
        bot.send_message(message.chat.id, "❗ Kamu sudah terdaftar.")
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Accept", callback_data=f"accept_{user_id}_{username}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}_{username}")
    )
    bot.send_message(message.chat.id, f"Konfirmasi pendaftaran:\n\nUsername: @{username}\nID: {user_id}", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("accept_") or c.data.startswith("reject_"))
def callback(call):
    act, uid, uname = call.data.split("_")
    uid = int(uid)
    if act == "accept":
        cur.execute("SELECT * FROM premium_users WHERE user_id = %s", (uid,))
        if not cur.fetchone():
            today = datetime.utcnow().date()
            cur.execute("INSERT INTO premium_users (user_id, username, expired) VALUES (%s, %s, %s)", (uid, uname, today))
            conn.commit()
            bot.send_message(call.message.chat.id, f"✅ @{uname} berhasil didaftarkan.")
        else:
            bot.send_message(call.message.chat.id, f"@{uname} sudah terdaftar.")
    else:
        bot.send_message(call.message.chat.id, f"❌ @{uname} ditolak.")

@bot.message_handler(commands=['lregis'])
def list_regis(message):
    cur.execute("SELECT username, expired FROM premium_users ORDER BY expired")
    data = cur.fetchall()
    if not data:
        bot.send_message(message.chat.id, "❌ Belum ada yang terdaftar.")
    else:
        msg = "✅ Daftar Premium:\n"
        for u, e in data:
            msg += f"@{u} - Expired: {e}\n"
        bot.send_message(message.chat.id, msg)

@bot.message_handler(commands=['admin'])
def admin(message):
    if message.from_user.id == ADMIN_ID and message.from_user.username == ADMIN_USERNAME:
        bot.send_message(message.chat.id, "🛡️ Admin Mode Active.")
    else:
        bot.send_message(message.chat.id, "⛔ Tidak diizinkan.")

@bot.message_handler(commands=['addprem'])
def addprem_step1(message):
    if message.from_user.id != ADMIN_ID:
        return
    admin_state[message.chat.id] = {'step': 1}
    bot.send_message(message.chat.id, "Masukkan username (tanpa @):")

@bot.message_handler(commands=['deletprem'])
def deletprem(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            return bot.send_message(message.chat.id, "Gunakan format: /deletprem username")
        uname = parts[1].replace("@", "")
        cur.execute("DELETE FROM premium_users WHERE username = %s", (uname,))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ @{uname} berhasil dihapus.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")

@bot.message_handler(func=lambda m: m.chat.id in admin_state)
def handle_addprem_flow(message):
    state = admin_state[message.chat.id]
    try:
        if state['step'] == 1:
            state['username'] = message.text.replace("@", "")
            state['step'] = 2
            bot.send_message(message.chat.id, "Masukkan jumlah hari expired:")
        elif state['step'] == 2:
            days = int(message.text.strip())
            expired = datetime.utcnow().date() + timedelta(days=days)
            username = state['username']

            # Cek apakah user ada
            cur.execute("SELECT user_id FROM premium_users WHERE username = %s", (username,))
            res = cur.fetchone()
            if not res:
                bot.send_message(message.chat.id, f"❌ @{username} belum terdaftar. Gunakan /regis dulu.")
            else:
                cur.execute("UPDATE premium_users SET expired = %s WHERE username = %s", (expired, username))
                conn.commit()
                bot.send_message(message.chat.id, f"✅ @{username} jadi premium hingga {expired}")
            admin_state.pop(message.chat.id)
    except Exception as e:
        admin_state.pop(message.chat.id)
        bot.send_message(message.chat.id, f"❌ Error: {e}")

# Run the bot
bot.infinity_polling()
