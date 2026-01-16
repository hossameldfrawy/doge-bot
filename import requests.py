import requests
import pandas as pd
import numpy as np
import time
import os
import json
import sys
from datetime import datetime, timedelta
from colorama import Fore, Back, Style, init

init(autoreset=True)

# ---------------- إعدادات البوت ----------------
SYMBOL = 'DOGEUSDT'
INTERVAL = '1m'
INITIAL_BALANCE = 8.0
# -----------------------------------------------

HISTORY_FILE = "trade_history.json"
STATE_FILE = "bot_state.json"

def load_data():
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f: history = json.load(f)
        except: pass
    wallet, active = INITIAL_BALANCE, None
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                wallet = state.get('wallet', INITIAL_BALANCE)
                active = state.get('active_trade')
        except: pass
    return history, wallet, active

def save_all(history, wallet, active):
    with open(HISTORY_FILE, 'w') as f: json.dump(history, f, indent=4)
    with open(STATE_FILE, 'w') as f: json.dump({'wallet': wallet, 'active_trade': active}, f)

trade_journal, wallet, active_trade = load_data()

def get_data(interval='1m', limit=500):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={SYMBOL}&interval={interval}&limit={limit}"
        data = requests.get(url, timeout=5).json()
        df = pd.DataFrame(data, columns=['ts', 'open', 'high', 'low', 'close', 'v', 'ct', 'qa', 'nt', 'tb', 'tq', 'i'])
        for col in ['open', 'high', 'low', 'close']: df[col] = df[col].astype(float)
        return df
    except: return pd.DataFrame()

def get_win_rate(hours):
    now = datetime.now()
    start_time = now - timedelta(hours=hours)
    relevant = []
    for t in trade_journal:
        time_str = t.get('close_time_full') or t.get('time') or now.isoformat()
        try:
            t_time = datetime.fromisoformat(time_str) if 'T' in time_str else datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            if t_time >= start_time: relevant.append(t)
        except: continue
    if not relevant: return "0.0% (0/0)"
    wins = len([t for t in relevant if 'WIN' in t['status']])
    return f"{(wins/len(relevant))*100:.1f}% ({wins}/{len(relevant)})"

def main():
    global active_trade, wallet, trade_journal
    
    while True:
        try:
            df = get_data('1m', 500)
            df_daily = get_data('1d', 5)
            if df.empty or df_daily.empty: time.sleep(5); continue
            
            last_day = df_daily.iloc[-2]
            pivot = (last_day['high'] + last_day['low'] + last_day['close']) / 3
            res1 = (2 * pivot) - last_day['low']
            sup1 = (2 * pivot) - last_day['high']

            close = df['close']
            rsi = 100 - (100 / (1 + (close.diff().where(close.diff() > 0, 0).rolling(14).mean() / -close.diff().where(close.diff() < 0, 0).rolling(14).mean())))
            sma20 = close.rolling(20).mean()
            std20 = close.rolling(20).std()
            lower_bb = sma20 - (std20 * 2)
            atr = (df['high'] - df['low']).rolling(14).mean()
            
            curr_p = close.iloc[-1]
            curr_rsi = rsi.iloc[-1]
            
            if active_trade:
                if curr_p >= active_trade['target']:
                    final_money = active_trade['amount'] * curr_p
                    profit = final_money - active_trade['invested_usd']
                    wallet = final_money
                    active_trade.update({
                        'status': 'WIN 🏆', 
                        'close_price': curr_p,
                        'profit_usd': round(profit, 4),
                        'close_time': datetime.now().strftime("%H:%M"),
                        'close_time_full': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    trade_journal.append(active_trade)
                    active_trade = None
                    save_all(trade_journal, wallet, active_trade)
            
            elif curr_rsi < 31 and curr_p <= lower_bb.iloc[-1]:
                invested = wallet
                amount = invested / curr_p
                target = curr_p + (atr.iloc[-1] * 2.2)
                active_trade = {
                    'entry': curr_p, 'target': target, 'amount': round(amount, 2),
                    'invested_usd': invested, 'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'status': 'ACTIVE ⏳'
                }
                wallet = 0
                save_all(trade_journal, wallet, active_trade)

            # --- الواجهة النهائية المدمجة ---
            os.system('cls' if os.name == 'nt' else 'clear')
            total_profit = sum([float(t.get('profit_usd', 0)) for t in trade_journal])
            
            print(f"{Back.CYAN}{Fore.BLACK} 🦅 V6.8 UNCHAINED PREDATOR (LOCAL SESSION) {Style.RESET_ALL}")
            print(f"🐶 PRICE: {Fore.YELLOW}${curr_p:.6f}{Style.RESET_ALL} | 💰 Wallet: ${wallet if not active_trade else active_trade['invested_usd']:.2f}")
            print(f"💎 Total Profit: {Fore.GREEN}+${round(total_profit, 4)}{Style.RESET_ALL}")
            
            print(f"\n{Fore.WHITE}📅 TODAY'S PREDICTED RANGE")
            print(f"📉 Low: ${sup1:.5f} | 📈 High: ${res1:.5f}")
            
            print(f"\n{Fore.WHITE}📊 PERFORMANCE")
            print(f"1H Win: {get_win_rate(1)} | 24H Win: {get_win_rate(24)}")

            if active_trade:
                pnl_pct = ((curr_p - active_trade['entry']) / active_trade['entry']) * 100
                print(f"\n{Back.GREEN}{Fore.BLACK} ⚡ ACTIVE TRADE RUNNING ⚡ {Style.RESET_ALL}")
                print(f"📥 Entry: ${active_trade['entry']:.5f} | 🎯 Target: ${active_trade['target']:.5f}")
                print(f"💵 In: ${active_trade['invested_usd']:.2f} ({active_trade['amount']} DOGE)")
                print(f"📈 P/L: {Fore.GREEN if pnl_pct > 0 else Fore.RED}{pnl_pct:.2f}%")
            else:
                print(f"\nStatus: {Fore.MAGENTA}Hunting for Opportunity...{Style.RESET_ALL} (RSI: {curr_rsi:.1f})")

            print(f"\n{Fore.WHITE}📜 RECENT TRADES HISTORY:")
            for t in trade_journal[-3:]:
                inv = t.get('invested_usd', 0)
                prof = t.get('profit_usd', 0)
                coins = t.get('amount', 0)
                t_time = t.get('close_time') or "00:00"
                
                print(f"[{t_time}] {Fore.GREEN}WIN 🏆{Fore.RESET} | In: ${inv:.2f} ({coins} DOGE) | Profit: {Fore.GREEN}+${prof}{Fore.RESET}")
                print(f"      ↳ Entry: {t.get('entry',0):.5f} → Exit: {t.get('close_price',0):.5f}")
                print("-" * 50)

            time.sleep(10)
        except Exception as e: print(f"Error: {e}"); time.sleep(5)

if __name__ == "__main__": main()