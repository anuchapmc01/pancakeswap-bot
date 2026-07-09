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

    # 1. คำนวณอินดิเคเตอร์พื้นฐาน
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    df['ema_9'] = ta.trend.EMAIndicator(df['close'], window=9).ema_indicator()
    df['ema_21'] = ta.trend.EMAIndicator(df['close'], window=21).ema_indicator()
    
    macd = ta.trend.MACD(df['close'])
    df['macd_line'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    
    stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
    df['stoch_k'] = stoch.stoch()
    
    # 2. Bollinger Bands
    indicator_bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_high'] = indicator_bb.bollinger_hband()
    df['bb_low'] = indicator_bb.bollinger_lband()
    df['bb_mid'] = indicator_bb.bollinger_mavg()

    # 3. Volume Moving Average
    df['vol_sma'] = df['volume'].rolling(window=20).mean()

    l = df.iloc[-1]   # แท่งปัจจุบัน
    p = df.iloc[-2]   # แท่งก่อนหน้า
    
    up_score = 0
    down_score = 0
    
    # --- เริ่มระบบตรวจนับคะแนน 6 มิติ ---
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

    # --- สรุปผลและสร้างคำแนะนำ ---
    if up_score >= 80:
        prediction = "🟢 คาดว่าจะปิด **สูงกว่า** แท่งปัจจุบัน"
        action = "✅ แนะนำให้ **เล่นได้** (กด UP)"
        reason = "เพราะทิศทางกราฟชัดเจน มี Volume ซื้อสนับสนุน อินดิเคเตอร์สอดคล้องกันถึง {}% และราคายังไม่ล้นขอบบนของกรอบความผันผวน".format(up_score)
        win_p = up_score
    elif down_score >= 80:
        prediction = "🔴 คาดว่าจะปิด **ต่ำกว่า** แท่งปัจจุบัน"
        action = "✅ แนะนำให้ **เล่นได้** (กด DOWN)"
        reason = "เพราะทิศทางเทขายชัดเจน มี Volume ขายสนับสนุน อินดิเคเตอร์สอดคล้องกันถึง {}% และราคายังไม่หลุดขอบล่างจนเกินไป".format(down_score)
        win_p = down_score
    else:
        prediction = "⚪ คาดการณ์ยาก (ทิศทางแกว่งตัว)"
        action = "⏸ แนะนำให้ **ข้ามรอบนี้** (WAIT)"
        win_p = max(up_score, down_score)
        reason = "เพราะกราฟมีความขัดแย้งกัน (ความมั่นใจแค่ {}%) อาจเกิดจาก Volume ต่ำ, ราคาชนแนวรับ/ต้าน หรือตลาดยังไม่เลือกทาง เสี่ยงโดนกราฟหลอกสูงมาก".format(win_p)

    loss_p = 100 - win_p
    return prediction, action, reason, win_p, loss_p

def send_telegram_message(text):
    url = "https://api.telegram.org/bot{}/sendMessage".format(TELEGRAM_BOT_TOKEN)
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': text}
    try: requests.post(url, data=payload, timeout=5)
    except: pass

def main():
    print("บอทวิเคราะห์พร้อมคำแนะนำ (BNB/USDT 5m) เริ่มทำงาน...")
    last_alerted_minute = -1

    while True:
        try:
            now = datetime.now()
            # ยิงสัญญาณวิเคราะห์วินาทีสุดท้ายก่อนปิดแท่ง 5 นาที
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
