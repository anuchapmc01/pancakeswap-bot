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
    startup_msg = "✅ บอท PancakeSwap ปรับเวลาเริ่มต้นช้าลงอีก 20 วิ (รวมเริ่มต้นหน่วง 65 วิ) เรียบร้อยแล้ว! 🚀"
    send_telegram_message(startup_msg)
    print("Bot started.")
    
    last_alerted_minute = -1
    
    # 🛠 ปรับค่าเริ่มต้นจาก 45 เป็น 65 เพื่อให้แจ้งเตือนช้าลงอีก 20 วินาที
    accumulated_delay = 65  

    while True:
        now = datetime.now()
        
        target_second = accumulated_delay
        check_minute = now.minute
        
        # จัดการวินาทีถ้าสะสมจนเกิน 60 ให้ขยับนาทีตามอัตโนมัติ (เช่น 65 วิ จะกลายเป็น +1 นาที กับอีก 5 วินาที)
        if target_second >= 60:
            check_minute += (target_second // 60)
            target_second = target_second % 60

        # ทำงานที่นาทีลงท้ายด้วย 1 หรือ 6 ตามบล็อกเวลาหลัก
        if (check_minute % 5 == 1 or check_minute % 5 == 6) and now.second == target_second:
            if now.minute != last_alerted_minute:
                try:
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
                            f"⏳ รีบลงเดิมพันด่วน!\n"
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
                    last_alerted_minute = now.minute
                    
                    # หลังส่งเสร็จในแต่ละรอบ ให้บวกเพิ่มอีก 10 วินาทีตามตรรกะเดิม
                    accumulated_delay += 10
                    print(f"[{now.strftime('%H:%M:%S')}] ส่งสัญญาณแล้ว -> ปรับเพิ่มเวลาหน่วงรอบถัดไปเป็น +{accumulated_delay} วิ")
                    
                    time.sleep(70)  
                except Exception as e:
                    print(f"Error: {e}")
                    time.sleep(5)
        
        time.sleep(0.5)

if __name__ == "__main__":
    main()
