from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from . import crud, models, schemas
from .database import SessionLocal, engine
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, List
import logging
from urllib.parse import unquote
import json
import pandas as pd
import yfinance as yf
import numpy as np

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

SECRET_KEY = "YOUR_SECRET_KEY"  # Replace with a secure secret key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@app.post("/register", response_model=schemas.User)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

@app.post("/token", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, username=form_data.username)
    if not user or not user.verify_password(form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/ohlc_data/{symbol}")
def get_ohlc_data(symbol: str):
    try:
        symbol = unquote(symbol)
        logging.debug(f"Fetching OHLC data for symbol: {symbol}")
        # Add your logic to fetch OHLC data here
        # Return the data or raise an exception if there's an error
    except Exception as e:
        logging.error(f"Error fetching OHLC data for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching OHLC data: {str(e)}")
    
# ... (keep existing endpoints)

from fastapi import FastAPI, HTTPException
from app import crud
from app.models import Signal
from pydantic import BaseModel

app = FastAPI()

class SignalResponse(BaseModel):
    symbol: str
    signal: str
    entry: float
    stop_loss: float
    take_profit: float
    timestamp: datetime  # Change this to datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()  # Convert datetime to ISO format string
        }

@app.get("/api/signals", response_model=List[Signal])
async def get_signals():
    try:
        signals = crud.get_signals()
        if not signals:
            logging.warning("No signals generated")
        return signals
    except Exception as e:
        logging.error(f"Error in get_signals: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ... (other endpoints)

from app.database import get_db

@app.get("/health")
def health_check():
    try:
        db = next(get_db())
        db.execute("SELECT 1")
        return {"status": "healthy"}
    except Exception as e:
        logging.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/test_signal")
def add_test_signal():
    db = next(get_db())
    try:
        test_signal = Signal(
            symbol="BTCUSD",
            signal="BUY",
            entry=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            timestamp=datetime.utcnow()
        )
        db.add(test_signal)
        db.commit()
        return {"message": "Test signal added successfully"}
    except Exception as e:
        db.rollback()
        logging.error(f"Error adding test signal: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/test")
def test():
    return {"message": "Backend is working"}

from fastapi import FastAPI, HTTPException
from typing import List
import logging
from app import crud
from app.models import Signal, OHLC
from pydantic import BaseModel
from datetime import datetime, timedelta

@app.get("/api/ohlc/{symbol}")
async def get_ohlc_data(symbol: str):
    try:
        logging.info(f"Fetching OHLC data for symbol: {symbol}")
        ohlc_data = crud.get_ohlc_data(symbol)
        if not ohlc_data:
            logging.warning(f"No OHLC data available for {symbol}")
        return ohlc_data
    except Exception as e:
        logging.error(f"Error fetching OHLC data: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)