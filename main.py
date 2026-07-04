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
            return pd.DataFrame()
        df = pd.DataFrame(response, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        df['close'] = pd.to_numeric(df['close'])
        return df
    except:
        return pd.DataFrame()

def analyze_trend(df):
    # คำนวณอินดิเคเตอร์
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    df['ema_50'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
    
    macd = ta.trend.MACD(df['close'])
    df['macd_line'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()

    latest = df.iloc[-1]
    signal = "WAIT"
    
    # เงื่อนไขใหม่: เพิ่มความเข้มงวดเพื่อลดโอกาสผิด
    # UP: ราคาต้องอยู่เหนือ EMA50 + MACD ตัดขึ้น + RSI อยู่ในโซนโมเมนตัมขาขึ้น
    if (latest['close'] > latest['ema_50'] and 
        latest['macd_line'] > latest['macd_signal'] and 
        50 < latest['rsi'] < 60):
        signal = "UP 🟢"
        
    # DOWN: ราคาต้องอยู่ใต้ EMA50 + MACD ตัดลง + RSI อยู่ในโซนโมเมนตัมขาลง
    elif (latest['close'] < latest['ema_50'] and 
          latest['macd_line'] < latest['macd_signal'] and 
          40 < latest['rsi'] < 50):
        signal = "DOWN 🔴"
        
    return signal, latest['close'], latest['rsi']

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': text}
    requests.post(url, data=payload)

def main():
    startup_msg = "✅ บอทปรับกลยุทธ์เพิ่มความแม่นยำ (Signal Filter) เริ่มทำงานแล้ว! 🚀"
    send_telegram_message(startup_msg)
    
    while True:
        now = datetime.now()
        
        # ปรับเวลาเตือน: นาทีที่ 0/5 วินาทีที่ 40 (ช้าลง 40 วิจากจุดเริ่มแรก)
        if now.minute % 5 == 0 and now.second == 40: 
            try:
                df = get_binance_data()
                
                if df.empty:
                    time.sleep(60)
                    continue
                    
                signal, price, rsi = analyze_trend(df)
                
                if signal != "WAIT":
                    msg = (
                        f"🔮 PancakeSwap Prediction (High Accuracy)\n"
                        f"📍 สัญญาณ: {signal}\n"
                        f"💰 ราคา BNB: ${price:.2f}\n"
                        f"📊 RSI: {rsi:.2f}\n"
                        f"⏳ รีบลงเดิมพันก่อนปุ่มล็อค!"
                    )
                    send_telegram_message(msg)
                else:
                    # กรณีไม่ผ่านเงื่อนไขจะไม่ส่งข้อความ เพื่อคัดเฉพาะสัญญาณที่แม่นยำจริงๆ
                    print(f"[{now.strftime('%H:%M:%S')}] สัญญาณไม่ชัดเจน (Skipped).")
                    
                time.sleep(70) # เว้นช่วงหลังส่งสัญญาณ
                
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(5)
        else:
            time.sleep(1)

if __name__ == "__main__":
    main()
