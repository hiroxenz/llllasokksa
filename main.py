import requests, time, os

# KONFIGURASI DARI ENV VAR
API_KEY = os.getenv("API_KEY")
PAIR = 'XAU/USD'
TIMEFRAME = '15min'
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("ADMIN_ID")
LOG_FILE = 'sinyal_log_xau.txt'

def get_price_data():
    url = f'https://api.twelvedata.com/time_series?symbol={PAIR}&interval={TIMEFRAME}&outputsize=5&apikey={API_KEY}'
    try:
        r = requests.get(url)
        data = r.json()
        return data.get('values', [])[::-1]
    except Exception as e:
        print("❌ Gagal ambil data:", e)
        return []

def send_telegram(msg):
    try:
        r = requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            data={'chat_id': CHAT_ID, 'text': msg}
        )
        print("✅ Terkirim ke Telegram:", r.status_code)
    except Exception as e:
        print("❌ Gagal kirim Telegram:", e)

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
    else:
        return None

def run_bot():
    last_signal = ""
    while True:
        try:
            print("⏳ Mengecek sinyal...")
            data = get_price_data()
            if not data:
                time.sleep(60)
                continue

            signal = detect_breakout(data)
            if signal and signal != last_signal:
                time_str = data[-1]['datetime']
                price = data[-1]['close']
                msg = f"""📡 Sinyal XAU/USD Terbaru
━━━━━━━━━━━━━━━━━━
🔔 Arah: {signal}
⏰ Waktu: {time_str}
💰 Harga: {price}
━━━━━━━━━━━━━━━━━━
🚀 Eksekusi sinyal dan pantau chart!
"""
                send_telegram(msg)
                last_signal = signal
            else:
                print("📉 Belum ada sinyal baru.")
            time.sleep(60)
        except Exception as e:
            print("❌ ERROR:", e)
            time.sleep(60)

if __name__ == '__main__':
    run_bot()
