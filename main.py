import time
import requests
import pandas as pd
import ta
from datetime import datetime
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def get_binance_data(interval="1m", limit=100):
    url = f"https://data-api.binance.vision/api/v3/klines?symbol=BNBUSDT&interval={interval}&limit={limit}"
    try:
        response = requests.get(url, timeout=5).json()
        if isinstance(response, dict) and 'code' in response:
            return pd.DataFrame()
        df = pd.DataFrame(response, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        for col in ['close', 'open', 'high', 'low']:
            df[col] = pd.to_numeric(df[col])
        return df
    except:
        return pd.DataFrame()

def analyze_trend(df_1m, df_3m):
    # คำนวณอินดิเคเตอร์ 1 นาที
    df_1m['rsi'] = ta.momentum.RSIIndicator(df_1m['close'], window=14).rsi()
    df_1m['ema_20'] = ta.trend.EMAIndicator(df_1m['close'], window=20).ema_indicator()
    stoch_1m = ta.momentum.StochasticOscillator(df_1m['high'], df_1m['low'], df_1m['close'])
    df_1m['stoch'] = stoch_1m.stoch()
    
    # คำนวณอินดิเคเตอร์ 3 นาที
    df_3m['ema_20'] = ta.trend.EMAIndicator(df_3m['close'], window=20).ema_indicator()
    
    l1 = df_1m.iloc[-1]
    l3 = df_3m.iloc[-1]
    
    ema_diff_1m = (l1['close'] - l1['ema_20']) / l1['ema_20'] * 100
    ema_diff_3m = (l3['close'] - l3['ema_20']) / l3['ema_20'] * 100
    
    price_velocity = l1['close'] - l1['open']
    estimated_lock_price = l1['close'] + (price_velocity * 0.5)
    
    signal = "WAIT"
    reason = "⏸ สัญญาณยังไม่ชัดเจน"
    
    if (ema_diff_3m > -0.05 and ema_diff_1m > -0.05 and 
        35 < l1['rsi'] < 78 and l1['stoch'] < 88 and 
        estimated_lock_price > l1['close']):
        signal = "UP 🟢"
        reason = f"✅ ราคาใกล้/เหนือ EMA20\n✅ RSI: {l1['rsi']:.1f}\n✅ Stoch: {l1['stoch']:.1f}\n📈 EMA diff 1m: {ema_diff_1m:+.3f}%"
        
    elif (ema_diff_3m < 0.05 and ema_diff_1m < 0.05 and 
          22 < l1['rsi'] < 65 and l1['stoch'] > 12 and 
          estimated_lock_price < l1['close']):
        signal = "DOWN 🔴"
        reason = f"✅ ราคาใกล้/ต่ำกว่า EMA20\n✅ RSI: {l1['rsi']:.1f}\n✅ Stoch: {l1['stoch']:.1f}\n📉 EMA diff 1m: {ema_diff_1m:+.3f}%"
    
    if signal == "WAIT":
        reason = f"RSI: {l1['rsi']:.1f} | Stoch: {l1['stoch']:.1f}\nEMA diff 1m: {ema_diff_1m:+.3f}% | 3m: {ema_diff_3m:+.3f}%"
        
    return signal, l1['close'], reason, estimated_lock_price

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': text}
    try:
        requests.post(url, data=payload, timeout=5)
    except:
        pass

def main():
    startup_msg = "✅ บอท PancakeSwap v22 (ระบบดีเลย์ตรงเวลาเครื่อง หน่วง 2 นาทีครึ่ง) พร้อมลุยแล้วครับ! 🚀"
    send_telegram_message(startup_msg)
    print("Bot started. Monitoring time by simple local clock...")
    
    last_alerted_minute = -1

    while True:
        try:
            now = datetime.now()
            
            # 🎯 ล็อกเวลาเครื่องตรงๆ: หน่วงเวลาเพิ่ม 2 นาทีครึ่งจากล็อกนาทีที่ 4 และ 9 
            # (ขยับมาทำงานที่ นาทีลงท้ายด้วย 1 และ 6 ณ วินาทีที่ 00 เป๊ะๆ แทนการไปยุ่งกับวินาทีลอยๆ)
            if (now.minute % 5 == 1 or now.minute % 5 == 6) and now.second == 0:
                if now.minute != last_alerted_minute:
                    print(f"[{now.strftime('%H:%M:%S')}] ได้จังหวะเวลาล็อก! กำลังคำนวณสัญญาณ...")
                    
                    df1 = get_binance_data(interval="1m")
                    df3 = get_binance_data(interval="3m")
                    
                    if not df1.empty and not df3.empty:
                        signal, price, reason, est_lock = analyze_trend(df1, df3)
                        
                        action = "👆 แนะนำ: กด ENTER UP" if "UP" in signal else "👇 แนะนำ: กด ENTER DOWN" if "DOWN" in signal else "⏸ แนะนำ: ข้ามรอบนี้"
                        
                        msg = (
                            f"🔮 PancakeSwap 5m Prediction\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"📍 สัญญาณ: {signal}\n"
                            f"{action}\n"
                            f"💰 ราคา: ${price:.4f}\n"
                            f"🎯 คาดการณ์ราคาล็อก: ${est_lock:.4f}\n"
                            f"📊 {reason}\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"⏳ เหลือเวลาแทงก่อนปุ่มปิด: ~30s\n"
                            f"🕐 เวลาส่ง: {now.strftime('%H:%M:%S')}"
                        )
                        
                        send_telegram_message(msg)
                        last_alerted_minute = now.minute
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ส่งสำเร็จในรอบนาทีที่ {now.minute}")
            
            # เช็กเวลาถี่ยิบทุก 0.5 วิ ไม่มีพลาดวินาทีที่ 00
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()
