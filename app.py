from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from src.signal_generator import generate_signal, get_performance_stats, generate_signals_for_multiple_symbols  # Updated import statement
from flask_migrate import Migrate  # Add this import
import yfinance as yf
import pandas as pd
import logging
from urllib.parse import unquote  # Add this import
import json
import numpy as np
from flask_socketio import SocketIO, emit
from threading import Lock
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)
migrate = Migrate(app, db)  # Add this line
login_manager = LoginManager(app)
login_manager.login_view = 'login'

logging.basicConfig(level=logging.DEBUG)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    selected_symbol = db.Column(db.String(20), nullable=True)  # Changed from selected_stock to selected_symbol

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)  # Remove the method parameter
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        current_user.selected_symbol = request.form['symbol']  # Changed from 'stock' to 'symbol'
        db.session.commit()
    return render_template('dashboard.html', symbol=current_user.selected_symbol or 'AAPL')  # Default to AAPL if no symbol is selected

@app.route('/get_signals')
@login_required
def get_signals():
    signals = generate_signals_for_multiple_symbols()
    return jsonify(signals)

@app.route('/get_signal')
@login_required
def get_signal():
    if current_user.selected_symbol:
        signal_data = generate_signal(current_user.selected_symbol)
        print('Signal data:', signal_data)  # Add this line for debugging
        return jsonify(signal_data)
    return jsonify({'error': 'No symbol selected'})

@app.route('/performance')
@login_required
def performance():
    if current_user.selected_symbol:
        stats = get_performance_stats(current_user.selected_symbol)
        return jsonify(stats)
    return jsonify({'error': 'No symbol selected'})

@app.route('/get_ohlc_data/<path:symbol>')
@login_required
def get_ohlc_data(symbol):
    try:
        symbol = unquote(symbol)
        logging.debug(f"Fetching OHLC data for symbol: {symbol}")
        
        if '/' in symbol:  # Forex pair
            base, quote = symbol.split('/')
            symbol = f"{base}{quote}=X"
        
        logging.debug(f"Adjusted symbol for yfinance: {symbol}")
        data = yf.Ticker(symbol)
        df = data.history(period="6mo")

        logging.debug(f"Data fetched, shape: {df.shape}")

        if df.empty:
            logging.warning(f"No data returned for symbol: {symbol}")
            return jsonify({'error': 'No data available for this symbol'}), 404

        # Calculate moving averages
        df['ma5'] = df['Close'].rolling(window=5).mean()
        df['ma8'] = df['Close'].rolling(window=8).mean()
        df['ma21'] = df['Close'].rolling(window=21).mean()
        df['ma50'] = df['Close'].rolling(window=50).mean()
        df['ma100'] = df['Close'].rolling(window=100).mean()
        df['ma200'] = df['Close'].rolling(window=200).mean()

        # Calculate MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - signal

        # Prepare data for Lightweight Charts
        ohlc_data = df.reset_index().apply(lambda row: {
            'time': int(row['Date'].timestamp()),
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close'])
        }, axis=1).tolist()

        ma_data = {
            'ma5': df.reset_index().apply(lambda row: {'time': int(row['Date'].timestamp()), 'value': float(row['ma5']) if pd.notnull(row['ma5']) else None}, axis=1).tolist(),
            'ma8': df.reset_index().apply(lambda row: {'time': int(row['Date'].timestamp()), 'value': float(row['ma8']) if pd.notnull(row['ma8']) else None}, axis=1).tolist(),
            'ma21': df.reset_index().apply(lambda row: {'time': int(row['Date'].timestamp()), 'value': float(row['ma21']) if pd.notnull(row['ma21']) else None}, axis=1).tolist(),
            'ma50': df.reset_index().apply(lambda row: {'time': int(row['Date'].timestamp()), 'value': float(row['ma50']) if pd.notnull(row['ma50']) else None}, axis=1).tolist(),
            'ma100': df.reset_index().apply(lambda row: {'time': int(row['Date'].timestamp()), 'value': float(row['ma100']) if pd.notnull(row['ma100']) else None}, axis=1).tolist(),
            'ma200': df.reset_index().apply(lambda row: {'time': int(row['Date'].timestamp()), 'value': float(row['ma200']) if pd.notnull(row['ma200']) else None}, axis=1).tolist(),
        }

        macd_data = {
            'macd': df.reset_index().apply(lambda row: {'time': int(row['Date'].timestamp()), 'value': float(macd.loc[row['Date']]) if pd.notnull(macd.loc[row['Date']]) else None}, axis=1).tolist(),
            'signal': df.reset_index().apply(lambda row: {'time': int(row['Date'].timestamp()), 'value': float(signal.loc[row['Date']]) if pd.notnull(signal.loc[row['Date']]) else None}, axis=1).tolist(),
            'histogram': df.reset_index().apply(lambda row: {'time': int(row['Date'].timestamp()), 'value': float(histogram.loc[row['Date']]) if pd.notnull(histogram.loc[row['Date']]) else None}, axis=1).tolist(),
        }

        logging.debug(f"Successfully prepared data for symbol: {symbol}")
        response_data = {
            'ohlc': ohlc_data,
            'ma5': ma_data['ma5'],
            'ma8': ma_data['ma8'],
            'ma21': ma_data['ma21'],
            'ma50': ma_data['ma50'],
            'ma100': ma_data['ma100'],
            'ma200': ma_data['ma200'],
            'macd': macd_data,
        }
        return app.response_class(
            response=json.dumps(response_data, cls=NpEncoder),
            status=200,
            mimetype='application/json'
        )

    except Exception as e:
        logging.error(f"Error fetching OHLC data for symbol {symbol}: {str(e)}")
        return jsonify({'error': str(e)}), 500

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (pd.Timestamp, pd.Timedelta)):
            return str(obj)
        if pd.isna(obj):
            return None
        return super(NpEncoder, self).default(obj)

socketio = SocketIO(app, cors_allowed_origins="*")
thread = None
thread_lock = Lock()

def background_thread():
    symbols = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF', 'AUD/USD', 'USD/CAD', 'NZD/USD']
    while True:
        for symbol in symbols:
            data = get_latest_data(symbol)
            socketio.emit('ohlc_update', {'symbol': symbol, 'data': data})
        time.sleep(5)  # Update every 5 seconds

def get_latest_data(symbol):
    if '/' in symbol:
        base, quote = symbol.split('/')
        symbol = f"{base}{quote}=X"
    
    data = yf.Ticker(symbol)
    df = data.history(period="1d", interval="1m")
    
    if df.empty:
        return None

    latest = df.iloc[-1]
    return {
        'time': int(latest.name.timestamp()),
        'open': float(latest['Open']),
        'high': float(latest['High']),
        'low': float(latest['Low']),
        'close': float(latest['Close'])
    }

@socketio.on('connect')
def test_connect():
    global thread
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(background_thread)

if __name__ == '__main__':
    socketio.run(app, debug=True)