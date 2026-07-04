import time
import requests
import pandas as pd
import ta
from datetime import datetime
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def get_binance_data(interval="1m"):
    # ปรับ limit เป็น 100 ตามที่คุณต้องการเพื่อให้คำนวณค่า EMA ได้แม่นยำ
    url = f"https://data-api.binance.vision/api/v3/klines?symbol=BNBUSDT&interval={interval}&limit=100"
    try:
        data = requests.get(url).json()
        df = pd.DataFrame(data, columns=['ts', 'o', 'h', 'l', 'close', 'v', 'ct', 'q', 't', 'tb', 'tq', 'i'])
        df['close'] = pd.to_numeric(df['close'])
        df['ema_50'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
        stoch = ta.momentum.StochasticOscillator(df['h'], df['l'], df['close'])
        df['stoch'] = stoch.stoch()
        return df
    except:
        return pd.DataFrame()

def get_signal(df_1m, df_3m):
    l1 = df_1m.iloc[-1]
    l3 = df_3m.iloc[-1]
    
    # เงื่อนไขเดิม: ทั้ง 1m และ 3m ต้องเห็นพ้องต้องกัน
    if (l1['close'] > l1['ema_50'] and l3['close'] > l3['ema_50'] and 
        l1['stoch'] < 80 and l3['stoch'] < 80):
        return "UP 🟢", l1['close']
    elif (l1['close'] < l1['ema_50'] and l3['close'] < l3['ema_50'] and 
          l1['stoch'] > 20 and l3['stoch'] > 20):
        return "DOWN 🔴", l1['close']
    
    return "NEUTRAL ⚪", l1['close']

def send_telegram_message(text):
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                  data={'chat_id': TELEGRAM_CHAT_ID, 'text': text})

def main():
    send_telegram_message("✅ บอทปรับเวลาเตือนช้าลง 1 นาที พร้อมระบบ 2 Timeframe และ Data 100 แท่ง! 🚀")
    
    while True:
        now = datetime.now()
        
        # ปรับจังหวะเวลา: นาทีที่ (1, 6, 11...) วินาทีที่ 40
        if now.minute % 5 == 1 and now.second == 40: 
            try:
                df1 = get_binance_data("1m")
                df3 = get_binance_data("3m")
                
                if not df1.empty and not df3.empty:
                    signal, price = get_signal(df1, df3)
                    
                    msg = (f"🔮 PancakeSwap Multi-TF Analysis\n"
                           f"📍 สัญญาณ: {signal}\n"
                           f"💰 ราคา: ${price:.2f}\n"
                           f"⏳ เวลาที่ส่ง: {now.strftime('%H:%M:%S')}")
                    send_telegram_message(msg)
                    
                time.sleep(70) # เว้นระยะ 70 วินาที เพื่อกันการเหลื่อมเวลา
            except:
                time.sleep(5)
        else:
            time.sleep(1)

if __name__ == "__main__":
    main()
