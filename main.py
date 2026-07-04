import time
import requests
import pandas as pd
import ta
from datetime import datetime
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def get_binance_data(interval="1m"):
    url = f"https://data-api.binance.vision/api/v3/klines?symbol=BNBUSDT&interval={interval}&limit=50"
    try:
        data = requests.get(url).json()
        df = pd.DataFrame(data, columns=['ts', 'o', 'h', 'l', 'close', 'v', 'ct', 'q', 't', 'tb', 'tq', 'i'])
        df['close'] = pd.to_numeric(df['close'])
        # อินดิเคเตอร์สำหรับวิเคราะห์
        df['ema_50'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
        stoch = ta.momentum.StochasticOscillator(df['h'], df['l'], df['close'])
        df['stoch'] = stoch.stoch()
        return df
    except:
        return pd.DataFrame()

def get_signal(df_1m, df_3m):
    # ดึงค่าล่าสุด
    l1 = df_1m.iloc[-1]
    l3 = df_3m.iloc[-1]
    
    # Logic: ต้องเห็นพ้องต้องกันทั้ง 1m และ 3m
    # UP: ทั้งสอง TF ต้องมีราคา > EMA50 และ Stoch ยังไม่ Overbought (>80)
    if (l1['close'] > l1['ema_50'] and l3['close'] > l3['ema_50'] and 
        l1['stoch'] < 80 and l3['stoch'] < 80):
        return "UP 🟢", l1['close']
    
    # DOWN: ทั้งสอง TF ต้องมีราคา < EMA50 และ Stoch ยังไม่ Oversold (<20)
    elif (l1['close'] < l1['ema_50'] and l3['close'] < l3['ema_50'] and 
          l1['stoch'] > 20 and l3['stoch'] > 20):
        return "DOWN 🔴", l1['close']
    
    return "NEUTRAL ⚪", l1['close']

def send_telegram_message(text):
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                  data={'chat_id': TELEGRAM_CHAT_ID, 'text': text})

def main():
    send_telegram_message("✅ บอทโหมดวิเคราะห์ 2 Timeframe (1m & 3m) เริ่มงานแล้ว! 🚀")
    
    while True:
        now = datetime.now()
        # เงื่อนไขเวลาเดิม: นาทีที่ 0/5 วินาทีที่ 40
        if now.minute % 5 == 0 and now.second == 40: 
            try:
                df1 = get_binance_data("1m")
                df3 = get_binance_data("3m")
                
                if not df1.empty and not df3.empty:
                    signal, price = get_signal(df1, df3)
                    
                    msg = (f"🔮 PancakeSwap (1m & 3m Analysis)\n"
                           f"📍 สัญญาณ: {signal}\n"
                           f"💰 ราคา: ${price:.2f}\n"
                           f"⏳ รอบเวลา: {now.strftime('%H:%M:%S')}")
                    send_telegram_message(msg)
                    
                time.sleep(70) # เว้นระยะ 70 วิ ตามเงื่อนไขคุณ
            except:
                time.sleep(5)
        else:
            time.sleep(1)

if __name__ == "__main__":
    main()
