import time
import requests
import pandas as pd
import ta
from datetime import datetime
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def get_binance_data(symbol="BNBUSDT", interval="1m", limit=100):
    url = f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        response = requests.get(url).json()
        if isinstance(response, dict) and 'code' in response:
            print(f"Binance API Error: {response}")
            return pd.DataFrame()
            
        df = pd.DataFrame(response, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        df['close'] = pd.to_numeric(df['close'])
        df['open'] = pd.to_numeric(df['open'])
        return df
    except Exception as e:
        print(f"Fetch Error: {e}")
        return pd.DataFrame()

def analyze_trend(df):
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    df['ema_9'] = ta.trend.EMAIndicator(df['close'], window=9).ema_indicator()
    df['ema_21'] = ta.trend.EMAIndicator(df['close'], window=21).ema_indicator()
    df['ema_50'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
    
    macd = ta.trend.MACD(df['close'])
    df['macd_line'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()

    latest = df.iloc[-1]
    
    # --- 🛠 ส่วนคำนวณคาดการณ์ราคาล่วงหน้า (Price Estimation) ---
    # คำนวณความต่างของราคาในแท่งปัจจุบันเพื่อดูแรงส่งระดับวินาที
    price_velocity = latest['close'] - latest['open'] 
    
    # กะประมาณราคาที่จะล็อกล่วงหน้าในอีก 30 วินาทีข้างหน้า (Estimated Locked Price)
    # โดยอิงจากราคาล่าสุด + (แรงส่ง * ค่าสัมประสิทธิ์ความหน่วงเวลา)
    estimated_lock_price = latest['close'] + (price_velocity * 0.5)
    
    signal = "WAIT"
    
    # เพิ่มเงื่อนไข: ราคาคาดการณ์ต้องสนับสนุนทิศทางเทรนด์ด้วย
    if (latest['close'] > latest['ema_50'] and 
        latest['ema_9'] > latest['ema_21'] and 
        latest['macd_line'] > latest['macd_signal'] and 
        45 <= latest['rsi'] <= 65 and
        estimated_lock_price > latest['close']): # ราคาคาดการณ์ต้องสูงกว่าราคาปัจจุบัน
        signal = "UP 🟢"
        
    elif (latest['close'] < latest['ema_50'] and 
          latest['ema_9'] < latest['ema_21'] and 
          latest['macd_line'] < latest['macd_signal'] and 
          35 <= latest['rsi'] <= 55 and
          estimated_lock_price < latest['close']): # ราคาคาดการณ์ต้องต่ำกว่าราคาปัจจุบัน
        signal = "DOWN 🔴"
        
    return signal, latest['close'], latest['rsi'], estimated_lock_price

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': text}
    res = requests.post(url, data=payload).json()
    if not res.get("ok"):
        print(f"Telegram Error: {res}")

def main():
    startup_msg = "✅ บอท PancakeSwap (ระบบคาดการณ์ Locked Price ล่วงหน้า) เริ่มทำงานแล้ว! 🚀"
    send_telegram_message(startup_msg)
    print("Bot started. Startup message sent.")
    
    last_alerted_minute = -1
    
    while True:
        now = datetime.now()
        
        # ทำงานนาทีที่ 4 และ 9 วินาทีที่ 30 (เหลือ 30 วิสุดท้ายก่อนปุ่มล็อก)
        if now.minute % 5 == 4 and now.second == 30:
            if now.minute != last_alerted_minute:
                try:
                    df = get_binance_data()
                    
                    if df.empty:
                        print(f"[{now.strftime('%H:%M:%S')}] ไม่สามารถดึงกราฟได้ ข้ามรอบนี้ไปก่อน")
                        continue
                        
                    signal, price, rsi, est_lock = analyze_trend(df)
                    
                    if signal != "WAIT":
                        msg = (
                            f"🔮 PancakeSwap 5m Prediction\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"📍 สัญญาณ: {signal}\n"
                            f"💰 ราคา BNB ปัจจุบัน: ${price:.2f}\n"
                            f"🎯 คาดการณ์ราคาสัญญาณล็อก: ${est_lock:.2f}\n"
                            f" Bars📊 RSI (1m): {rsi:.2f}\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"⏳ รีบลงเดิมพันภายใน 20 วินาที!\n"
                            f"🕐 เวลาส่ง: {now.strftime('%H:%M:%S')}"
                        )
                        send_telegram_message(msg)
                        print(f"[{now.strftime('%H:%M:%S')}] Sent Signal: {signal} | Est Lock: {est_lock:.2f}")
                    else:
                        msg = (
                            f"⏸ PancakeSwap 5m Prediction\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"📍 สัญญาณ: ข้ามรอบนี้ (ทรงกราฟไม่ชัวร์)\n"
                            f"💰 ราคาปัจจุบัน: ${price:.2f}\n"
                            f"🎯 คาดการณ์ราคาล็อก: ${est_lock:.2f}\n"
                            f"📊 RSI (1m): {rsi:.2f}\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"🕐 เวลาส่ง: {now.strftime('%H:%M:%S')}"
                        )
                        send_telegram_message(msg)
                        print(f"[{now.strftime('%H:%M:%S')}] แจ้งเตือนข้ามรอบนี้ (Skipped).")
                    
                    last_alerted_minute = now.minute
                    
                except Exception as e:
                    print(f"Error: {e}")
                    time.sleep(5)
        
        time.sleep(0.5)

if __name__ == "__main__":
    main()
