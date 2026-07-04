import time
import requests
import pandas as pd
import ta
from datetime import datetime
import os
from web3 import Web3

# ---------------------------------------------------------
# 🛡️ ระบบดักจับเวอร์ชัน Web3 เพื่อแปลภาษา Binance Smart Chain (แก้ Error อ่านข้อมูลไม่ออก)
# ---------------------------------------------------------
try:
    # สำหรับ Web3 เวอร์ชันใหม่ (v7+)
    from web3.middleware import ExtraDataToPOAMiddleware as geth_poa_middleware
except ImportError:
    try:
        # สำหรับ Web3 เวอร์ชันเก่า (v6 ลงไป)
        from web3.middleware import geth_poa_middleware
    except ImportError:
        geth_poa_middleware = None

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# คัดเฉพาะ RPC ที่ไม่บล็อกเซิร์ฟเวอร์คลาวด์ 100%
RPC_LIST = [
    "https://bsc.publicnode.com",
    "https://bsc-dataseed1.defibit.io",
    "https://bsc-dataseed1.ninicoin.io",
    "https://bsc-dataseed.binance.org/"
]
current_rpc_index = 0

CONTRACT_ADDRESS = "0x18B2A6826674A0A57CB7fA9Fdeb9E955353cE530"
ABI = '[{"inputs":[],"name":"currentEpoch","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"","type":"uint256"}],"name":"epochs","outputs":[{"internalType":"uint256","name":"epoch"},{"internalType":"uint256","name":"startTimestamp"},{"internalType":"uint256","name":"lockTimestamp"},{"internalType":"uint256","name":"closeTimestamp"},{"internalType":"int256","name":"lockPrice"},{"internalType":"int256","name":"closePrice"},{"internalType":"uint256","name":"lockOracleId"},{"internalType":"uint256","name":"closeOracleId"},{"internalType":"uint256","name":"totalAmount"},{"internalType":"uint256","name":"bullAmount"},{"internalType":"uint256","name":"bearAmount"},{"internalType":"uint256","name":"rewardBaseCalAmount"},{"internalType":"uint256","name":"rewardAmount"},{"internalType":"bool","name":"oracleCalled"}],"stateMutability":"view","type":"function"}]'

def get_contract(rpc_url):
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    # ฉีดตัวแปลภาษาเข้าไปให้บอทอ่าน BSC รู้เรื่อง
    if geth_poa_middleware:
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    contract = w3.eth.contract(address=w3.to_checksum_address(CONTRACT_ADDRESS), abi=ABI)
    return w3, contract

w3, contract = get_contract(RPC_LIST[current_rpc_index])

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
    global current_rpc_index, w3, contract
    
    startup_msg = "✅ บอท Web3 (สมบูรณ์แบบ 100%) อัปเดตตัวแปลภาษาบล็อกเชนเรียบร้อย เริ่มทำงานแล้ว! 🚀"
    send_telegram_message(startup_msg)
    print(f"Bot started. Connected to {RPC_LIST[current_rpc_index]}")
    
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
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Sent Signal for Epoch #{current_epoch}")
                    
                    last_signaled_epoch = current_epoch
                    time.sleep(60)
                    continue
                    
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {e}")
            current_rpc_index = (current_rpc_index + 1) % len(RPC_LIST)
            print(f"🔄 กำลังสลับเซิร์ฟเวอร์บล็อกเชนไปที่: {RPC_LIST[current_rpc_index]}")
            
            try:
                w3, contract = get_contract(RPC_LIST[current_rpc_index])
            except:
                pass
            
            time.sleep(2)
            continue
            
        time.sleep(2)

if __name__ == "__main__":
    main()
