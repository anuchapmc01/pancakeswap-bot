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
        df['open'] = pd.to_numeric(df['open'])
        df['timestamp'] = pd.to_numeric(df['timestamp'])
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
    price_velocity = latest['close'] - latest['open'] 
    estimated_lock_price = latest['close'] + (price_velocity * 0.5)
    
    signal = "WAIT"
    if (latest['close'] > latest['ema_50'] and latest['ema_9'] > latest['ema_21'] and 
        latest['macd_line'] > latest['macd_signal'] and 45 <= latest['rsi'] <= 65 and
        estimated_lock_price > latest['close']): 
        signal = "UP 🟢"
    elif (latest['close'] < latest['ema_50'] and latest['ema_9'] < latest['ema_21'] and 
          latest['macd_line'] < latest['macd_signal'] and 35 <= latest['rsi'] <= 55 and
          estimated_lock_price < latest['close']): 
        signal = "DOWN 🔴"
        
    return signal, latest['close'], latest['rsi'], estimated_lock_price

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': text}
    requests.post(url, data=payload)

def main():
    startup_msg = "✅ บอท PancakeSwap v15 (ล็อกเป้าหมาย 30 วิสุดท้ายถาวร) เริ่มทำงานแล้วครับ! 🚀"
    send_telegram_message(startup_msg)
    print("Bot started.")
    
    last_alerted_round = -1

    while True:
        try:
            now = datetime.now()
            
            # คำนวณหาตำแหน่งวินาทีในรอบ 5 นาทีปัจจุบันของนาฬิกาเครื่อง (0 - 299 วินาที)
            current_secs_in_round = (now.minute % 5) * 60 + now.second
            
            # 🎯 ล็อกเป้าหมาย: บอทจะส่งสัญญาณก็ต่อเมื่อเวลาของรอบเดินไปถึงวินาทีที่ 265 
            # ซึ่งในจังหวะนี้หน้าเว็บของพี่จะเหลือเวลานับถอยหลังประมาณ 30-35 วินาทีสุดท้ายพอดีเป๊ะ
            if current_secs_in_round == 265:
                # คำนวณ ID ของรอบปัจจุบันเพื่อป้องกันการส่งซ้ำ
                current_round_id = (now.hour * 12) + (now.minute // 5)
                
                if current_round_id != last_alerted_round:
                    df = get_binance_data()
                    if df.empty:
                        continue
                        
                    signal, price, rsi, est_lock = analyze_trend(df)
                    
                    if signal != "WAIT":
                        msg = (
                            f"🔮 PancakeSwap 5m Prediction\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"📍 สัญญาณ: {signal}\n"
                            f"💰 ราคา BNB ปัจจุบัน: ${price:.2f}\n"
                            f"🎯 คาดการณ์ราคาสัญญาณล็อก: ${est_lock:.2f}\n"
                            f"📊 RSI (1m): {rsi:.2f}\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"⏳ รีบลงเดิมพันด่วน! (เหลือประมาณ 30 วิ)\n"
                            f"🕐 เวลาส่ง: {now.strftime('%H:%M:%S')}"
                        )
                    else:
                        msg = (
                            f"⏸ PancakeSwap 5m Prediction\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"📍 สัญญาณ: ข้ามรอบนี้ (ทรงกราฟไม่ชัวร์)\n"
                            f"💰 ราคาปัจจุบัน: ${price:.2f}\n"
                            f"🎯 คาดการณ์ราคาล็อก: ${est_lock:.2f}\n"
                            f"📊 RSI (1m): {rsi:.2f}\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"🕐 เวลาส่ง: {now.strftime('%H:%M:%S')}"
                        )
                    
                    send_telegram_message(msg)
                    last_alerted_round = current_round_id
                    
                    # พักระบบ 10 วินาทีเพื่อป้องกันลูปวินาทีเดิมทำงานซ้ำ
                    time.sleep(10)
                    
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(2)
            
        time.sleep(0.2)

if __name__ == "__main__":
    main()
