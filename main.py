import os
import requests
import threading
import time
from telegram import Bot
from telegram.ext import Updater, CommandHandler
from dotenv import load_dotenv
import logging

# Set up logging to catch bot errors
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Memuat environment variables dari file .env
load_dotenv()

# API Key Telegram dan Alpha Vantage
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
ALPHA_VANTAGE_API_KEY = os.getenv("API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

# URL untuk mendapatkan data XAU/USD dari Alpha Vantage
API_URL = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=XAUUSD=X&interval=1min&apikey={ALPHA_VANTAGE_API_KEY}"

# Fungsi untuk mendapatkan harga XAU/USD terbaru
def get_xau_usd_price():
    response = requests.get(API_URL)
    data = response.json()
    try:
        # Mengambil harga penutupan terakhir (1 menit sebelumnya)
        time_series = data["Time Series (1min)"]
        latest_time = list(time_series.keys())[0]
        latest_price = time_series[latest_time]["4. close"]
        return float(latest_price)
    except KeyError:
        return None

# Fungsi untuk menghitung TP dan SL berdasarkan harga
def calculate_tp_sl(current_price):
    tp = current_price * 1.005  # Target Profit +0.5%
    sl = current_price * 0.995  # Stop Loss -0.5%
    return tp, sl

# Fungsi untuk mengirimkan update harga dan rekomendasi ke Admin
def send_price_update():
    bot = Bot(token=TELEGRAM_TOKEN)
    
    while True:
        price = get_xau_usd_price()
        if price is None:
            message = "Tidak dapat mengambil data harga XAU/USD saat ini."
        else:
            tp, sl = calculate_tp_sl(price)
            message = (
                f"Update Harga XAU/USD\n"
                f"Harga saat ini: ${price:.2f}\n"
                f"Rekomendasi:\n"
                f"Open Posisi: {price:.2f}\n"
                f"Target Profit (TP): {tp:.2f}\n"
                f"Stop Loss (SL): {sl:.2f}"
            )

        # Kirim pesan ke Admin
        bot.send_message(chat_id=ADMIN_ID, text=message)
        
        # Tunggu 5 menit sebelum mengirim update berikutnya
        time.sleep(60)  # 300 detik = 5 menit

# Fungsi utama untuk menjalankan bot
def main():
    # Inisialisasi Updater
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Menjalankan thread untuk mengirimkan update harga XAU/USD ke admin
    update_thread = threading.Thread(target=send_price_update)
    update_thread.daemon = True  # Menjalankan thread sebagai daemon sehingga bisa berhenti saat program utama berhenti
    update_thread.start()

    # Mulai polling untuk bot (meskipun tidak ada perintah yang dijalankan)
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
