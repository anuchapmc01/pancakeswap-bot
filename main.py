import time
import requests
import pandas as pd
import ta
from datetime import datetime
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

def get_binance_data(interval="1m", limit=100):
    url = f"https://data-api.binance.vision/api/v3/klines?symbol=BNBUSDT&interval={interval}&limit={limit}"
    try:
        data = requests.get(url, timeout=10).json()
        df = pd.DataFrame(data, columns=['ts','o','h','l','close','v','ct','q','t','tb','tq','i'])
        for col in ['close','h','l','o','v']:
            df[col] = pd.to_numeric(df[col])
        df['ema_20'] = ta.trend.EMAIndicator(df['close'], window=20).ema_indicator()
        df['rsi']    = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
        stoch        = ta.momentum.StochasticOscillator(df['h'], df['l'], df['close'])
        df['stoch']  = stoch.stoch()
        return df
    except Exception as e:
        print(f"[ERROR] Binance: {e}")
        return pd.DataFrame()

def get_signal(df_1m, df_3m):
    l1 = df_1m.iloc[-1]
    l3 = df_3m.iloc[-1]
    required = ['close','ema_20','rsi','stoch']
    if any(pd.isna(l1[c]) for c in required) or pd.isna(l3['ema_20']):
        return "NEUTRAL ⚪", l1['close'], "ข้อมูลไม่พอ"
    price = l1['close']
    ema_diff_3m = (l3['close'] - l3['ema_20']) / l3['ema_20'] * 100
    ema_diff_1m = (l1['close'] - l1['ema_20']) / l1['ema_20'] * 100
    
    if (ema_diff_3m > -0.05 and ema_diff_1m > -0.05 and 35 < l1['rsi'] < 78 and l1['stoch'] < 88):
        reason = "\n".join([
            "✅ ราคาใกล้/เหนือ EMA20",
            f"✅ RSI: {l1['rsi']:.1f}",
            f"✅ Stoch: {l1['stoch']:.1f}",
            f"📈 EMA diff: {ema_diff_1m:+.3f}%"
        ])
        return "UP 🟢", price, reason
    elif (ema_diff_3m < 0.05 and ema_diff_1m < 0.05 and 22 < l1['rsi'] < 65 and l1['stoch'] > 12):
        reason = "\n".join([
            "✅ ราคาใกล้/ต่ำกว่า EMA20",
            f"✅ RSI: {l1['rsi']:.1f}",
            f"✅ Stoch: {l1['stoch']:.1f}",
            f"📉 EMA diff: {ema_diff_1m:+.3f}%"
        ])
        return "DOWN 🔴", price, reason
    miss = [
        f"RSI: {l1['rsi']:.1f} | Stoch: {l1['stoch']:.1f}",
        f"EMA diff 1m: {ema_diff_1m:+.3f}% | 3m: {ema_diff_3m:+.3f}%"
    ]
    return "NEUTRAL ⚪", price, "⏸ สัญญาณยังไม่ชัด:\n" + "\n".join(miss)

def send_telegram_message(text):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                      data={'chat_id': TELEGRAM_CHAT_ID, 'text': text}, timeout=10)
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")

def main():
    send_telegram_message("✅ Bot โละระบบเวลาเดิมทิ้ง ใช้การจับเวลาจากนาฬิกาเป๊ะๆ แล้วครับ! 🚀")

    while True:
        now = datetime.now()
        
        # 📌 หัวใจสำคัญ: สั่งทำงานที่ นาทีที่ 4 (และ 9) วินาทีที่ 30 เป๊ะๆ (เช่น 02:34:30)
        if now.minute % 5 == 4 and now.second == 30: 
            try:
                df1 = get_binance_data("1m")
                df3 = get_binance_data("3m")

                if not df1.empty and not df3.empty:
                    signal, price, reason = get_signal(df1, df3)

                    if "UP" in signal:
                        action = "👆 แนะนำ: กด ENTER UP"
                    elif "DOWN" in signal:
                        action = "👇 แนะนำ: กด ENTER DOWN"
                    else:
                        action = "⏸ แนะนำ: ข้ามรอบนี้"

                    # แสดงผลเวลา 30 วิ + บวกเพิ่ม 10 วิ ในข้อความ ตามที่คุณสั่ง
                    display_secs = 30 + 10 
                    
                    msg = (
                        f"🔮 PancakeSwap Prediction\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"📍 สัญญาณ: {signal}\n"
                        f"{action}\n"
                        f"💰 ราคา: ${price:.4f}\n"
                        f"📊 {reason}\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"⏳ เหลือเวลาแทง: ~{display_secs}s\n"
                        f"🕐 เวลาจริง: {now.strftime('%H:%M:%S')}"
                    )
                    send_telegram_message(msg)
                    
                time.sleep(70) # หยุด 70 วิ กันบอทส่งซ้ำในรอบเดิม
                
            except Exception as e:
                print(f"[ERROR] main: {e}")
                send_telegram_message(f"❌ Error: {e}")
                time.sleep(5)
        else:
            time.sleep(1)

if __name__ == "__main__":
    main()
