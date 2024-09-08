from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from app.database import Base
from pydantic import BaseModel
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    def verify_password(self, password):
        return bcrypt.verify(password, self.hashed_password)

    @classmethod
    def create(cls, username, email, password):
        return cls(
            username=username,
            email=email,
            hashed_password=bcrypt.hash(password)
        )

class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    signal = Column(String)
    entry = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class OHLC(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float

class Signal(BaseModel):
    symbol: str
    chart_symbol: str
    signal_time: datetime
    entry: float
    stop_loss: float
    take_profit: float
    d_exp: str

    class Config:
        from_attributes = True