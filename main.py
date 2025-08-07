import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2
import os

# Ambil token dan URL database dari environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")  # Format: postgresql://user:pass@host:port/dbname

bot = telebot.TeleBot(BOT_TOKEN)

# Fungsi koneksi dinamis agar thread aman
def get_db():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn, conn.cursor()

# Buat tabel jika belum ada
def init_db():
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

init_db()

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

    msg = f"📝 Pendaftaran:\n👤 Username: @{username}\n\nPilih:"
    bot.send_message(message.chat.id, msg, reply_markup=markup)

# Tombol Accept / Reject
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

        # Kirim feedback ke pengguna
        bot.answer_callback_query(call.id, f"Kamu memilih: {status}")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

        # Kirim pesan info status
        if status == "Accepted":
            bot.send_message(call.message.chat.id, f"✅ Data user @{username} telah di-*Accept*.", parse_mode="Markdown")
        else:
            bot.send_message(call.message.chat.id, f"❌ Data user @{username} telah di-*Reject*.", parse_mode="Markdown")

    except Exception as e:
        print(f"[ERROR] Callback DB error: {e}")
        bot.send_message(call.message.chat.id, "⚠️ Gagal menyimpan data.")

# /lregis - List accepted users
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
            msg = f"✅ Daftar user yang sudah *Accepted*:\n\n{users}"
        else:
            msg = "❌ Belum ada user yang di-*Accept*."

        bot.send_message(message.chat.id, msg, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(message.chat.id, "⚠️ Gagal mengambil data.")
        print(f"[ERROR] /lregis: {e}")

# Jalankan bot polling
if __name__ == "__main__":
    logging.info("Bot is running...")
    bot.infinity_polling()
