from sqlalchemy.orm import Session
from . import models, schemas
from app.models import Signal, OHLC
from app.database import get_db
import logging
from datetime import datetime, timedelta
from typing import List
import yfinance as yf
import random
from .signal_generator_be import generate_signals
import pandas as pd
from .data_fetcher import fetch_ohlc_data

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user: schemas.UserCreate):
    db_user = models.User.create(
        username=user.username,
        email=user.email,
        password=user.password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_signals() -> List[Signal]:
    symbols = ['GBP/USD', 'EUR/USD', 'AUD/USD', 'NZD/USD', 'USD/CAD', 'EUR/JPY', 'USD/JPY']
    all_signals = []
    for symbol in symbols:
        try:
            logging.info(f"Fetching data for {symbol}")
            ohlc_data = fetch_ohlc_data(symbol)
            if not ohlc_data:
                logging.warning(f"No data available for {symbol}, skipping signal generation")
                continue
            
            logging.info(f"Processing data for {symbol}")
            df = pd.DataFrame([vars(ohlc) for ohlc in ohlc_data])
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
            df.index.name = symbol  # Set the index name to the symbol for ATR calculation
            
            logging.info(f"Generating signals for {symbol}")
            signals = generate_signals(df)
            
            for signal in signals:
                d_exp_str = f"{'+' if signal['direction'] == 'buy' else '-' if signal['direction'] == 'sell' else ''}{abs(signal['d_exp']):.0f}.{signal['bars_ago']}"
                all_signals.append(Signal(
                    symbol=symbol,
                    chart_symbol=symbol.replace('/', ''),
                    signal_time=signal['time'],
                    entry=signal['entry'],
                    stop_loss=signal['stop_loss'],
                    take_profit=signal['take_profit'],
                    d_exp=d_exp_str
                ))
            logging.info(f"Generated {len(signals)} signals for {symbol}")
        except Exception as e:
            logging.error(f"Error generating signals for {symbol}: {str(e)}")
    
    logging.info(f"Total signals generated: {len(all_signals)}")
    return all_signals