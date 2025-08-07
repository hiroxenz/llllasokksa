import telebot
import logging
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2
import os
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO)

# Ambil variabel dari environment
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")  # postgresql://user:pass@host:port/dbname
ADMIN_ID = int(os.getenv("ADMIN_ID"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")

bot = telebot.TeleBot(BOT_TOKEN)

# Fungsi koneksi database
def get_db():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn, conn.cursor()

# Inisialisasi tabel
def init_db():
    conn, cur = get_db()
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
        expired_at DATE
    );
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "👋 Selamat datang!\n\nGunakan perintah berikut:\n/regis - Daftar\n/lregis - Lihat user diterima")

# /regis
@bot.message_handler(commands=['regis'])
def regis_user(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Cek apakah user sudah daftar
    conn, cur = get_db()
    cur.execute("SELECT * FROM registrations WHERE user_id = %s", (user_id,))
    existing = cur.fetchone()
    cur.close()
    conn.close()

    if existing:
        bot.send_message(message.chat.id, "⚠️ Kamu sudah terdaftar.")
        return

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Accept", callback_data=f"accept_{user_id}"),
        InlineKeyboardButton("❌ Not Accept", callback_data=f"reject_{user_id}")
    )

    msg = f"📝 Pendaftaran:\n👤 Username: @{username}\n🆔 ID: {user_id}\n\nPilih:"
    bot.send_message(message.chat.id, msg, reply_markup=markup)

# Button accept / reject
@bot.callback_query_handler(func=lambda call: call.data.startswith("accept_") or call.data.startswith("reject_"))
def handle_callback(call):
    action, uid = call.data.split("_")
    uid = int(uid)
    username = call.from_user.username or call.from_user.first_name
    status = "Accepted" if action == "accept" else "Rejected"

    try:
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

        if status == "Accepted":
            bot.send_message(call.message.chat.id, f"✅ Data user @{username} telah di-*Accept*.", parse_mode="Markdown")
        else:
            bot.send_message(call.message.chat.id, f"❌ Data user @{username} telah di-*Reject*.", parse_mode="Markdown")

    except Exception as e:
        logging.error(f"[ERROR] Callback DB: {e}")
        bot.send_message(call.message.chat.id, "⚠️ Gagal menyimpan data.")

# /lregis - list accepted
@bot.message_handler(commands=['lregis'])
def list_accepted(message):
    try:
        conn, cur = get_db()
        cur.execute("SELECT username FROM registrations WHERE status = 'Accepted'")
        results = cur.fetchall()
        cur.close()
        conn.close()

        if results:
            users = "\n".join([f"@{r[0]}" if r[0] else "(tanpa username)" for r in results])
            msg = f"✅ User yang *Accepted*:\n\n{users}"
        else:
            msg = "❌ Belum ada user yang di-*Accept*."

        bot.send_message(message.chat.id, msg, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"[ERROR] /lregis: {e}")
        bot.send_message(message.chat.id, "⚠️ Gagal mengambil data.")

# /admin - hidden, hanya bisa diakses ID dan username tertentu
@bot.message_handler(commands=['admin'])
def admin_command(message):
    if message.from_user.id == ADMIN_ID and message.from_user.username == ADMIN_USERNAME:
        bot.send_message(message.chat.id, "🛠️ Admin Mode:\n/addprem [username] [expired]\n/deletprem [username]")
    else:
        pass  # tidak merespon

# /addprem username expired_days
@bot.message_handler(commands=['addprem'])
def add_prem(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        args = message.text.split()
        if len(args) != 3:
            return bot.reply_to(message, "Format: /addprem username jumlah_hari")

        username = args[1].lstrip("@")
        expired_days = int(args[2])
        expired_at = datetime.now().date() + timedelta(days=expired_days)

        # Ambil user_id dari database registration
        conn, cur = get_db()
        cur.execute("SELECT user_id FROM registrations WHERE username = %s", (username,))
        row = cur.fetchone()

        if not row:
            return bot.reply_to(message, "❌ Username tidak ditemukan di data registrasi.")

        user_id = row[0]

        cur.execute("""
        INSERT INTO premium_users (user_id, username, expired_at)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username, expired_at = EXCLUDED.expired_at
        """, (user_id, username, expired_at))
        conn.commit()
        cur.close()
        conn.close()

        bot.reply_to(message, f"✅ @{username} ditambahkan sebagai premium hingga {expired_at}")
    except Exception as e:
        logging.error(f"[ERROR] /addprem: {e}")
        bot.reply_to(message, "⚠️ Gagal menambahkan premium user.")

# /deletprem username
@bot.message_handler(commands=['deletprem'])
def delete_prem(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        args = message.text.split()
        if len(args) != 2:
            return bot.reply_to(message, "Format: /deletprem username")

        username = args[1].lstrip("@")

        conn, cur = get_db()
        cur.execute("DELETE FROM premium_users WHERE username = %s", (username,))
        conn.commit()
        cur.close()
        conn.close()

        bot.reply_to(message, f"❌ @{username} telah dihapus dari daftar premium.")
    except Exception as e:
        logging.error(f"[ERROR] /deletprem: {e}")
        bot.reply_to(message, "⚠️ Gagal menghapus premium user.")

# Run bot
if __name__ == "__main__":
    logging.info("Bot is running...")
    bot.infinity_polling()
