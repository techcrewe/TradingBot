from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from src.signal_generator import generate_signal, get_performance_stats, generate_signals_for_multiple_symbols  # Updated import statement
from flask_migrate import Migrate  # Add this import

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)
migrate = Migrate(app, db)  # Add this line
login_manager = LoginManager(app)
login_manager.login_view = 'login'

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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)