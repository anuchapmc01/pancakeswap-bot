import time
import requests
import pandas as pd
import ta
from datetime import datetime
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def get_binance_data(symbol="BNBUSDT", interval="1m", limit=30):
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
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    df['ema_9'] = ta.trend.EMAIndicator(df['close'], window=9).ema_indicator()
    df['ema_21'] = ta.trend.EMAIndicator(df['close'], window=21).ema_indicator()
    latest = df.iloc[-1]
    
    signal = "WAIT"
    if latest['ema_9'] > latest['ema_21'] and latest['rsi'] < 45:
        signal = "UP 🟢"
    elif latest['ema_9'] < latest['ema_21'] and latest['rsi'] > 55:
        signal = "DOWN 🔴"
    return signal, latest['close'], latest['rsi']

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': text}
    requests.post(url, data=payload)

def main():
    # ส่งข้อความทดสอบเข้า Telegram ทันทีที่รันบอท
    startup_msg = "✅ บอท PancakeSwap 5m Prediction เริ่มทำงานแล้ว!\nระบบกำลังสแตนด์บายรอจับสัญญาณครับ 🚀"
    send_telegram_message(startup_msg)
    print("Bot started. Startup message sent to Telegram.")
    
    while True:
        now = datetime.now()
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
                    print(f"[{now.strftime('%H:%M:%S')}] Skipped.")
                time.sleep(60)
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(5)
        else:
            time.sleep(1)

if __name__ == "__main__":
    main()
