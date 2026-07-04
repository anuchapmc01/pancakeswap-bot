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
    vol_ok = l1['v'] > l1['vol_ma20'] * 0.6
    trend_up   = l1['close'] > l1['ema_50'] and l3['close'] > l3['ema_50']
    trend_down = l1['close'] < l1['ema_50'] and l3['close'] < l3['ema_50']

    if (trend_up and 38 < l1['rsi'] < 75 and
        l1['macd'] > l1['macd_signal'] and l1['stoch'] < 85 and vol_ok):
        reason = "\n".join([
            f"✅ Trend UP (1m & 3m)",
            f"✅ RSI: {l1['rsi']:.1f}",
            f"✅ MACD: Bullish",
            f"✅ Stoch: {l1['stoch']:.1f}",
            f"✅ Vol: {l1['v']:.1f} > 60%MA ({l1['vol_ma20']*0.6:.1f})"
        ])
        return "UP 🟢", price, reason

    elif (trend_down and 25 < l1['rsi'] < 60 and
          l1['macd'] < l1['macd_signal'] and l1['stoch'] > 15 and vol_ok):
        reason = "\n".join([
            f"✅ Trend DOWN (1m & 3m)",
            f"✅ RSI: {l1['rsi']:.1f}",
            f"✅ MACD: Bearish",
            f"✅ Stoch: {l1['stoch']:.1f}",
            f"✅ Vol: {l1['v']:.1f} > 60%MA ({l1['vol_ma20']*0.6:.1f})"
        ])
        return "DOWN 🔴", price, reason

    miss = []
    if not vol_ok:
        miss.append(f"Volume ต ({l1['v']:.1f} < 60%MA {l1['vol_ma20']*0.6:.1f})")
    if not trend_up and not trend_down:
        miss.append("Trend 1m/3m ขัดแย้ง")
    miss.append(f"RSI: {l1['rsi']:.1f} | Stoch: {l1['stoch']:.1f}")
    return "NEUTRAL ⚪", price, "⏸ รอสัญญาณ:\n" + "\n".join(miss)

def send_telegram_message(text):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={'chat_id': TELEGRAM_CHAT_ID, 'text': text},
            timeout=10
        )
        print(f"[TG] {r.status_code} | {text[:60]}")
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")

def main():
    send_telegram_message(
        "✅ Bot v6 เริ่มงานแล้ว!\n"
        "⏰ ส่งสัญญาณ 30 วินาทีก่อนปิดรอบ PancakeSwap 🚀"
    )
    sent_this_round = False

    while True:
        now = datetime.now()
        minute_in_round = now.minute % 5  # 0,1,2,3,4
        sec = now.second

        # ✅ ส่งตอนนาทีที่ 4 วินาที 28-32
        # = 30 วินาทีก่อนรอบปิด (นาทีที่ 5 วินาทีที่ 0 รอบ reset)
        is_signal_window = (minute_in_round == 4 and 28 <= sec <= 32)

        # reset flag เมื่อขึ้นรอบใหม่
        if minute_in_round == 0 and sec < 10:
            sent_this_round = False

        if is_signal_window and not sent_this_round:
            print(f"[SIGNAL WINDOW] {now.strftime('%H:%M:%S')} — กำลังวิเคราะห์...")
            try:
                df1 = get_binance_data("1m", limit=100)
                df3 = get_binance_data("3m", limit=100)

                if not df1.empty and not df3.empty:
                    signal, price, reason = get_signal(df1, df3)

                    # คำนวณรอบถัดไปที่จะเริ่ม
                    next_round_min = (now.minute // 5 + 1) * 5
                    next_round_str = f"{now.hour:02d}:{next_round_min % 60:02d}:00"

                    msg = (
                        f"🔮 PancakeSwap Prediction\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"📍 สัญญาณ: {signal}\n"
                        f"💰 ราคา: ${price:.4f}\n"
                        f"📊 {reason}\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"⚡ แทงรอบ: {next_round_str}\n"
                        f"⏳ เหลือเวลา: ~30 วินาที!"
                    )
                    send_telegram_message(msg)
                    sent_this_round = True
                else:
                    send_telegram_message(f"⚠️ ดึงข้อมูลไม่ได้ [{now.strftime('%H:%M:%S')}]")
                    sent_this_round = True

            except Exception as e:
                print(f"[ERROR] {e}")
                send_telegram_message(f"❌ Error: {e}")
                sent_this_round = True

        else:
            # log ทุก 10 วิ ให้รู้ว่า loop ยังทำงาน
            if sec % 10 == 0:
                print(f"[WAIT] {now.strftime('%H:%M:%S')} | round_min={minute_in_round} | sent={sent_this_round}")

        time.sleep(1)

if __name__ == "__main__":
    main()
