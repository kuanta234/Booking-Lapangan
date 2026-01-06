from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime, timedelta
import uuid 
import json 
import os
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# --- KONFIGURASI FILE ---
BOOKINGS_FILE = '/tmp/bookings_data.json' 
bookings = {} 

def load_bookings():
    global bookings
    if os.path.exists(BOOKINGS_FILE):
        try:
            with open(BOOKINGS_FILE, 'r') as f:
                data = json.load(f)
                bookings = data if isinstance(data, dict) else {}
        except:
            bookings = {}
    else:
        bookings = {}

def save_bookings():
    global bookings
    try:
        with open(BOOKINGS_FILE, 'w') as f:
            json.dump(bookings, f, indent=4)
    except Exception as e:
        print(f"Simpan file dilewati: {e}")

# --- APLIKASI DAN KONFIGURASI FLASK ---
app = Flask(__name__)
app.secret_key = 'kunci_rahasia_bebas_nama' 

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 

# --- KONSTANTA DATA ---
WEB_NAME = "Booking Lapangan"
LAPANGAN_NAMES = ['Lapangan 1', 'Lapangan 2'] 
PRICE_PER_HOUR = 15000 
MASTER_PASSWORD = "password123"  # <--- Password sudah diubah ke password123

JAM_MULAI = list(range(9, 18)) 
JAM_OPERASIONAL = []
for h in JAM_MULAI:
    start_time = datetime(2000, 1, 1, h, 0)
    end_time = start_time + timedelta(hours=1)
    JAM_OPERASIONAL.append(f'{start_time.strftime("%H:%M")}-{end_time.strftime("%H:%M")}')

# --- MODEL USER DINAMIS ---
class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id
        self.username = user_id
        self.full_name = user_id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# --- FILTER MATA UANG ---
@app.template_filter('currency')
def format_currency(value):
    try:
        return "{:,.0f}".format(value).replace(",", ".")
    except:
        return str(value)

# --- HELPER ---
def initialize_day(date_str):
    if date_str not in bookings:
        bookings[date_str] = {}
        for lapangan in LAPANGAN_NAMES:
            bookings[date_str][lapangan] = {jam: None for jam in JAM_OPERASIONAL}

load_bookings()

# --- ROUTES ---

@app.route('/')
def index():
    today_date = datetime.now().strftime('%Y-%m-%d')
    return redirect(url_for('show_schedule', date_str=today_date))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username_input = request.form.get('username')
        password_input = request.form.get('password')
        
        if password_input == MASTER_PASSWORD:
            user_obj = User(username_input)
            login_user(user_obj)
            flash(f'Selamat datang, {username_input}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Password salah!', 'danger')
            
    return render_template('login.html', web_name=WEB_NAME)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda telah logout.', 'success')
    return redirect(url_for('login'))

@app.route('/schedule/<date_str>')
@login_required
def show_schedule(date_str):
    today_date_str = datetime.now().strftime('%Y-%m-%d')
    try:
        current_date = datetime.strptime(date_str, '%Y-%m-%d')
        today_date = datetime.strptime(today_date_str, '%Y-%m-%d')
    except ValueError:
        return redirect(url_for('show_schedule', date_str=today_date_str))
    
    if current_date < today_date:
        return redirect(url_for('show_schedule', date_str=today_date_str))
    
    initialize_day(date_str)
    prev_date = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
    
    return render_template(
        'schedule.html',
        date_str=date_str,
        lapangan_names=LAPANGAN_NAMES,
        jam_operasional=JAM_OPERASIONAL,
        schedule=bookings[date_str],
        prev_date=prev_date,
        next_date=next_date,
        price_per_hour=PRICE_PER_HOUR,
        web_name=WEB_NAME,
        is_current_date_today=(current_date == today_date)
    )

@app.route('/book', methods=['POST'])
@login_required
def book():
    date_str = request.form.get('date')
    lapangan_name = request.form.get('lapangan')
    time_slot = request.form.get('time')
    
    if not all([date_str, lapangan_name, time_slot]):
        return redirect(url_for('index'))

    initialize_day(date_str)
    if bookings[date_str][lapangan_name][time_slot] is None:
        bookings[date_str][lapangan_name][time_slot] = {
            'id': str(uuid.uuid4()),
            'user_name': current_user.full_name,
            'status': 'Booked',
            'price': PRICE_PER_HOUR,
            'payment_method': None
        }
        save_bookings()
        flash('Booking berhasil! Segera bayar.', 'warning')
    return redirect(url_for('show_schedule', date_str=date_str))

@app.route('/pay', methods=['POST'])
@login_required
def pay():
    date_str = request.form.get('date')
    lapangan_name = request.form.get('lapangan').replace('%20', ' ')
    time_slot = request.form.get('time')
    payment_method = request.form.get('payment_method')

    initialize_day(date_str)
    slot = bookings[date_str][lapangan_name].get(time_slot)

    if slot and slot['user_name'] == current_user.full_name:
        slot['status'] = 'Paid'
        slot['payment_method'] = payment_method
        save_bookings()
        return redirect(url_for('receipt', date_str=date_str, lapangan_name=lapangan_name, time_slot=time_slot))
    return redirect(url_for('show_schedule', date_str=date_str))

@app.route('/receipt/<date_str>/<lapangan_name>/<time_slot>')
@login_required
def receipt(date_str, lapangan_name, time_slot):
    lapangan_name = lapangan_name.replace('%20', ' ')
    initialize_day(date_str)
    slot = bookings[date_str][lapangan_name].get(time_slot)
    
    if slot and slot['status'] == 'Paid' and slot['user_name'] == current_user.full_name:
        return render_template('receipt.html', date_str=date_str, lapangan_name=lapangan_name, time_slot=time_slot, slot=slot, web_name=WEB_NAME)
    return redirect(url_for('index'))

@app.route('/cancel/<date_str>/<lapangan_name>/<time_slot>')
@login_required
def cancel(date_str, lapangan_name, time_slot):
    lapangan_name = lapangan_name.replace('%20', ' ')
    initialize_day(date_str)
    slot = bookings[date_str][lapangan_name].get(time_slot)
    if slot and slot['user_name'] == current_user.full_name:
        bookings[date_str][lapangan_name][time_slot] = None
        save_bookings()
        flash('Booking dibatalkan.', 'success')
    return redirect(url_for('show_schedule', date_str=date_str))

if __name__ == '__main__':
    app.run(debug=True)


