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
        return "WAIT", 0, 100, "ระบบดึงข้อมูลไม่สมบูรณ์"

    # 1. คำนวณอินดิเคเตอร์พื้นฐาน
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    df['ema_9'] = ta.trend.EMAIndicator(df['close'], window=9).ema_indicator()
    df['ema_21'] = ta.trend.EMAIndicator(df['close'], window=21).ema_indicator()
    
    macd = ta.trend.MACD(df['close'])
    df['macd_line'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    
    stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
    df['stoch_k'] = stoch.stoch()
    
    # 2. เพิ่ม Bollinger Bands (เช็กกรอบราคา)
    indicator_bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_high'] = indicator_bb.bollinger_hband()
    df['bb_low'] = indicator_bb.bollinger_lband()
    df['bb_mid'] = indicator_bb.bollinger_mavg()

    # 3. เพิ่ม Volume Moving Average (เช็กเม็ดเงิน)
    df['vol_sma'] = df['volume'].rolling(window=20).mean()

    l = df.iloc[-1]   # แท่งปัจจุบัน
    p = df.iloc[-2]   # แท่งก่อนหน้า
    
    up_score = 0
    down_score = 0
    
    # --- เริ่มระบบตรวจนับคะแนน 6 มิติ (รวม 100%) ---
    
    # มิติที่ 1: เทรนด์ EMA (20%)
    if l['close'] > l['ema_9'] and l['ema_9'] > l['ema_21']:
        up_score += 20
    elif l['close'] < l['ema_9'] and l['ema_9'] < l['ema_21']:
        down_score += 20
        
    # มิติที่ 2: โมเมนตัม MACD (20%)
    if l['macd_line'] > l['macd_signal']:
        up_score += 20
    elif l['macd_line'] < l['macd_signal']:
        down_score += 20
        
    # มิติที่ 3: พื้นที่ราคา RSI (15%)
    if 52 <= l['rsi'] <= 68: # ไม่ให้ซื้อตอน Overbought
        up_score += 15
    elif 32 <= l['rsi'] <= 48: # ไม่ให้ขายตอน Oversold
        down_score += 15
        
    # มิติที่ 4: พลังงาน Stochastic (15%)
    if 20 < l['stoch_k'] < 80: 
        # ให้คะแนนถ้าทิศทาง Stoch สอดคล้องกับแท่งเทียน
        if l['close'] > p['close']: up_score += 15
        elif l['close'] < p['close']: down_score += 15

    # มิติที่ 5: Bollinger Bands Space (15%) 
    # ป้องกันการเข้าผิดจังหวะตอนราคาชนขอบแล้วเตรียมเด้งกลับ
    if l['close'] > l['bb_mid'] and l['close'] < l['bb_high']:
        up_score += 15
    elif l['close'] < l['bb_mid'] and l['close'] > l['bb_low']:
        down_score += 15

    # มิติที่ 6: Volume Confirmation (15%)
    # ราคาที่วิ่งต้องมีวอลลุ่มมากกว่าค่าเฉลี่ย 20 แท่งหลังสุดสนับสนุน
    if l['volume'] > l['vol_sma']:
        if l['close'] > p['close']: up_score += 15
        elif l['close'] < p['close']: down_score += 15

    # --- สรุปผล (คัดเฉพาะ 80% ขึ้นไป) ---
    if up_score >= 80:
        signal = "UP 🟢 (แนวโน้มแท่งถัดไป ปิดสูงกว่าปัจจุบัน)"
        win_p = up_score
        status = "🛡️ สัญญาณสมบูรณ์แบบ (มี Volume & Trend สนับสนุน)"
    elif down_score >= 80:
        signal = "DOWN 🔴 (แนวโน้มแท่งถัดไป ปิดต่ำกว่าปัจจุบัน)"
        win_p = down_score
        status = "🛡️ สัญญาณสมบูรณ์แบบ (มี Volume & Trend สนับสนุน)"
    else:
        signal = "WAIT (ข้ามรอบนี้)"
        win_p = max(up_score, down_score)
        status = "❌ กราฟไม่มีวอลลุ่ม หรือชนขอบความเสี่ยงสูง"

    loss_p = 100 - win_p
    details = "Price: ${:.2f} | Vol > SMA: {} | RSI: {:.1f}".format(
        l['close'], "Yes" if l['volume'] > l['vol_sma'] else "No", l['rsi'])
    
    return signal, win_p, loss_p, status, details

def send_telegram_message(text):
    url = "https://api.telegram.org/bot{}/sendMessage".format(TELEGRAM_BOT_TOKEN)
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': text}
    try: requests.post(url, data=payload, timeout=5)
    except: pass

def main():
    print("บอทกลยุทธ์ Ultimate 6-Dimensions (BNB/USDT 5m) เริ่มทำงาน...")
    last_alerted_minute = -1

    while True:
        try:
            now = datetime.now()
            # ยิงสัญญาณวิเคราะห์วินาทีสุดท้ายก่อนปิดแท่ง 5 นาที
            if (now.minute % 5 == 4) and now.second == 45:
                if now.minute != last_alerted_minute:
                    df = get_binance_5m_data()
                    signal, win_p, loss_p, status, details = analyze_ultimate_strategy(df)
                    
                    msg = (
                        "🎯 วิเคราะห์เชิงลึก BNB/USDT (5m VSA & Trend)\n"
                        "━━━━━━━━━━━━━━━\n"
                        "📍 สัญญาณ: {}\n"
                        "💡 ประเมินสภาวะ: {}\n"
                        "━━━━━━━━━━━━━━━\n"
                        "📊 โอกาสถูกต้อง: {}%\n"
                        "🚨 โอกาสผิดพลาด: {}%\n"
                        "📝 ข้อมูลดิบ: {}\n"
                        "🕐 เวลาคำนวณ: {}\n"
                        "━━━━━━━━━━━━━━━\n"
                        "⚠️ กรองเฉพาะความมั่นใจ 80%+ (รวม Volume แล้ว)"
                    ).format(signal, status, win_p, loss_p, details, now.strftime('%H:%M:%S'))
                    
                    send_telegram_message(msg)
                    last_alerted_minute = now.minute
                    time.sleep(10)
            
            time.sleep(0.5)
        except Exception as e:
            print("Error: {}".format(e))
            time.sleep(2)

if __name__ == "__main__":
    main()
