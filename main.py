import requests
import pandas as pd
import ta
import time
from datetime import datetime
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def get_binance_5m_data():
    url = "https://data-api.binance.vision/api/v3/klines?symbol=BNBUSDT&interval=5m&limit=100"
    try:
        response = requests.get(url, timeout=5).json()
        df = pd.DataFrame(response, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        for col in ['close', 'open', 'high', 'low', 'volume']:
            df[col] = pd.to_numeric(df[col])
        return df
    except:
        return pd.DataFrame()

def analyze_ultimate_strategy(df):
    if df.empty or len(df) < 35:
        return "รอข้อมูล", "ข้าม", "ดึงข้อมูลจาก Binance ไม่สำเร็จ", 0, 100

    # 1. คำนวณอินดิเคเตอร์
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    df['ema_9'] = ta.trend.EMAIndicator(df['close'], window=9).ema_indicator()
    df['ema_21'] = ta.trend.EMAIndicator(df['close'], window=21).ema_indicator()
    
    macd = ta.trend.MACD(df['close'])
    df['macd_line'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    
    stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
    df['stoch_k'] = stoch.stoch()
    
    indicator_bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_high'] = indicator_bb.bollinger_hband()
    df['bb_low'] = indicator_bb.bollinger_lband()
    df['bb_mid'] = indicator_bb.bollinger_mavg()

    df['vol_sma'] = df['volume'].rolling(window=20).mean()

    l = df.iloc[-1]   
    p = df.iloc[-2]   
    
    up_score = 0
    down_score = 0
    
    # ตรวจนับคะแนน 6 มิติ (รวม 100%)
    if l['close'] > l['ema_9'] and l['ema_9'] > l['ema_21']: up_score += 20
    elif l['close'] < l['ema_9'] and l['ema_9'] < l['ema_21']: down_score += 20
        
    if l['macd_line'] > l['macd_signal']: up_score += 20
    elif l['macd_line'] < l['macd_signal']: down_score += 20
        
    if 52 <= l['rsi'] <= 68: up_score += 15
    elif 32 <= l['rsi'] <= 48: down_score += 15
        
    if 20 < l['stoch_k'] < 80: 
        if l['close'] > p['close']: up_score += 15
        elif l['close'] < p['close']: down_score += 15

    if l['close'] > l['bb_mid'] and l['close'] < l['bb_high']: up_score += 15
    elif l['close'] < l['bb_mid'] and l['close'] > l['bb_low']: down_score += 15

    if l['volume'] > l['vol_sma']:
        if l['close'] > p['close']: up_score += 15
        elif l['close'] < p['close']: down_score += 15

    # --- ส่วนที่แก้ไข: แยกการวิเคราะห์ทิศทาง ออกจาก คำแนะนำ ---
    
    # 1. สรุปทิศทางที่คะแนนเยอะกว่า (แสดงเสมอ)
    if up_score > down_score:
        prediction = "🟢 คาดว่ามีแนวโน้มปิด **สูงกว่า** แท่งปัจจุบัน"
        win_p = up_score
        lean = "UP"
    elif down_score > up_score:
        prediction = "🔴 คาดว่ามีแนวโน้มปิด **ต่ำกว่า** แท่งปัจจุบัน"
        win_p = down_score
        lean = "DOWN"
    else:
        prediction = "⚪ กราฟสูสีมาก (50/50)"
        win_p = 50
        lean = "NONE"

    # 2. ให้คำแนะนำโดยอิงจากเกณฑ์ความปลอดภัย 80%
    if win_p >= 80:
        action = f"✅ แนะนำให้ **เล่นได้** (กด {lean})"
        reason = f"อินดิเคเตอร์ชี้ไปทางเดียวกันหนาแน่นถึง {win_p}% มีแรงซื้อขายสนับสนุนชัดเจน"
    else:
        action = "⏸ แนะนำให้ **ข้ามรอบนี้** (WAIT)"
        reason = f"ความมั่นใจอยู่ที่ {win_p}% (ยังไม่ถึงเกณฑ์ปลอดภัย 80%) กราฟมีความขัดแย้ง เสี่ยงโดนหลอกสูง"

    loss_p = 100 - win_p
    return prediction, action, reason, win_p, loss_p

def send_telegram_message(text):
    url = "https://api.telegram.org/bot{}/sendMessage".format(TELEGRAM_BOT_TOKEN)
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': text}
    try: requests.post(url, data=payload, timeout=5)
    except: pass

def main():
    print("บอทวิเคราะห์พร้อมแสดงเปอร์เซ็นต์ทุกรอบ (BNB 5m) เริ่มทำงาน...")
    last_alerted_minute = -1

    while True:
        try:
            now = datetime.now()
            # ยิงสัญญาณวินาทีสุดท้ายก่อนปิดแท่ง 5 นาที
            if (now.minute % 5 == 4) and now.second == 45:
                if now.minute != last_alerted_minute:
                    df = get_binance_5m_data()
                    prediction, action, reason, win_p, loss_p = analyze_ultimate_strategy(df)
                    
                    msg = (
                        "🎯 วิเคราะห์ BNB/USDT (แท่ง 5m ถัดไป)\n"
                        "━━━━━━━━━━━━━━━\n"
                        "📈 ทิศทาง: {}\n"
                        "🎯 คำแนะนำ: {}\n"
                        "💡 เหตุผล: {}\n"
                        "━━━━━━━━━━━━━━━\n"
                        "📊 โอกาสถูกต้อง: {}%\n"
                        "🚨 โอกาสผิดพลาด: {}%\n"
                        "🕐 เวลาคำนวณ: {}\n"
                        "━━━━━━━━━━━━━━━"
                    ).format(prediction, action, reason, win_p, loss_p, now.strftime('%H:%M:%S'))
                    
                    send_telegram_message(msg)
                    last_alerted_minute = now.minute
                    time.sleep(10)
            
            time.sleep(0.5)
        except Exception as e:
            print("Error: {}".format(e))
            time.sleep(2)

if __name__ == "__main__":
    main()
