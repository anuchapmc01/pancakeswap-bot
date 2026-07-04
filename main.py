import time
import requests
import pandas as pd
import ta
from datetime import datetime
import os
from web3 import Web3

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ---------------------------------------------------------
# 🔗 เปลี่ยน RPC เป็นของ Ankr (อนุญาตให้บอทคลาวด์ดึงข้อมูลได้ ไม่โดนบล็อก IP)
# ---------------------------------------------------------
BSC_RPC = "https://rpc.ankr.com/bsc"
w3 = Web3(Web3.HTTPProvider(BSC_RPC))

# ที่อยู่ Contract ของ PancakeSwap Prediction V2 (BNB)
CONTRACT_ADDRESS = w3.to_checksum_address("0x18B2A6826674A0A57CB7fA9Fdeb9E955353cE530")

ABI = '[{"inputs":[],"name":"currentEpoch","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"","type":"uint256"}],"name":"epochs","outputs":[{"internalType":"uint256","name":"epoch"},{"internalType":"uint256","name":"startTimestamp"},{"internalType":"uint256","name":"lockTimestamp"},{"internalType":"uint256","name":"closeTimestamp"},{"internalType":"int256","name":"lockPrice"},{"internalType":"int256","name":"closePrice"},{"internalType":"uint256","name":"lockOracleId"},{"internalType":"uint256","name":"closeOracleId"},{"internalType":"uint256","name":"totalAmount"},{"internalType":"uint256","name":"bullAmount"},{"internalType":"uint256","name":"bearAmount"},{"internalType":"uint256","name":"rewardBaseCalAmount"},{"internalType":"uint256","name":"rewardAmount"},{"internalType":"bool","name":"oracleCalled"}],"stateMutability":"view","type":"function"}]'
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=ABI)

# ตั้งค่าให้เตือนล่วงหน้าก่อนเวลา Lock จริงบนบล็อกเชน 30 วินาที
NOTIFY_BEFORE_SECONDS = 30

def get_binance_data(symbol="BNBUSDT", interval="1m", limit=100):
    url = f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        response = requests.get(url).json()
        if isinstance(response, dict) and 'code' in response:
            return pd.DataFrame()
        df = pd.DataFrame(response, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        df['close'] = pd.to_numeric(df['close'])
        return df
    except:
        return pd.DataFrame()

def analyze_trend(df):
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    df['ema_9'] = ta.trend.EMAIndicator(df['close'], window=9).ema_indicator()
    df['ema_21'] = ta.trend.EMAIndicator(df['close'], window=21).ema_indicator()
    df['ema_50'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
    
    macd = ta.trend.MACD(df['close'])
    df['macd_line'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()

    latest = df.iloc[-1]
    signal = "WAIT"
    
    if (latest['close'] > latest['ema_50'] and 
        latest['ema_9'] > latest['ema_21'] and 
        latest['macd_line'] > latest['macd_signal'] and 
        45 <= latest['rsi'] <= 65):
        signal = "UP 🟢"
    elif (latest['close'] < latest['ema_50'] and 
          latest['ema_9'] < latest['ema_21'] and 
          latest['macd_line'] < latest['macd_signal'] and 
          35 <= latest['rsi'] <= 55):
        signal = "DOWN 🔴"
        
    return signal, latest['close'], latest['rsi']

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': text}
    requests.post(url, data=payload)

def main():
    startup_msg = "✅ บอท PancakeSwap อัปเกรด (Web3 - Ankr) เริ่มทำงานแล้ว!\nจับเวลาแม่นยำ 100% จากบล็อกเชน 🚀"
    send_telegram_message(startup_msg)
    print("Bot started with Web3 tracking (Ankr RPC).")
    
    last_signaled_epoch = 0
    
    while True:
        try:
            current_epoch = contract.functions.currentEpoch().call()
            
            if current_epoch != last_signaled_epoch:
                epoch_data = contract.functions.epochs(current_epoch).call()
                lock_timestamp = epoch_data[2]
                
                current_time = int(time.time())
                time_remaining = lock_timestamp - current_time
                
                if 0 < time_remaining <= NOTIFY_BEFORE_SECONDS:
                    df = get_binance_data()
                    
                    if not df.empty:
                        signal, price, rsi = analyze_trend(df)
                        action_time = max(1, time_remaining - 10) 
                        
                        if signal != "WAIT":
                            msg = (
                                f"🔮 PancakeSwap Prediction (รอบ: #{current_epoch})\n"
                                f"📍 สัญญาณ: {signal}\n"
                                f"💰 ราคา BNB: ${price:.2f}\n"
                                f"📊 RSI (1m): {rsi:.2f}\n"
                                f"⏳ รีบกดภายใน {action_time} วินาที!"
                            )
                        else:
                            msg = (
                                f"⏸ PancakeSwap Prediction (รอบ: #{current_epoch})\n"
                                f"📍 สัญญาณ: ข้ามรอบนี้ (ทรงกราฟไม่ชัวร์)\n"
                                f"💰 ราคาปัจจุบัน: ${price:.2f}\n"
                                f"📊 RSI (1m): {rsi:.2f}"
                            )
                        send_telegram_message(msg)
                        print(f"Sent Signal for Epoch #{current_epoch}")
                    
                    last_signaled_epoch = current_epoch
                    time.sleep(60)
                    continue
                    
        except Exception as e:
            # ถ้ายังมี Error โผล่มาบ้างเป็นบางครั้ง (เช่น เน็ตกระตุก) ให้ข้ามไป ไม่ต้องปริ้นท์รบกวนหน้าจอ
            pass
            
        time.sleep(2)

if __name__ == "__main__":
    main()
