import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import logging
from typing import List
from app.models import OHLC
import time
from oandapyV20 import API
from oandapyV20.endpoints.instruments import InstrumentsCandles
import configparser
import os

# Read Oanda configuration
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), '..', 'oanda.cfg')
config.read(config_path)

oanda_access_token = config['oanda']['access_token']
oanda_account_id = config['oanda']['account_id']

oanda_api = API(access_token=oanda_access_token, environment="practice")

def fetch_ohlc_data_oanda(symbol: str, days: int = 180) -> List[OHLC]:
    try:
        logging.info(f"Fetching OHLC data from Oanda for symbol: {symbol}")
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Convert symbol to Oanda format
        oanda_symbol = symbol.replace('/', '_')
        
        params = {
            "from": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "granularity": "D"
        }
        
        request = InstrumentsCandles(instrument=oanda_symbol, params=params)
        response = oanda_api.request(request)
        
        candles = response['candles']
        
        ohlc_data = []
        for candle in candles:
            if candle['complete']:
                ohlc_data.append(OHLC(
                    time=candle['time'][:10],
                    open=float(candle['mid']['o']),
                    high=float(candle['mid']['h']),
                    low=float(candle['mid']['l']),
                    close=float(candle['mid']['c'])
                ))
        
        logging.info(f"Received {len(ohlc_data)} data points for {symbol} from Oanda")
        return ohlc_data
    except Exception as e:
        logging.error(f"Error fetching OHLC data from Oanda for {symbol}: {str(e)}", exc_info=True)
        return []

# Keep the existing yfinance function for backup or comparison
def fetch_ohlc_data_yfinance(symbol: str, max_retries: int = 3) -> List[OHLC]:
    for attempt in range(max_retries):
        try:
            logging.info(f"Fetching OHLC data for symbol: {symbol} (Attempt {attempt + 1})")
            end_date = datetime.now()
            start_date = end_date - timedelta(days=180)  # 6 months of data
            yf_symbol = symbol.replace('/', '') + '=X'
            ticker = yf.Ticker(yf_symbol)
            
            # Remove the 'retries' argument
            df = ticker.history(start=start_date, end=end_date, interval="1d", timeout=60)
            
            logging.info(f"Received {len(df)} data points for {symbol}")
            
            if df.empty:
                logging.warning(f"No data received for {symbol}")
                return []
            
            return [
                OHLC(
                    time=index.strftime('%Y-%m-%d'),
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close'])
                ) for index, row in df.iterrows()
            ]
        except Exception as e:
            logging.error(f"Error fetching OHLC data for {symbol} (Attempt {attempt + 1}): {str(e)}", exc_info=True)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                return []

# Main function to fetch data, prioritizing Oanda
def fetch_ohlc_data(symbol: str) -> List[OHLC]:
    oanda_data = fetch_ohlc_data_oanda(symbol)
    if oanda_data:
        return oanda_data
    logging.warning(f"Failed to fetch data from Oanda for {symbol}. Falling back to yfinance.")
    return fetch_ohlc_data_yfinance(symbol)