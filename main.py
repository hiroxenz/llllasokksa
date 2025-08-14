import os
import re
import json
import time
import uuid
import asyncio
import random
import string
import secrets
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, Tuple

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    filters, ConversationHandler
)

# ===============================
# ENV & CONFIG
# ===============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

MENU_IMAGE_URL = "https://raw.githubusercontent.com/hiroxenz/llllasokksa/refs/heads/main/photo_2025-08-14_15-26-37.jpg"

# === Pixelcut (Upscaling) ===
PIXELCUT_URL = "https://api2.pixelcut.app/image/upscale/v1"
PIXELCUT_HEADERS = {
    'authority': 'api2.pixelcut.app',
    'accept': 'application/json',
    'origin': 'https://www.pixelcut.ai',
    'referer': 'https://www.pixelcut.ai/',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
    'x-client-version': 'web',
    'x-locale': 'en',
}

# === API MILIKMU (GANTI DENGAN punyamu) ===
API_BASE = "https://api.domain-kamu.com"  # <- ganti
ENDPOINT_GET_SESSION    = f"{API_BASE}/session/init"                 # return: {client_id, app_id, rollout_hash, csrftoken}
ENDPOINT_CREATE_ACCOUNT = f"{API_BASE}/accounts/create/attempt"      # cek username/step awal
ENDPOINT_CHECK_AGE      = f"{API_BASE}/accounts/age/check"           # {eligible_to_register: true/false}
ENDPOINT_SEND_CODE      = f"{API_BASE}/accounts/email/send_code"     # {email_sent: true/false}
ENDPOINT_VERIFY_CODE    = f"{API_BASE}/accounts/email/verify_code"   # {signup_code: "..."}
ENDPOINT_FINALIZE       = f"{API_BASE}/accounts/create/finalize"     # hasil final

# ===============================
# STATE CONVERSATION
# ===============================
WAITING_IMAGE = 1
REG_WAIT_EMAIL, REG_WAIT_CODE = range(2)

# ===============================
# HELPER & MODEL ALUR REGISTER
# ===============================
def rand_str(n=12, pool=string.ascii_letters + string.digits):
    return ''.join(secrets.choice(pool) for _ in range(n))

def now_ts():
    return int(time.time())

@dataclass
class Setup:
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    locale: str = "id-ID"

@dataclass
class Create_Accnt:
    email: str
    setup: Setup = field(default_factory=Setup)
    s: requests.Session = field(default_factory=requests.Session)
    headers: Dict[str, str] = field(default_factory=dict)

    # state random identity
    first_name: str = field(default_factory=lambda: "User" + rand_str(5).lower())
    username: str = field(default_factory=lambda: ("user" + rand_str(6, string.ascii_lowercase + string.digits)))
    plain_password: str = field(default_factory=lambda: rand_str(12))
    enc_password: str = ""
    birth_day: int = field(default_factory=lambda: random.randint(1, 28))
    birth_month: int = field(default_factory=lambda: random.randint(1, 12))
    birth_year: int = field(default_factory=lambda: random.randint(1989, 2007))
    extra_session_id: str = field(default_factory=lambda: ":".join(
        "".join(random.choices(string.ascii_lowercase + string.digits, k=6)) for _ in range(3)
    ))

    # meta dari SetAccnt
    client_id: str = ""
    app_id: str = ""
    rollout_hash: str = ""
    csrftoken: str = ""

    def _build_headers(self, extra: Dict[str, str] = None) -> Dict[str, str]:
        base = {
            "User-Agent": self.setup.user_agent,
            "Accept-Language": self.setup.locale + ",en;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        if extra:
            base.update(extra)
        return base

    # ===== SetAccnt =====
    def SetAccnt(self) -> Tuple[str, str]:
        # generate enc_password
        self.enc_password = f"#PWD_BROWSER:0:{now_ts()}:{self.plain_password}"

        r = self.s.get(ENDPOINT_GET_SESSION, headers=self._build_headers(), timeout=20)
        r.raise_for_status()
        meta = r.json()
        self.client_id    = meta.get("client_id","")
        self.app_id       = meta.get("app_id","")
        self.rollout_hash = meta.get("rollout_hash","")
        self.csrftoken    = meta.get("csrftoken","")

        cookies_string = "; ".join([f"{k}={v}" for k,v in self.s.cookies.get_dict().items()])
        self.headers = self._build_headers({
            "X-Csrftoken": self.csrftoken,
            "X-App-Id": self.app_id,
            "X-Rollout-Hash": self.rollout_hash,
        })
        return self.csrftoken, cookies_string

    # ===== ICreate =====
    def ICreate(self) -> bool:
        data = {
            "enc_password": self.enc_password,
            "email": self.email,
            "first_name": self.first_name,
            "username": self.username,
            "client_id": self.client_id,
            "use_new_suggested_user_name": "true",
        }
        r = self.s.post(ENDPOINT_CREATE_ACCOUNT, headers=self.headers, data=data, timeout=30)
        r.raise_for_status()
        j = r.json()
        return bool("username_suggestions" in j or j.get("ok"))

    # ===== IBirthday =====
    def IBirthday(self) -> bool:
        data = {"day": self.birth_day, "month": self.birth_month, "year": self.birth_year}
        r = self.s.post(ENDPOINT_CHECK_AGE, headers=self.headers, data=data, timeout=20)
        r.raise_for_status()
        return bool(r.json().get("eligible_to_register", False))

    # ===== IGetCode =====
    def IGetCode(self) -> bool:
        data = {"device_id": self.client_id, "email": self.email}
        r = self.s.post(ENDPOINT_SEND_CODE, headers=self.headers, data=data, timeout=20)
        r.raise_for_status()
        return bool(r.json().get("email_sent", False))

    # ===== IVcode =====
    def IVcode(self, code: str):
        data = {"code": code, "device_id": self.client_id, "email": self.email}
        r = self.s.post(ENDPOINT_VERIFY_CODE, headers=self.headers, data=data, timeout=20)
        r.raise_for_status()
        j = r.json()
        return j.get("signup_code", None)

    # ===== IVsig =====
    def IVsig(self, signup_code: str) -> Dict:
        data = {
            "enc_password": self.enc_password,
            "day": self.birth_day,
            "email": self.email,
            "first_name": self.first_name,
            "month": self.birth_month,
            "username": self.username,
            "year": self.birth_year,
            "client_id": self.client_id,
            "tos_version": "row",
            "force_sign_up_code": signup_code,
            "extra_session_id": self.extra_session_id,
        }
        r = self.s.post(ENDPOINT_FINALIZE, headers=self.headers, data=data, timeout=30)
        r.raise_for_status()
        return r.json()

# ===============================
# ADMIN GUARD
# ===============================
def is_admin(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == ADMIN_ID

# ===============================
# /start
# ===============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await menu(update, context)

# ===============================
# /menu
# ===============================
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    menu_text = (
        "╭━━━『 📜 *Main Menu* 』━━━╮\n"
        "┣ 🎯 /upscaling — *Perbesar & tingkatkan kualitas gambar*\n"
        "┣ 📨 /register — *Daftar akun (email + kode verifikasi)*\n"
        "┣ 📌 /menu — *Tampilkan menu ini*\n"
        "┣ 🏁 /start — *Mulai bot*\n"
        "╰━━━━━━━━━━━━━━━━━━╯"
    )
    await update.message.reply_photo(photo=MENU_IMAGE_URL, caption=menu_text, parse_mode=ParseMode.MARKDOWN)

# ===============================
# /upscaling (tetap)
# ===============================
async def upscaling(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text("📤 Silakan kirim *foto* atau *link gambar* yang ingin di-*upscale*.", parse_mode=ParseMode.MARKDOWN)
    return WAITING_IMAGE

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    file_data = None
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        new_file = await context.bot.get_file(file_id)
        file_data = requests.get(new_file.file_path, timeout=30).content
    elif update.message.text and update.message.text.strip().lower().startswith("http"):
        img_url = update.message.text.strip()
        file_data = requests.get(img_url, timeout=30).content

    if not file_data:
        await update.message.reply_text("❌ Gagal membaca gambar. Kirim foto atau link yang valid.")
        return ConversationHandler.END

    files = {
        'image': ('image.png', file_data, 'image/png'),
        'scale': (None, '2'),
    }
    await update.message.reply_text("⏳ Memproses *upscaling*...", parse_mode=ParseMode.MARKDOWN)
    resp = requests.post(PIXELCUT_URL, headers=PIXELCUT_HEADERS, files=files, timeout=120)
    try:
        url_image = resp.json().get('result_url')
        if url_image:
            await update.message.reply_photo(photo=url_image, caption="✅ *Upscaling selesai!*", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("❌ Gagal mendapatkan URL hasil upscaling.")
    except Exception as e:
        await update.message.reply_text(f"❌ Terjadi error: `{e}`", parse_mode=ParseMode.MARKDOWN)

    return ConversationHandler.END

# ===============================
# /register (email -> code -> proses)
# ===============================
async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    await update.message.reply_text("📧 Masukkan *email* yang akan didaftarkan:", parse_mode=ParseMode.MARKDOWN)
    return REG_WAIT_EMAIL

async def register_recv_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    email = update.message.text.strip()
    context.user_data['reg_email'] = email

    # Init instance & jalankan SetAccnt + ICreate + IBirthday + IGetCode
    acc = Create_Accnt(email=email)
    context.user_data['acc'] = acc

    try:
        await update.message.reply_text("⚙️ Inisialisasi sesi...", parse_mode=ParseMode.MARKDOWN)
        acc.SetAccnt()

        await update.message.reply_text("🔎 Mengecek ketersediaan nama & langkah awal...", parse_mode=ParseMode.MARKDOWN)
        if not acc.ICreate():
            await update.message.reply_text("❌ Gagal tahap *ICreate*. Silakan coba lagi.")
            return ConversationHandler.END

        await update.message.reply_text("🗓️ Mengecek kelayakan umur...", parse_mode=ParseMode.MARKDOWN)
        if not acc.IBirthday():
            await update.message.reply_text("❌ Tidak memenuhi syarat usia.")
            return ConversationHandler.END

        await update.message.reply_text("📨 Mengirim kode verifikasi ke email...", parse_mode=ParseMode.MARKDOWN)
        if not acc.IGetCode():
            await update.message.reply_text("❌ Gagal mengirim kode verifikasi ke email.")
            return ConversationHandler.END

        await update.message.reply_text(
            "✉️ Silakan cek email kamu. Lalu *kirimkan kode verifikasi* di sini.",
            parse_mode=ParseMode.MARKDOWN
        )
        return REG_WAIT_CODE

    except requests.HTTPError as e:
        await update.message.reply_text(f"❌ HTTP error: {e.response.status_code}\n{e.response.text[:300]}")
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ Error: `{e}`", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

async def register_recv_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    code = update.message.text.strip()
    acc: Create_Accnt = context.user_data.get('acc')

    if not acc:
        await update.message.reply_text("⚠️ Sesi registrasi tidak ditemukan. Mulai lagi dengan /register.")
        return ConversationHandler.END

    try:
        await update.message.reply_text("🔐 Memvalidasi kode...", parse_mode=ParseMode.MARKDOWN)
        signup_code = acc.IVcode(code)
        if not signup_code:
            await update.message.reply_text("❌ Kode verifikasi salah/invalid.")
            return ConversationHandler.END

        await update.message.reply_text("🧩 Menyelesaikan pendaftaran...", parse_mode=ParseMode.MARKDOWN)
        result = acc.IVsig(signup_code)

        creds_text = (
            "✅ *Pendaftaran Berhasil!*\n\n"
            f"👤 *Username*: `{acc.username}`\n"
            f"📧 *Email*: `{acc.email}`\n"
            f"🔑 *Password*: `{acc.plain_password}`\n"
            f"🧾 *Enc Pass*: `{acc.enc_password}`\n"
            f"🎂 *DOB*: `{acc.birth_day:02d}-{acc.birth_month:02d}-{acc.birth_year}`\n"
        )
        await update.message.reply_text(creds_text, parse_mode=ParseMode.MARKDOWN)

        pretty = json.dumps(result, indent=2, ensure_ascii=False)
        if len(pretty) < 3500:
            await update.message.reply_text(f"📦 *Response Final:*\n```\n{pretty}\n```", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_document(document=bytes(pretty, "utf-8"), filename="register_result.json", caption="📦 Response Final")

    except requests.HTTPError as e:
        await update.message.reply_text(f"❌ HTTP error: {e.response.status_code}\n{e.response.text[:300]}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: `{e}`", parse_mode=ParseMode.MARKDOWN)
    finally:
        # bersihkan state
        context.user_data.pop('acc', None)
        context.user_data.pop('reg_email', None)

    return ConversationHandler.END

# ===============================
# AUTO MESSAGE TANPA JOB_QUEUE
# ===============================
async def auto_message_task(application):
    while True:
        now = datetime.now()
        target_times = [
            now.replace(hour=7, minute=0, second=0, microsecond=0),   # Pagi
            now.replace(hour=17, minute=0, second=0, microsecond=0), # Sore
        ]
        for target_time in target_times:
            if datetime.now() > target_time:
                target_time += timedelta(days=1)
            wait_seconds = (target_time - datetime.now()).total_seconds()
            await asyncio.sleep(max(0, wait_seconds))
            try:
                await application.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=("🌅 Selamat pagi! Semoga harimu menyenangkan." if target_time.hour == 7
                          else "🌇 Selamat sore! Jangan lupa istirahat.")
                )
            except Exception as e:
                print(f"Gagal kirim auto message: {e}")

# ===============================
# MAIN
# ===============================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Upscaling convo
    upscaling_conv = ConversationHandler(
        entry_points=[CommandHandler("upscaling", upscaling)],
        states={WAITING_IMAGE: [MessageHandler(filters.PHOTO | (filters.TEXT & ~filters.COMMAND), handle_image)]},
        fallbacks=[],
    )

    # Register convo (email -> code)
    register_conv = ConversationHandler(
        entry_points=[CommandHandler("register", register_start)],
        states={
            REG_WAIT_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_recv_email)],
            REG_WAIT_CODE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, register_recv_code)],
        },
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(upscaling_conv)
    app.add_handler(register_conv)

    loop = asyncio.get_event_loop()
    loop.create_task(auto_message_task(app))

    print("🚀 Bot berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()
