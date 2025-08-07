import os
import time
import requests
import telebot

# === ENV CONFIG ===
API_KEY = os.getenv("API_KEY")  # Pastikan API_KEY di-set di environment variable
PAIR = 'XAU/USD'
TIMEFRAME = '1min'  # Ganti jadi 1 menit
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
LOG_FILE = 'sinyal_log_xau.txt'

# === INIT BOT ===
bot = telebot.TeleBot(BOT_TOKEN)

# === FETCH PRICE DATA ===
def get_price_data():
    url = f'https://api.twelvedata.com/time_series?symbol={PAIR}&interval={TIMEFRAME}&outputsize=5&apikey={API_KEY}'
    try:
        r = requests.get(url)
        data = r.json()
        
        # Cek jika ada error dari API Twelve Data
        if data.get("status") == "error":
            print(f"❌ Error API: {data.get('message')}")
            return []
        
        # Return reversed data supaya data terbaru di akhir list
        return data.get('values', [])[::-1]
    except Exception as e:
        print("❌ Gagal ambil data:", e)
        return []

# === DETEKSI BREAKOUT ===
def detect_breakout(data):
    if len(data) < 3:
        return None
    prev_high = float(data[-2]['high'])
    prev_low = float(data[-2]['low'])
    last_close = float(data[-1]['close'])
    
    if last_close > prev_high:
        return 'BUY'
    elif last_close < prev_low:
        return 'SELL'
    
    return None

# === MAIN LOOP ===
def run_bot():
    last_signal = ""  # Untuk memastikan sinyal tidak dikirim berkali-kali
    while True:
        try:
            print("⏳ Mengecek sinyal...")
            data = get_price_data()
            
            if not data:
                animasi_countdown(ADMIN_ID, durasi=60)
                continue

            signal = detect_breakout(data)
            if signal and signal != last_signal:
                time_str = data[-1]['datetime']
                price = data[-1]['close']
                
                # Pesan yang akan dikirimkan ke admin
                msg = f"""📡 Sinyal XAU/USD Terbaru
━━━━━━━━━━━━━━━━━━
🔔 Arah: {signal}
⏰ Waktu: {time_str}
💰 Harga: {price}
━━━━━━━━━━━━━━━━━━
🚀 Eksekusi sinyal dan pantau chart!
"""
                # Kirim sinyal ke admin
                bot.send_message(chat_id=ADMIN_ID, text=msg)
                
                # Log sinyal ke file
                log_signal(signal, time_str, price)
                
                # Simpan sinyal terakhir
                last_signal = signal
            else:
                print("📉 Belum ada sinyal baru.")
            
            # Tidur selama 60 detik sebelum melakukan pengecekan berikutnya
            time.sleep(60)
        
        except Exception as e:
            print("❌ ERROR:", e)
            time.sleep(60)

# === START ===
if __name__ == '__main__':
    run_bot()
