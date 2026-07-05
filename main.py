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
    df_1m['rsi'] = ta.momentum.RSIIndicator(df_1m['close'], window=14).rsi()
    df_1m['ema_20'] = ta.trend.EMAIndicator(df_1m['close'], window=20).ema_indicator()
    stoch_1m = ta.momentum.StochasticOscillator(df_1m['high'], df_1m['low'], df_1m['close'])
    df_1m['stoch'] = stoch_1m.stoch()
    
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
    startup_msg = "✅ บอท PancakeSwap v25 (ดีเลย์รอบแรก 2.30 นาที + หน่วง 10 วิหลังส่ง) พร้อมลุยครับ! 🚀"
    send_telegram_message(startup_msg)
    print("Bot started. Waiting for first alignment at XX:X4:40 or XX:X9:40...")
    
    # 🎯 1. ตั้งหลักรอบแรก: ปรับดีเลย์ออกไปอีก 2 นาทีครึ่ง ขยับมาเริ่มที่ นาทีลงท้ายด้วย 4 หรือ 9 ณ วินาทีที่ 40 ของเครื่อง
    while True:
        now = datetime.now()
        if (now.minute % 5 == 4 or now.minute % 5 == 9) and now.second == 40:
            break
        time.sleep(0.5)

    while True:
        try:
            now = datetime.now()
            print(f"[{now.strftime('%H:%M:%S')}] ถึงจังหวะประมวลผลสัญญาณ...")
            
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
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ส่งสัญญาณสำเร็จ")
                
                # 📌 2. ส่งเสร็จปุ๊บ -> หน่วงรอยต่อเคลียร์ระบบเว็บ 10 วินาทีทันทีตามสั่ง
                print("-> [ACTION] เริ่มนับหน่วงเวลาช่วงปิดระบบเว็บ 10 วินาที...")
                time.sleep(10)
                
                # 📌 3. ครบ 10 วิ -> นับถอยหลังต่ออีก 260 วินาที เพื่อล็อกจังหวะเข้าทำรอบถัดไป
                print("-> [ACTION] ครบ 10 วิ เริ่มเข้าลูปนับถอยหลังอีก 260 วินาทีเพื่อรอส่งรอบหน้า...")
                time.sleep(260)
            else:
                print("ดึงข้อมูลพลาด รอ 5 วิ...")
                time.sleep(5)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
