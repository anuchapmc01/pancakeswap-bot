import time
import requests
import pandas as pd
import ta
from datetime import datetime
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

last_signal = "NEUTRAL"

def get_binance_data(interval="1m", limit=100):
    url = f"https://data-api.binance.vision/api/v3/klines?symbol=BNBUSDT&interval={interval}&limit={limit}"
    try:
        data = requests.get(url, timeout=10).json()
        df = pd.DataFrame(data, columns=[
            'ts','o','h','l','close','v','ct','q','t','tb','tq','i'
        ])
        for col in ['close','h','l','o','v']:
            df[col] = pd.to_numeric(df[col])

        df['ema_50']      = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
        df['rsi']         = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
        macd              = ta.trend.MACD(df['close'])
        df['macd']        = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        stoch             = ta.momentum.StochasticOscillator(df['h'], df['l'], df['close'])
        df['stoch']       = stoch.stoch()

        # ✅ Volume MA20 — กรองตลาดเงียบ
        df['vol_ma20']    = df['v'].rolling(window=20).mean()

        return df
    except Exception as e:
        print(f"[ERROR] get_binance_data({interval}): {e}")
        return pd.DataFrame()

def get_signal(df_1m, df_3m):
    l1 = df_1m.iloc[-1]
    l3 = df_3m.iloc[-1]

    required = ['close','ema_50','rsi','macd','macd_signal','stoch','vol_ma20']
    if any(pd.isna(l1[c]) for c in required) or pd.isna(l3['ema_50']):
        return "NEUTRAL ⚪", l1['close'], "ข้อมูลไม่พอ (NaN)"

    price = l1['close']

    # ✅ Volume ต้องสูงกว่าค่าเฉลี่ย (ตลาดมีแรง)
    vol_ok = l1['v'] > l1['vol_ma20']

    # ✅ Trend 1m และ 3m ต้องไปทางเดียวกัน
    trend_up   = l1['close'] > l1['ema_50'] and l3['close'] > l3['ema_50']
    trend_down = l1['close'] < l1['ema_50'] and l3['close'] < l3['ema_50']

    # === UP ===
    if (trend_up and
        40 < l1['rsi'] < 72 and
        l1['macd'] > l1['macd_signal'] and
        l1['stoch'] < 78 and
        vol_ok):

        reason = "\n".join([
            f"✅ Trend UP ทั้ง 1m & 3m",
            f"✅ RSI: {l1['rsi']:.1f} (40-72)",
            f"✅ MACD: Bullish",
            f"✅ Stoch: {l1['stoch']:.1f} < 78",
            f"✅ Volume: {l1['v']:.0f} > MA20 {l1['vol_ma20']:.0f}"
        ])
        return "UP 🟢", price, reason

    # === DOWN ===
    elif (trend_down and
          28 < l1['rsi'] < 58 and
          l1['macd'] < l1['macd_signal'] and
          l1['stoch'] > 22 and
          vol_ok):

        reason = "\n".join([
            f"✅ Trend DOWN ทั้ง 1m & 3m",
            f"✅ RSI: {l1['rsi']:.1f} (28-58)",
            f"✅ MACD: Bearish",
            f"✅ Stoch: {l1['stoch']:.1f} > 22",
            f"✅ Volume: {l1['v']:.0f} > MA20 {l1['vol_ma20']:.0f}"
        ])
        return "DOWN 🔴", price, reason

    # บอกว่าติดเงื่อนไขอะไร (ช่วย debug)
    miss = []
    if not vol_ok:       miss.append(f"Volume ต่ำ ({l1['v']:.0f} < MA {l1['vol_ma20']:.0f})")
    if not trend_up and not trend_down: miss.append("Trend 1m/3m ไม่สอดคล้องกัน")
    if not (40 < l1['rsi'] < 72) and not (28 < l1['rsi'] < 58):
        miss.append(f"RSI อยู่นอก zone ({l1['rsi']:.1f})")

    return "NEUTRAL ⚪", price, "ไม่ผ่าน: " + ", ".join(miss) if miss else "เงื่อนไขไม่ครบ"

def send_telegram_message(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={'chat_id': TELEGRAM_CHAT_ID, 'text': text},
            timeout=10
        )
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")

def main():
    global last_signal
    send_telegram_message("✅ Bot v3 (Volume + Relaxed Threshold) เริ่มงานแล้ว! 🚀")

    while True:
        now = datetime.now()
        if now.minute % 5 == 0 and 40 <= now.second <= 42:
            try:
                df1 = get_binance_data("1m", limit=100)
                df3 = get_binance_data("3m", limit=100)

                if not df1.empty and not df3.empty:
                    signal, price, reason = get_signal(df1, df3)

                    if signal != last_signal or "UP" in signal or "DOWN" in signal:
                        msg = (
                            f"🔮 BNB/USDT — 5min Prediction\n"
                            f"📍 สัญญาณ: {signal}\n"
                            f"💰 ราคา: ${price:.4f}\n"
                            f"📊 เหตุผล:\n{reason}\n"
                            f"⏳ เวลา: {now.strftime('%H:%M:%S')}"
                        )
                        send_telegram_message(msg)
                        last_signal = signal

                time.sleep(70)
            except Exception as e:
                print(f"[ERROR] main loop: {e}")
                time.sleep(5)
        else:
            time.sleep(1)

if __name__ == "__main__":
    main()
