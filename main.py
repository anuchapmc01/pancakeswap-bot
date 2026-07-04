import time
import requests
import pandas as pd
import ta
from datetime import datetime
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def get_binance_data(symbol="BNBUSDT", interval="1m", limit=100):
    # เปลี่ยนมาใช้ลิงก์สำรอง (data-api.binance.vision) เพื่อแก้ปัญหาโดนบล็อก IP จากเซิร์ฟเวอร์
    url = f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        response = requests.get(url).json()
        
        # เช็คว่า Binance ส่ง Error กลับมาแทนกราฟหรือเปล่า
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
    # ถ้าส่งไม่สำเร็จ ให้ปริ้นท์บอกใน Log จะได้รู้ว่าพังที่ Telegram
    if not res.get("ok"):
        print(f"Telegram Error: {res}")

def main():
    startup_msg = "✅ บอท PancakeSwap (อัปเกรด API + แก้ Error) เริ่มทำงานแล้ว!\nระบบกำลังสแตนด์บายรอจับสัญญาณครับ 🚀"
    send_telegram_message(startup_msg)
    print("Bot started. Startup message sent.")
    
    while True:
        now = datetime.now()
        if now.minute % 5 == 4 and now.second == 30:
            try:
                df = get_binance_data()
                
                # ป้องกัน Error ถ้ากราฟว่างเปล่า
                if df.empty:
                    print(f"[{now.strftime('%H:%M:%S')}] ไม่สามารถดึงกราฟได้ ข้ามรอบนี้ไปก่อน")
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
                    print(f"[{now.strftime('%H:%M:%S')}] เงื่อนไขยังไม่ชัวร์ 100% ข้ามรอบนี้ (Skipped).")
                time.sleep(60)
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(5)
        else:
            time.sleep(1)

if __name__ == "__main__":
    main()
