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

    price  = l1['close']
    vol_ok = l1['v'] > l1['vol_ma20']
    trend_up   = l1['close'] > l1['ema_50'] and l3['close'] > l3['ema_50']
    trend_down = l1['close'] < l1['ema_50'] and l3['close'] < l3['ema_50']

    if (trend_up and 40 < l1['rsi'] < 72 and
        l1['macd'] > l1['macd_signal'] and l1['stoch'] < 78 and vol_ok):
        reason = "\n".join([
            f"✅ Trend UP (1m & 3m)",
            f"✅ RSI: {l1['rsi']:.1f}",
            f"✅ MACD: Bullish",
            f"✅ Stoch: {l1['stoch']:.1f}",
            f"✅ Volume: {l1['v']:.0f} > MA {l1['vol_ma20']:.0f}"
        ])
        return "UP 🟢", price, reason

    elif (trend_down and 28 < l1['rsi'] < 58 and
          l1['macd'] < l1['macd_signal'] and l1['stoch'] > 22 and vol_ok):
        reason = "\n".join([
            f"✅ Trend DOWN (1m & 3m)",
            f"✅ RSI: {l1['rsi']:.1f}",
            f"✅ MACD: Bearish",
            f"✅ Stoch: {l1['stoch']:.1f}",
            f"✅ Volume: {l1['v']:.0f} > MA {l1['vol_ma20']:.0f}"
        ])
        return "DOWN 🔴", price, reason

    # NEUTRAL — บอกเหตุผลละเอียด
    miss = []
    if not vol_ok:
        miss.append(f"Volume ต่ำ ({l1['v']:.0f} < MA {l1['vol_ma20']:.0f})")
    if not trend_up and not trend_down:
        miss.append(f"Trend ขัดแย้ง (1m vs 3m)")
    if l1['macd'] == l1['macd_signal']:
        miss.append("MACD ไม่ชัด")
    miss.append(f"RSI: {l1['rsi']:.1f} | Stoch: {l1['stoch']:.1f}")

    return "NEUTRAL ⚪", price, "⏸ รอสัญญาณ:\n" + "\n".join(miss)

def send_telegram_message(text):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={'chat_id': TELEGRAM_CHAT_ID, 'text': text},
            timeout=10
        )
        print(f"[TG] {r.status_code} | {text[:50]}")
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")

def main():
    send_telegram_message("✅ Bot v4 เริ่มงานแล้ว — ส่งสัญญาณทุก 5 นาที 🚀")

    while True:
        now = datetime.now()
        print(f"[LOOP] {now.strftime('%H:%M:%S')} — กำลังดึงข้อมูล...")

        try:
            df1 = get_binance_data("1m", limit=100)
            df3 = get_binance_data("3m", limit=100)

            if not df1.empty and not df3.empty:
                signal, price, reason = get_signal(df1, df3)

                msg = (
                    f"🔮 BNB/USDT — 5min Prediction\n"
                    f"📍 สัญญาณ: {signal}\n"
                    f"💰 ราคา: ${price:.4f}\n"
                    f"📊 {reason}\n"
                    f"⏳ เวลา: {now.strftime('%H:%M:%S')}"
                )
                send_telegram_message(msg)
            else:
                send_telegram_message(f"⚠️ ดึงข้อมูลไม่ได้ [{now.strftime('%H:%M:%S')}]")

        except Exception as e:
            print(f"[ERROR] main loop: {e}")
            send_telegram_message(f"❌ Error: {e}")

        # ✅ รอ 5 นาทีตรงๆ ไม่ต้องเช็คเวลาเลย
        print("[LOOP] รอ 5 นาที...")
        time.sleep(300)

if __name__ == "__main__":
    main()
