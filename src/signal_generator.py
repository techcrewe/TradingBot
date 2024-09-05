import yfinance as yf
import pandas as pd
import numpy as np
import json

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.float64):
            return float(obj)
        return super(NumpyEncoder, self).default(obj)

def get_data(symbol, period="1mo", interval="1d"):
    if '/' in symbol:  # Forex pair
        base, quote = symbol.split('/')
        symbol = f"{base}{quote}=X"
    
    data = yf.Ticker(symbol)
    df = data.history(period=period, interval=interval)
    return df

def calculate_rsi(data, periods=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(data, fast=12, slow=26, signal=9):
    exp1 = data.ewm(span=fast, adjust=False).mean()
    exp2 = data.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return pd.DataFrame({'MACD': macd, 'Signal': signal_line, 'Histogram': histogram})

def calculate_atr(high, low, close, period=14):
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def calculate_indicators(df, upper_period=5, rsi_period=14):
    # Custom upper band (5-period MA of High)
    df['upper'] = df['High'].rolling(window=upper_period).mean()
    
    # Custom lower band (using Low price)
    df['lower'] = df['Low']
    
    # Middle band (for reference)
    df['middle'] = (df['upper'] + df['lower']) / 2
    
    # Band width and percent
    df['band_width'] = (df['upper'] - df['lower']) / df['middle']
    df['band_percent'] = (df['Close'] - df['lower']) / (df['upper'] - df['lower'])

    # RSI
    df['rsi'] = calculate_rsi(df['Close'], periods=rsi_period)

    # MACD
    macd_data = calculate_macd(df['Close'])
    df = pd.concat([df, macd_data], axis=1)

    # ATR
    df['atr'] = calculate_atr(df['High'], df['Low'], df['Close'])

    return df

def generate_signal(symbol):
    df = get_data(symbol)
    df = calculate_indicators(df)
    
    # Generate signals
    df['Signal'] = 0  # Initialize signal column
    
    # Custom band strategy
    df.loc[df['Close'] < df['lower'], 'Signal'] = 1  # Buy signal
    df.loc[df['Close'] > df['upper'], 'Signal'] = -1  # Sell signal
    
    # Additional conditions
    df.loc[(df['band_percent'] < 0.2) & (df['rsi'] < 30), 'Signal'] = 1  # Strong buy
    df.loc[(df['band_percent'] > 0.8) & (df['rsi'] > 70), 'Signal'] = -1  # Strong sell
    
    # Get the latest signal
    latest_signal = df['Signal'].iloc[-1]
    
    signal_type = 'HOLD'
    if latest_signal == 1:
        signal_type = 'BUY'
    elif latest_signal == -1:
        signal_type = 'SELL'

    # Calculate entry, stop, and target levels
    latest_price = df['Close'].iloc[-1]
    atr = df['atr'].iloc[-1]
    
    entry_level = float(latest_price)
    stop_level = float(entry_level - (2 * atr)) if signal_type == 'BUY' else float(entry_level + (2 * atr))
    target_level = float(entry_level + (3 * atr)) if signal_type == 'BUY' else float(entry_level - (3 * atr))

    # Create a list of all historical signals with their levels
    historical_signals = []
    for i in range(len(df)):
        if df['Signal'].iloc[i] != 0:
            stop = float(df['Close'].iloc[i] - (2 * df['atr'].iloc[i])) if df['Signal'].iloc[i] == 1 else float(df['Close'].iloc[i] + (2 * df['atr'].iloc[i]))
            target = float(df['Close'].iloc[i] + (3 * df['atr'].iloc[i])) if df['Signal'].iloc[i] == 1 else float(df['Close'].iloc[i] - (3 * df['atr'].iloc[i]))
            
            # Check for nan values and replace with None
            stop = None if np.isnan(stop) else stop
            target = None if np.isnan(target) else target
            
            signal = {
                'time': df.index[i].timestamp(),
                'price': float(df['Close'].iloc[i]),
                'type': 'BUY' if df['Signal'].iloc[i] == 1 else 'SELL',
                'stop': stop,
                'target': target
            }
            historical_signals.append(signal)

    # Return the signal and the indicators used
    return json.loads(json.dumps({
        'symbol': symbol,
        'signal': signal_type,
        'entry': entry_level,
        'stop': stop_level,
        'target': target_level,
        'historical_signals': historical_signals,
        'indicators': [
            {"id": "Moving Average", "inputs": {"length": 5, "source": "high"}},
            {"id": "Moving Average", "inputs": {"length": 5, "source": "low"}},
            {"id": "RSI@tv-basicstudies", "inputs": {"length": 14}},
            {"id": "MACD@tv-basicstudies", "inputs": {"fastLength": 12, "slowLength": 26, "signalSmoothing": 9}}
        ]
    }, cls=NumpyEncoder))

def get_performance_stats(symbol):
    df = get_data(symbol, period="6mo")
    df = calculate_indicators(df)
    
    # Generate signals (same logic as in generate_signal)
    df['Signal'] = 0
    df.loc[df['Close'] < df['lower'], 'Signal'] = 1
    df.loc[df['Close'] > df['upper'], 'Signal'] = -1
    df.loc[(df['band_percent'] < 0.2) & (df['rsi'] < 30), 'Signal'] = 1
    df.loc[(df['band_percent'] > 0.8) & (df['rsi'] > 70), 'Signal'] = -1
    
    # Calculate daily returns
    df['Returns'] = df['Close'].pct_change()
    
    # Calculate strategy returns
    df['Strategy_Returns'] = df['Signal'].shift(1) * df['Returns']
    
    # Calculate performance metrics
    total_signals = df['Signal'].abs().sum()
    success_rate = (df['Strategy_Returns'] > 0).mean()
    profit_loss = (df['Strategy_Returns'] + 1).prod() - 1
    
    return {
        'symbol': symbol,
        'success_rate': float(success_rate),
        'profit_loss': float(profit_loss * 100),  # Convert to percentage
        'total_signals': int(total_signals)
    }