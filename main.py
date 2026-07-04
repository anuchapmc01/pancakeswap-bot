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
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    df['ema_50'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
    
    macd = ta.trend.MACD(df['close'])
    df['macd_line'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()

    latest = df.iloc[-1]
    
    # ปรับให้ส่งสัญญาณได้กว้างขึ้น (ไม่คัดออกแล้ว)
    if (latest['close'] > latest['ema_50'] and latest['macd_line'] > latest['macd_signal']):
        return "UP 🟢", latest['close'], latest['rsi']
    elif (latest['close'] < latest['ema_50'] and latest['macd_line'] < latest['macd_signal']):
        return "DOWN 🔴", latest['close'], latest['rsi']
    else:
        return "NEUTRAL ⚪", latest['close'], latest['rsi']

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': text}
    requests.post(url, data=payload)

def main():
    send_telegram_message("✅ บอทกลับมาส่งสัญญาณทุกรอบแล้วครับ! พร้อมใช้งาน 🚀")
    
    while True:
        now = datetime.now()
        
        # เงื่อนไขเวลาที่คุณต้องการ: นาทีที่ 0/5 วินาทีที่ 40
        if now.minute % 5 == 0 and now.second == 40: 
            try:
                df = get_binance_data()
                if not df.empty:
                    signal, price, rsi = analyze_trend(df)
                    
                    # ส่งแจ้งเตือนทุกรอบไม่ว่าจะเป็นสัญญาณอะไร
                    msg = (
                        f"🔮 PancakeSwap Prediction\n"
                        f"📍 สัญญาณ: {signal}\n"
                        f"💰 ราคา: ${price:.2f}\n"
                        f"📊 RSI: {rsi:.2f}\n"
                        f"⏳ รีบลงเดิมพันก่อนปุ่มล็อค!"
                    )
                    send_telegram_message(msg)
                    
                # เว้นช่วง 70 วินาที ตามเงื่อนไขคุณ
                time.sleep(70) 
                
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(5)
        else:
            time.sleep(1)

if __name__ == "__main__":
    main()
