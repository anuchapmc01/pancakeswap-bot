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
    requests.post(url, data=payload)

def main():
    startup_msg = "✅ บอท PancakeSwap (ปรับเตือนเร็วขึ้น 30 วิ) เริ่มทำงานแล้ว! 🚀"
    send_telegram_message(startup_msg)
    
    while True:
        now = datetime.now()
        
        # ปรับให้เตือนที่วินาทีที่ 0 (เร็วขึ้น 30 วินาทีจากของเดิมที่เตือนวินาทีที่ 30)
        if now.minute % 5 == 4 and now.second == 0: 
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
                        f"⏳ รีบลงเดิมพันก่อนปุ่มล็อค!"
                    )
                    send_telegram_message(msg)
                else:
                    msg = (
                        f"⏸ PancakeSwap 5m Prediction\n"
                        f"📍 สัญญาณ: ข้ามรอบนี้ (ทรงกราฟไม่ชัวร์)\n"
                        f"💰 ราคาปัจจุบัน: ${price:.2f}\n"
                        f"📊 RSI (1m): {rsi:.2f}"
                    )
                    send_telegram_message(msg)
                    
                time.sleep(70) # เว้นช่วงรอบการประมวลผลใหม่ 70 วินาที
                
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(5)
        else:
            time.sleep(1)

if __name__ == "__main__":
    main()
