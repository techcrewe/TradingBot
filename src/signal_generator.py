import yfinance as yf
import pandas as pd
import numpy as np
import json
from typing import Tuple
from datetime import datetime, timedelta

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.float64):
            return float(obj)
        return super(NumpyEncoder, self).default(obj)

def get_data(symbol, period="6mo", interval="1d"):
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

def generate_signals_for_multiple_symbols():
    symbols = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF', 'AUD/USD', 'USD/CAD', 'NZD/USD']
    all_signals = {}

    for symbol in symbols:
        signal_data = generate_signal(symbol)
        all_signals[symbol] = signal_data

    return all_signals

def generate_signal(symbol):
    df = get_data(symbol)
    signal_generator = SignalGenerator(dir_filter_type="None")
    df = signal_generator.generate_signals(df)
    
    # Get the latest signal
    latest_signal = df['signal'].iloc[-1]
    
    signal_type = 'HOLD'
    if latest_signal == 1:
        signal_type = 'BUY'
    elif latest_signal == -1:
        signal_type = 'SELL'

    # Find the most recent non-zero signal
    last_signal_index = df[df['signal'] != 0].index[-1] if any(df['signal'] != 0) else None
    
    current_signal = None
    bars_ago = 0
    if last_signal_index:
        bars_ago = len(df) - df.index.get_loc(last_signal_index) - 1
        current_signal = {
            'time': last_signal_index.strftime('%Y-%m-%d %H:%M:%S'),
            'price': float(df.loc[last_signal_index, 'Close']),
            'type': 'BUY' if df.loc[last_signal_index, 'signal'] == 1 else 'SELL',
            'stop': float(df.loc[last_signal_index, 'stop_loss']),
            'target1': float(df.loc[last_signal_index, 'take_profit1']),
            'target2': float(df.loc[last_signal_index, 'take_profit2']),
            'target3': float(df.loc[last_signal_index, 'take_profit3']),
            'bars_ago': bars_ago
        }

    # Get the latest levels
    entry_level = float(df['entry'].iloc[-1]) if not np.isnan(df['entry'].iloc[-1]) else None
    stop_level = float(df['stop_loss'].iloc[-1]) if not np.isnan(df['stop_loss'].iloc[-1]) else None
    target_level1 = float(df['take_profit1'].iloc[-1]) if not np.isnan(df['take_profit1'].iloc[-1]) else None
    target_level2 = float(df['take_profit2'].iloc[-1]) if not np.isnan(df['take_profit2'].iloc[-1]) else None
    target_level3 = float(df['take_profit3'].iloc[-1]) if not np.isnan(df['take_profit3'].iloc[-1]) else None

    # Custom JSON encoder to handle NaN values
    class CustomEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, float) and np.isnan(obj):
                return None
            return super().default(obj)

    # Return the signal and the indicators used
    return json.loads(json.dumps({
        'symbol': symbol,
        'signal': signal_type,
        'entry': entry_level,
        'stop': stop_level,
        'target1': target_level1,
        'target2': target_level2,
        'target3': target_level3,
        'current_signal': current_signal,
        'bars_ago': bars_ago
    }, cls=CustomEncoder))

def get_performance_stats(symbol):
    df = get_data(symbol, period="6mo")
    df = calculate_indicators(df)
    
    # Generate signals (same logic as in generate_signal)
    df['Signal'] = 0
    df.loc[df['Close'] < df['lower'], 'Signal'] = 1
    df.loc[df['Close'] > df['upper'], 'Signal'] = -1
    
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

class SignalGenerator:
    def __init__(self, strategy: str = "Expansion", atr_multiplier: float = 1.5,
                 fast_ma: int = 5, med_ma: int = 8, slow_ma: int = 21,
                 band_length: int = 5, filter_ma: int = 50, dir_filter_type: str = "Price Struct",
                 tgt1: float = 1.0, tgt2: float = 1.5, tgt3: float = 2.0):
        self.strategy = strategy
        self.atr_multiplier = atr_multiplier
        self.fast_ma = fast_ma
        self.med_ma = med_ma
        self.slow_ma = slow_ma
        self.band_length = band_length
        self.filter_ma = filter_ma
        self.dir_filter_type = dir_filter_type
        self.tgt1 = tgt1
        self.tgt2 = tgt2
        self.tgt3 = tgt3

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        # Calculate indicators
        df = self._calculate_indicators(df)
        
        # Generate signals based on strategy
        if self.strategy == "Expansion":
            df = self._expansion_strategy(df)
        elif self.strategy == "Band Play":
            df = self._band_play_strategy(df)
        
        # Apply direction filter
        df = self._apply_direction_filter(df)
        
        # Calculate entry, stop loss, and take profit levels
        df = self._calculate_trade_levels(df)
        
        print("Generated signals:")
        print(df[['Close', 'signal', 'entry', 'stop_loss', 'take_profit1', 'take_profit2', 'take_profit3']].tail())
        
        return df

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df['fast_ma'] = df['Close'].rolling(window=self.fast_ma).mean()
        df['med_ma'] = df['Close'].rolling(window=self.med_ma).mean()
        df['slow_ma'] = df['Close'].rolling(window=self.slow_ma).mean()
        df['filter_ma'] = df['Close'].rolling(window=self.filter_ma).mean()
        df['band_high'] = df['High'].rolling(window=self.band_length).mean()
        df['band_low'] = df['Low'].rolling(window=self.band_length).mean()
        df['atr'] = self._calculate_atr(df)
        return df

    def _expansion_strategy(self, df: pd.DataFrame) -> pd.DataFrame:
        df['signal'] = 0
        long_condition = (
            (df['Close'] > df['band_high']) &
            (df['Close'] > df['slow_ma']) &
            (df['fast_ma'] > df['med_ma']) &
            (df['fast_ma'] > df['fast_ma'].shift(1))
        )
        short_condition = (
            (df['Close'] < df['band_low']) &
            (df['Close'] < df['slow_ma']) &
            (df['fast_ma'] < df['med_ma']) &
            (df['fast_ma'] < df['fast_ma'].shift(1))
        )
        print(f"Long conditions met: {long_condition.sum()}")
        print(f"Short conditions met: {short_condition.sum()}")
        df.loc[long_condition, 'signal'] = 1
        df.loc[short_condition, 'signal'] = -1
        return df

    def _band_play_strategy(self, df: pd.DataFrame) -> pd.DataFrame:
        df['signal'] = 0
        df['sma_cross'] = np.where(df['med_ma'] > df['slow_ma'], 1, -1)
        df['sma_cross_change'] = df['sma_cross'].diff()
        
        long_setup = (df['sma_cross_change'] == 2) & (df['Close'] > df['band_high'])
        short_setup = (df['sma_cross_change'] == -2) & (df['Close'] < df['band_low'])
        
        df.loc[long_setup & (df['Low'] <= df['med_ma']), 'signal'] = 1
        df.loc[short_setup & (df['High'] >= df['med_ma']), 'signal'] = -1
        return df

    def _apply_direction_filter(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.dir_filter_type == "Price Struct":
            # Simplified price structure filter
            df['higher_high'] = df['High'] > df['High'].shift(1)
            df['higher_low'] = df['Low'] > df['Low'].shift(1)
            df.loc[(df['signal'] == 1) & (~df['higher_high'] | ~df['higher_low']), 'signal'] = 0
            df.loc[(df['signal'] == -1) & (df['higher_high'] | df['higher_low']), 'signal'] = 0
        elif self.dir_filter_type == "SMA Slope":
            df['sma_slope'] = df['filter_ma'].diff()
            df.loc[(df['signal'] == 1) & (df['sma_slope'] <= 0), 'signal'] = 0
            df.loc[(df['signal'] == -1) & (df['sma_slope'] >= 0), 'signal'] = 0
        elif self.dir_filter_type == "SMA Posn":
            df.loc[(df['signal'] == 1) & (df['Close'] <= df['filter_ma']), 'signal'] = 0
            df.loc[(df['signal'] == -1) & (df['Close'] >= df['filter_ma']), 'signal'] = 0
        return df

    def _calculate_trade_levels(self, df: pd.DataFrame) -> pd.DataFrame:
        df['entry'] = df['Close']
        df['stop_loss'] = np.where(
            df['signal'] == 1,
            df['Close'] - df['atr'] * self.atr_multiplier,
            np.where(df['signal'] == -1,
                     df['Close'] + df['atr'] * self.atr_multiplier,
                     np.nan)
        )
        risk = abs(df['entry'] - df['stop_loss'])
        df['take_profit1'] = np.where(
            df['signal'] == 1,
            df['entry'] + risk * self.tgt1,
            np.where(df['signal'] == -1,
                     df['entry'] - risk * self.tgt1,
                     np.nan)
        )
        df['take_profit2'] = np.where(
            df['signal'] == 1,
            df['entry'] + risk * self.tgt2,
            np.where(df['signal'] == -1,
                     df['entry'] - risk * self.tgt2,
                     np.nan)
        )
        df['take_profit3'] = np.where(
            df['signal'] == 1,
            df['entry'] + risk * self.tgt3,
            np.where(df['signal'] == -1,
                     df['entry'] - risk * self.tgt3,
                     np.nan)
        )
        return df

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(window=period).mean()