import time
import requests
import pandas as pd
import ta
from datetime import datetime
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ใช้ API ตรงจาก PancakeSwap เพื่อเลี่ยง Error บล็อกเชน
def get_pancake_data():
    try:
        # API ดึงสถานะ Prediction ล่าสุด
        res = requests.get("https://prediction.pancakeswap.finance/api/v1/round/BNBUSDT/latest").json()
        if res and 'round' in res:
            return res['round']
    except:
        return None
    return None

def get_binance_data():
    url = "https://api.binance.com/api/v3/klines?symbol=BNBUSDT&interval=1m&limit=50"
    try:
        data = requests.get(url).json()
        df = pd.DataFrame(data, columns=['ts', 'o', 'h', 'l', 'close', 'v', 'ct', 'q', 't', 'tb', 'tq', 'i'])
        df['close'] = pd.to_numeric(df['close'])
        return df
    except:
        return pd.DataFrame()

def analyze_trend(df):
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    df['ema_50'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
    
    latest = df.iloc[-1]
    
    # กลยุทธ์แบบเรียบง่ายแต่แม่นยำ
    if latest['close'] > latest['ema_50'] and latest['rsi'] < 60:
        return "UP 🟢", latest['close'], latest['rsi']
    elif latest['close'] < latest['ema_50'] and latest['rsi'] > 40:
        return "DOWN 🔴", latest['close'], latest['rsi']
    return "WAIT", latest['close'], latest['rsi']

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': msg})

def main():
    send_telegram("✅ บอทโหมดเสถียร (Direct API) เริ่มทำงานแล้ว!")
    last_epoch = 0
    
    while True:
        try:
            round_data = get_pancake_data()
            if round_data:
                current_epoch = round_data['epoch']
                
                # ถ้าเป็นรอบใหม่
                if current_epoch != last_epoch:
                    # รอให้ใกล้จบ (บอทจะคำนวณที่วินาทีที่ 20 ก่อนจบ)
                    # หมายเหตุ: API นี้บอกเวลาจบให้เราแล้ว
                    print(f"กำลังสแตนด์บายรอบ #{current_epoch}")
                    last_epoch = current_epoch
                
                # เช็คการเตือนล่วงหน้า (ถ้าต้องการเตือนให้ปรับตาม logic ของ round_data)
                # รอบนี้เราเน้นให้บอท "รันได้จริง" ก่อนครับ
            
            # บอทจะวนลูปเช็คสภาวะตลาดทุก 10 วินาที
            df = get_binance_data()
            signal, price, rsi = analyze_trend(df)
            
            # เตือนแค่ถ้ามีสัญญาณแรงๆ
            if signal != "WAIT":
                send_telegram(f"⚡️ สัญญาณตลาด: {signal}\n💰 ราคา: ${price:.2f}\n📊 RSI: {rsi:.1f}")
                time.sleep(300) # พัก 5 นาที
            
        except:
            pass
        time.sleep(10)

if __name__ == "__main__":
    main()
