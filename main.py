import time
import requests
import pandas as pd
import ta
from datetime import datetime
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ---------------------------------------------------------
# ⚙️ ตั้งค่าเวลาแจ้งเตือน (ปรับตัวเลขตรงนี้ถ้าเวลาเว็บเคลื่อน)
# ---------------------------------------------------------
# ใส่เลข 0, 1, 2, 3 หรือ 4 (เช่น ถ้าเว็บล็อกตอนนาทีที่ 27 (27 หาร 5 เหลือเศษ 2) ให้เตือนก่อน 1 นาที คือเศษ 1)
TRIGGER_MINUTE_REMAINDER = 1  
TRIGGER_SECOND = 30           # วินาทีที่จะให้เตือน (แนะนำ 30)
# ---------------------------------------------------------

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
    signal = "WAIT"
    
    if (latest['close'] > latest['ema_50'] and 
        latest['ema_9'] > latest['ema_21'] and 
        latest['macd_line'] > latest['macd_signal'] and 
        45 <= latest['rsi'] <= 65):
        signal = "UP 🟢"
        
    elif (latest['close'] < latest['ema_50'] and 
          latest['ema_9'] < latest['ema_21'] and 
          latest['macd_line'] < latest['macd_signal'] and 
          35 <= latest['rsi'] <= 55):
        signal = "DOWN 🔴"
        
    return signal, latest['close'], latest['rsi']

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': text}
    res = requests.post(url, data=payload).json()
    if not res.get("ok"):
        print(f"Telegram Error: {res}")

def main():
    startup_msg = f"✅ บอทปรับเวลาใหม่เริ่มทำงานแล้ว!\nตั้งค่าเตือนที่เศษนาทีที่: {TRIGGER_MINUTE_REMAINDER} วินาทีที่: {TRIGGER_SECOND} 🚀"
    send_telegram_message(startup_msg)
    print("Bot started. Startup message sent.")
    
    while True:
        now = datetime.now()
        # ดึงค่าเวลามาจากตั้งค่าด้านบน
        if now.minute % 5 == TRIGGER_MINUTE_REMAINDER and now.second == TRIGGER_SECOND:
            try:
                df = get_binance_data()
                
                if df.empty:
                    time.sleep(60)
                    continue
                    
                signal, price, rsi = analyze_trend(df)
                
                if signal != "WAIT":
                    msg = (
                        f"🔮 PancakeSwap 5m Prediction\n"
                        f"📍 สัญญาณ: {signal}\n"
                        f"💰 ราคา BNB: ${price:.2f}\n"
                        f"📊 RSI (1m): {rsi:.2f}\n"
                        f"⏳ รีบลงเดิมพันภายใน 20 วินาที!"
                    )
                    send_telegram_message(msg)
                    print(f"[{now.strftime('%H:%M:%S')}] Sent Signal: {signal}")
                else:
                    msg = (
                        f"⏸ PancakeSwap 5m Prediction\n"
                        f"📍 สัญญาณ: ข้ามรอบนี้ (ทรงกราฟไม่ชัวร์)\n"
                        f"💰 ราคาปัจจุบัน: ${price:.2f}\n"
                        f"📊 RSI (1m): {rsi:.2f}"
                    )
                    send_telegram_message(msg)
                    print(f"[{now.strftime('%H:%M:%S')}] แจ้งเตือนข้ามรอบนี้ (Skipped).")
                    
                time.sleep(60)
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(5)
        else:
            time.sleep(1)

if __name__ == "__main__":
    main()
