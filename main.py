import time
import requests
import pandas as pd
import ta
from datetime import datetime
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def get_binance_data(symbol="BNBUSDT", interval="1m", limit=100):
    # ปรับ limit เป็น 100 เพื่อให้มีข้อมูลพอสำหรับคำนวณเส้น EMA 50
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    response = requests.get(url).json()
    df = pd.DataFrame(response, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'trades',
        'taker_buy_base', 'taker_buy_quote', 'ignore'
    ])
    df['close'] = pd.to_numeric(df['close'])
    return df

def analyze_trend(df):
    """ส่วนของสมองกลยุทธ์ (Strategy)"""
    # 1. RSI (วัดความสวิง แรงซื้อ/แรงขาย)
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    
    # 2. EMA (ดูเทรนด์)
    df['ema_9'] = ta.trend.EMAIndicator(df['close'], window=9).ema_indicator()
    df['ema_21'] = ta.trend.EMAIndicator(df['close'], window=21).ema_indicator()
    df['ema_50'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator() # เส้นเทรนด์หลัก
    
    # 3. MACD (ดูแรงส่ง หรือ Momentum)
    macd = ta.trend.MACD(df['close'])
    df['macd_line'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()

    latest = df.iloc[-1]
    signal = "WAIT"
    
    # 🟢 กลยุทธ์ขาขึ้น (UP):
    # - ราคาอยู่เหนือ EMA 50 (เทรนด์หลักเป็นขาขึ้น)
    # - EMA 9 อยู่เหนือ EMA 21 (เทรนด์รองเป็นขาขึ้น)
    # - MACD Line ชี้ตัดขึ้นเหนือ Signal (มีแรงส่งซื้อ)
    # - RSI อยู่ระหว่าง 45-65 (มีแรงส่ง และยังมีพื้นที่ให้กราฟวิ่งขึ้นไปได้อีก ไม่ Overbought)
    if (latest['close'] > latest['ema_50'] and 
        latest['ema_9'] > latest['ema_21'] and 
        latest['macd_line'] > latest['macd_signal'] and 
        45 <= latest['rsi'] <= 65):
        signal = "UP 🟢"
        
    # 🔴 กลยุทธ์ขาลง (DOWN):
    # - ราคาอยู่ใต้ EMA 50 (เทรนด์หลักเป็นขาลง)
    # - EMA 9 อยู่ใต้ EMA 21 (เทรนด์รองเป็นขาลง)
    # - MACD Line ชี้ตัดลงใต้ Signal (มีแรงส่งขาย)
    # - RSI อยู่ระหว่าง 35-55 (มีแรงส่ง และยังมีพื้นที่ให้กราฟวิ่งลงไปได้อีก ไม่ Oversold)
    elif (latest['close'] < latest['ema_50'] and 
          latest['ema_9'] < latest['ema_21'] and 
          latest['macd_line'] < latest['macd_signal'] and 
          35 <= latest['rsi'] <= 55):
        signal = "DOWN 🔴"
        
    return signal, latest['close'], latest['rsi']

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': text}
    requests.post(url, data=payload)

def main():
    startup_msg = "✅ บอท PancakeSwap (อัปเกรดกลยุทธ์ MACD+EMA50) เริ่มทำงานแล้ว!\nระบบกำลังสแตนด์บายรอจับสัญญาณครับ 🚀"
    send_telegram_message(startup_msg)
    print("Bot started. Startup message sent.")
    
    while True:
        now = datetime.now()
        # เช็คเวลาที่นาทีที่ 4 และ 9 ของทุกรอบ 5 นาที (บวก 30 วินาที)
        if now.minute % 5 == 4 and now.second == 30:
            try:
                df = get_binance_data()
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
