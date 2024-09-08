import pandas as pd
import numpy as np
from typing import List, Dict
from datetime import datetime

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def generate_signals(df: pd.DataFrame) -> List[Dict]:
    # Calculate indicators
    df['SMA_20'] = df['close'].rolling(window=20).mean()
    df['SMA_50'] = df['close'].rolling(window=50).mean()
    df['ATR'] = calculate_atr(df['high'], df['low'], df['close'])

    signals = []
    for i in range(1, len(df)):
        if df['SMA_20'].iloc[i] > df['SMA_50'].iloc[i] and df['SMA_20'].iloc[i-1] <= df['SMA_50'].iloc[i-1]:
            entry = df['close'].iloc[i]
            stop_loss = entry - 2 * df['ATR'].iloc[i]
            take_profit = entry + 3 * df['ATR'].iloc[i]
            d_exp = (entry - stop_loss) / (0.0001 if 'JPY' not in df.index.name else 0.01)
            
            signals.append({
                'time': df.index[i],
                'direction': 'buy',
                'entry': entry,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'd_exp': d_exp,
                'bars_ago': 0
            })
        elif df['SMA_20'].iloc[i] < df['SMA_50'].iloc[i] and df['SMA_20'].iloc[i-1] >= df['SMA_50'].iloc[i-1]:
            entry = df['close'].iloc[i]
            stop_loss = entry + 2 * df['ATR'].iloc[i]
            take_profit = entry - 3 * df['ATR'].iloc[i]
            d_exp = (stop_loss - entry) / (0.0001 if 'JPY' not in df.index.name else 0.01)
            
            signals.append({
                'time': df.index[i],
                'direction': 'sell',
                'entry': entry,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'd_exp': d_exp,
                'bars_ago': 0
            })

    # Only keep the most recent signal within the last 3 bars
    if signals:
        latest_signal = signals[-1]
        latest_signal['bars_ago'] = len(df) - 1 - df.index.get_loc(latest_signal['time'])
        if latest_signal['bars_ago'] <= 3:
            return [latest_signal]
    
    # If no signal within the last 3 bars, return a signal with d_exp = 0
    return [{
        'time': df.index[-1],
        'direction': 'none',
        'entry': df['close'].iloc[-1],
        'stop_loss': df['close'].iloc[-1],
        'take_profit': df['close'].iloc[-1],
        'd_exp': 0,
        'bars_ago': 0
    }]