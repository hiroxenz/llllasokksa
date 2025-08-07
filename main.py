import os
import time
import requests
import numpy as np
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

# === SMA (Simple Moving Average) ===
def calculate_sma(data, period=50):
    close_prices = [float(candle['close']) for candle in data]
    sma = np.mean(close_prices[-period:])
    return sma

# === RSI (Relative Strength Index) ===
def calculate_rsi(data, period=14):
    close_prices = [float(candle['close']) for candle in data]
    gains = []
    losses = []
    
    # Hitung perubahan harga
    for i in range(1, len(close_prices)):
        change = close_prices[i] - close_prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        elif change < 0:
            gains.append(0)
            losses.append(abs(change))
        else:
            gains.append(0)
            losses.append(0)
    
    # Rata-rata gain dan loss
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    
    # Menghindari pembagian dengan nol
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# === HITUNG TP (Take Profit) dan SL (Stop Loss) ===
def calculate_tp_sl(signal, current_price, risk_reward_ratio=2, risk_percentage=0.01):
    """
    Menghitung TP dan SL berdasarkan posisi dan Risk-to-Reward Ratio.
    """
    stop_loss = 0
    take_profit = 0
    
    # Untuk BUY, stop loss di bawah harga dan take profit di atas
    if signal == "BUY":
        stop_loss = current_price - (current_price * risk_percentage)  # SL = 1% di bawah harga saat ini
        take_profit = current_price + (current_price * risk_percentage * risk_reward_ratio)  # TP = 2% lebih tinggi
    # Untuk SELL, stop loss di atas harga dan take profit di bawah
    elif signal == "SELL":
        stop_loss = current_price + (current_price * risk_percentage)  # SL = 1% di atas harga saat ini
        take_profit = current_price - (current_price * risk_percentage * risk_reward_ratio)  # TP = 2% lebih rendah
    
    return take_profit, stop_loss

# === DETEKSI POSISI BUY/SELL DENGAN INDIKATOR ===
def detect_position(data):
    if len(data) < 50:  # Minimum data untuk menghitung SMA 50
        return None
    
    # Hitung indikator teknikal
    sma_50 = calculate_sma(data, period=50)
    rsi_14 = calculate_rsi(data, period=14)
    last_close = float(data[-1]['close'])
    
    # Deteksi sinyal
    if last_close > sma_50 and rsi_14 < 30:  # Kondisi oversold dan harga di atas SMA
        return 'BUY'
    elif last_close < sma_50 and rsi_14 > 70:  # Kondisi overbought dan harga di bawah SMA
        return 'SELL'
    
    return None

# === LOG FILE ===
def log_signal(signal, time_str, price):
    with open(LOG_FILE, "a") as f:
        f.write(f"{time_str} | {signal} | {price}\n")

# === ANIMASI COUNTDOWN 60 DETIK ===
def animasi_countdown(chat_id, durasi=60):
    msg = bot.send_message(chat_id, f"⏳ Menunggu sinyal dalam {durasi}s...")
    for detik in range(durasi, 0, -1):
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg.message_id,
                text=f"⏳ Menunggu sinyal dalam {detik}s..."
            )
            time.sleep(1)
        except Exception as e:
            print("⚠️ Animasi terhenti:", e)
            break

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

            signal = detect_position(data)  # Gunakan fungsi deteksi posisi dengan indikator

            if signal and signal != last_signal:
                time_str = data[-1]['datetime']
                price = float(data[-1]['close'])

                # Hitung Take Profit dan Stop Loss
                tp, sl = calculate_tp_sl(signal, price)
                
                # Pesan yang akan dikirimkan ke admin
                msg = f"""📡 Sinyal XAU/USD Terbaru
━━━━━━━━━━━━━━━━━━
🔔 Arah: {signal}
⏰ Waktu: {time_str}
💰 Harga: {price}
🎯 Take Profit (TP): {tp}
⛔ Stop Loss (SL): {sl}
━━━━━━━━━━━━━━━━━━
🚀 Eksekusi sinyal dan pantau chart!
"""
                
                # Kirim sinyal dan TP/SL ke admin
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
