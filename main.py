import time
import requests
import pandas as pd
import ta
from datetime import datetime
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

# PancakeSwap Prediction Contract (BSC)
PREDICTION_CONTRACT = "0x18B2A687610328590Bc8F2e5fEdDe3b582A49cdA"
BSC_RPC = "https://bsc-dataseed.binance.org/"

def get_round_end_timestamp():
    """ดึง lockTimestamp ของรอบปัจจุบันจาก contract โดยตรง"""
    try:
        # เรียก currentEpoch()
        payload_epoch = {
            "jsonrpc": "2.0", "method": "eth_call",
            "params": [{
                "to": PREDICTION_CONTRACT,
                # currentEpoch() selector = 0x96bc7bfe
                "data": "0x96bc7bfe"
            }, "latest"],
            "id": 1
        }
        r = requests.post(BSC_RPC, json=payload_epoch, timeout=5)
        epoch_hex = r.json()["result"]
        current_epoch = int(epoch_hex, 16)

        # เรียก rounds(epoch) → struct มี lockTimestamp ที่ index 2
        # rounds(uint256) selector = 0x4f48024d
        epoch_padded = hex(current_epoch)[2:].zfill(64)
        payload_round = {
            "jsonrpc": "2.0", "method": "eth_call",
            "params": [{
                "to": PREDICTION_CONTRACT,
                "data": "0x4f48024d" + epoch_padded
            }, "latest"],
            "id": 2
        }
        r2 = requests.post(BSC_RPC, json=payload_round, timeout=5)
        result = r2.json()["result"]

        # struct Round: epoch(0), startTimestamp(1), lockTimestamp(2), closeTimestamp(3)...
        # แต่ละ slot = 32 bytes = 64 hex chars
        # lockTimestamp อยู่ที่ slot index 2 (bytes 128-192)
        lock_ts  = int(result[2 + 64*2 : 2 + 64*3], 16)
        close_ts = int(result[2 + 64*3 : 2 + 64*4], 16)

        return lock_ts, close_ts, current_epoch

    except Exception as e:
        print(f"[ERROR] get_round_end_timestamp: {e}")
        return None, None, None

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
        print(f"[ERROR] get_binance_data: {e}")
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
        miss.append(f"Volume ต่ำ ({l1['v']:.1f} < 60%MA {l1['vol_ma20']*0.6:.1f})")
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
    send_telegram_message("✅ Bot v8 (Real Contract Time) เริ่มงานแล้ว! 🚀")

    last_alerted_epoch = -1

    while True:
        now = datetime.now()
        now_ts = int(now.timestamp())

        lock_ts, close_ts, epoch = get_round_end_timestamp()

        if lock_ts and close_ts and epoch:
            secs_to_lock = lock_ts - now_ts
            print(f"[LOOP] {now.strftime('%H:%M:%S')} | epoch={epoch} | lock ใน {secs_to_lock}s")

            # ✅ ส่งเมื่อเหลือ 25-40 วินาทีก่อน lock (กันพลาด)
            if 25 <= secs_to_lock <= 40 and epoch != last_alerted_epoch:
                print(f"[SIGNAL!] เหลือ {secs_to_lock}s ก่อน lock")
                df1 = get_binance_data("1m")
                df3 = get_binance_data("3m")

                if not df1.empty and not df3.empty:
                    signal, price, reason = get_signal(df1, df3)
                    lock_time_str = datetime.fromtimestamp(lock_ts).strftime('%H:%M:%S')

                    msg = (
                        f"🔮 PancakeSwap Prediction\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"📍 สัญญาณ: {signal}\n"
                        f"💰 ราคา: ${price:.4f}\n"
                        f"📊 {reason}\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"⚡ Lock ปิดตอน: {lock_time_str}\n"
                        f"⏳ เหลือ: ~{secs_to_lock} วินาที!\n"
                        f"🎯 Epoch: #{epoch+1}"
                    )
                    send_telegram_message(msg)
                    last_alerted_epoch = epoch
                else:
                    send_telegram_message(f"⚠️ ดึงข้อมูลไม่ได้ | epoch #{epoch}")
                    last_alerted_epoch = epoch

        else:
            print(f"[WARN] {now.strftime('%H:%M:%S')} | ดึง contract ไม่ได้")

        time.sleep(3)

if __name__ == "__main__":
    main()
