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
        # คำนวณอินดิเคเตอร์
        df['ema_50'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
        stoch = ta.momentum.StochasticOscillator(df['h'], df['l'], df['close'])
        df['stoch'] = stoch.stoch()
        return df
    except:
        return pd.DataFrame()

def get_signal(df_1m, df_3m, df_5m):
    # วิเคราะห์แต่ละ Timeframe
    def check(df):
        latest = df.iloc[-1]
        # สัญญาณ UP: ราคา > EMA50 และ Stochastic < 80 (ยังไม่แพงเกินไป)
        if latest['close'] > latest['ema_50'] and latest['stoch'] < 80: return 1
        # สัญญาณ DOWN: ราคา < EMA50 และ Stochastic > 20 (ยังไม่ถูกเกินไป)
        if latest['close'] < latest['ema_50'] and latest['stoch'] > 20: return -1
        return 0

    s1 = check(df_1m)
    s3 = check(df_3m)
    s5 = check(df_5m)

    # ต้องเห็นพ้องต้องกัน (อย่างน้อย 2 ใน 3 Timeframe)
    total = s1 + s3 + s5
    if total >= 2: return "UP 🟢", df_5m.iloc[-1]['close']
    if total <= -2: return "DOWN 🔴", df_5m.iloc[-1]['close']
    return "WAIT ⚪", df_5m.iloc[-1]['close']

def send_telegram_message(text):
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                  data={'chat_id': TELEGRAM_CHAT_ID, 'text': text})

def main():
    send_telegram_message("✅ บอทโหมดวิเคราะห์ 3 Timeframe (1m, 3m, 5m) เริ่มงานแล้ว! 🚀")
    
    while True:
        now = datetime.now()
        # ทำงานทุก 5 นาที (นาทีที่ 0, 5, 10...) ที่วินาทีที่ 40
        if now.minute % 5 == 0 and now.second == 40: 
            try:
                df1 = get_binance_data("1m")
                df3 = get_binance_data("3m")
                df5 = get_binance_data("5m")
                
                if not df1.empty and not df3.empty and not df5.empty:
                    signal, price = get_signal(df1, df3, df5)
                    
                    if signal != "WAIT ⚪":
                        msg = (f"🔮 PancakeSwap Multi-TF Analysis\n"
                               f"📍 สัญญาณ: {signal}\n"
                               f"💰 ราคา: ${price:.2f}\n"
                               f"⏳ ยืนยันแนวโน้มจาก 3 Timeframe (1m/3m/5m)")
                        send_telegram_message(msg)
                    else:
                        print(f"[{now.strftime('%H:%M:%S')}] สัญญาณไม่ชัดเจน (Skipped)")
                    
                time.sleep(70) # เว้นระยะ 70 วิ ตามเงื่อนไขเวลา
            except:
                time.sleep(5)
        else:
            time.sleep(1)

if __name__ == "__main__":
    main()
