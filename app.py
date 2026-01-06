from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime, timedelta
import uuid 
import locale 
import json 
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# --- KONFIGURASI FILE & PERSISTENCY ---
BOOKINGS_FILE = 'bookings_data.json' 
bookings = {} 

def load_bookings():
    """Memuat data booking dari file JSON saat aplikasi dimulai."""
    global bookings
    try:
        with open(BOOKINGS_FILE, 'r') as f:
            data = json.load(f)
            if isinstance(data, dict):
                bookings = data
            else:
                bookings = {}
    except (FileNotFoundError, json.JSONDecodeError):
        bookings = {}

def save_bookings():
    """Menyimpan data booking ke file JSON setelah ada perubahan."""
    global bookings
    try:
        with open(BOOKINGS_FILE, 'w') as f:
            json.dump(bookings, f, indent=4)
    except IOError as e:
        print(f"Error saat menyimpan data booking: {e}")

# --- APLIKASI DAN KONFIGURASI FLASK ---
app = Flask(__name__)
app.secret_key = 'kunci_rahasia_anda' 

# Inisialisasi Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 

# Modifikasi Pesan Default Flask-Login
login_manager.login_message = "Anda harus login untuk mengakses halaman jadwal."
login_manager.login_message_category = "warning"

# --- KONSTANTA DAN DATA DUMMY ---
WEB_NAME = "Booking Lapangan" # DIUBAH: Nama web disederhanakan
LAPANGAN_NAMES = ['Lapangan 1', 'Lapangan 2'] 
PRICE_PER_HOUR = 15000 

# Data Pengguna Dummy (Simulasi Database)
USERS = {
    'user1': {'id': 'user1', 'username': 'user1', 'password': 'password123', 'full_name': 'Budi Santoso'},
    'user2': {'id': 'user2', 'username': 'user2', 'password': 'password123', 'full_name': 'Siti Aisyah'}
}

# Logic Jam Operasional (09:00 - 18:00)
JAM_MULAI = list(range(9, 18)) 
JAM_OPERASIONAL = []
for h in JAM_MULAI:
    start_time = datetime(2000, 1, 1, h, 0)
    end_time = start_time + timedelta(hours=1)
    JAM_OPERASIONAL.append(f'{start_time.strftime("%H:%M")}-{end_time.strftime("%H:%M")}')


# --- MODEL DAN HELPER LOGIN ---

class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data['id']
        self.username = user_data['username']
        self.full_name = user_data['full_name']
        self.password = user_data['password']

@login_manager.user_loader
def load_user(user_id):
    if user_id in USERS:
        return User(USERS[user_id])
    return None

# --- FILTER JINJA2 ---
def format_currency(value):
    try:
        # Mengatur locale Indonesia untuk format mata uang
        locale.setlocale(locale.LC_ALL, 'id_ID.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, 'id_ID') 
        except locale.Error:
             # Fallback format jika locale ID tidak tersedia
             return "{:,.0f}".format(value).replace(",", "#").replace(".", ",").replace("#", ".")
        
    formatted = locale.format_string("%.0f", value, grouping=True)
    return formatted.split(',')[0].split('.')[0] 

app.jinja_env.filters['currency'] = format_currency 

# --- FUNGSI HELPER UMUM ---
def initialize_day(date_str):
    """Memastikan setiap hari memiliki struktur data slot kosong."""
    if date_str not in bookings:
        bookings[date_str] = {}
        for lapangan in LAPANGAN_NAMES:
            bookings[date_str][lapangan] = {jam: None for jam in JAM_OPERASIONAL}

# --- ROUTES APLIKASI ---

@app.route('/')
def index():
    """Route utama. Redirect ke jadwal hari ini."""
    today_date = datetime.now().strftime('%Y-%m-%d')
    return redirect(url_for('show_schedule', date_str=today_date))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Menangani proses login pengguna."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username in USERS and USERS[username]['password'] == password:
            user_data = USERS[username]
            user_obj = User(user_data)
            
            login_user(user_obj) 
            
            flash('Login berhasil!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Username atau password salah.', 'danger')
            
    return render_template('login.html', web_name=WEB_NAME)

@app.route('/logout')
@login_required 
def logout():
    """Menangani proses logout pengguna."""
    logout_user()
    flash('Anda telah logout.', 'success')
    return redirect(url_for('login'))

@app.route('/schedule/<date_str>')
@login_required 
def show_schedule(date_str):
    """Menampilkan tabel jadwal booking dengan pembatasan tanggal."""
    
    today_date_str = datetime.now().strftime('%Y-%m-%d')
    try:
        current_date = datetime.strptime(date_str, '%Y-%m-%d')
        today_date = datetime.strptime(today_date_str, '%Y-%m-%d')
    except ValueError:
        # Jika format tanggal salah, arahkan ke hari ini
        return redirect(url_for('show_schedule', date_str=today_date_str))
    
    # --- PEMBATASAN AKSES: Tidak bisa melihat tanggal sebelum hari ini ---
    if current_date < today_date:
        # Langsung alihkan tanpa pesan flash, sehingga akses benar-benar tertutup.
        return redirect(url_for('show_schedule', date_str=today_date_str))
    # ------------------------------------------------------------------
    
    initialize_day(date_str)
    
    prev_date = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Flag untuk membantu menonaktifkan tombol 'Hari Sebelumnya' di template
    is_current_date_today = (current_date == today_date)

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
        is_current_date_today=is_current_date_today 
    )

@app.route('/book', methods=['POST'])
@login_required 
def book():
    """Memproses permintaan booking slot waktu."""
    date_str = request.form.get('date')
    lapangan_name = request.form.get('lapangan')
    time_slot = request.form.get('time')
    user_name = current_user.full_name 

    if not all([date_str, lapangan_name, time_slot]):
        flash('Data booking tidak lengkap!', 'danger')
        return redirect(url_for('show_schedule', date_str=date_str))
    
    # Tambahkan pengecekan agar tidak bisa booking di masa lalu
    today_date_str = datetime.now().strftime('%Y-%m-%d')
    if date_str < today_date_str:
        flash('Booking untuk masa lalu tidak diizinkan.', 'danger')
        return redirect(url_for('show_schedule', date_str=today_date_str))
    # Catatan: Booking di masa depan (setelah hari ini) diizinkan.

    initialize_day(date_str)
    
    # Logika Proteksi Booking
    if bookings[date_str][lapangan_name][time_slot] is None:
        # Slot Tersedia
        booking_id = str(uuid.uuid4())
        bookings[date_str][lapangan_name][time_slot] = {
            'id': booking_id,
            'user_name': user_name,
            'status': 'Booked', 
            'price': PRICE_PER_HOUR,
            'payment_method': None
        }
        save_bookings() 
        formatted_price = format_currency(PRICE_PER_HOUR)
        flash(f'Booking **sementara** berhasil! Total: Rp {formatted_price}.', 'warning')
    else:
        # Slot Sudah Terisi
        flash('Slot waktu ini sudah dibooking.', 'danger') 
        
    return redirect(url_for('show_schedule', date_str=date_str))

@app.route('/pay', methods=['POST'])
@login_required 
def pay():
    """Memproses pembayaran dan mengubah status booking menjadi 'Paid'. (Fitur Otorisasi)"""
    date_str = request.form.get('date')
    lapangan_name = request.form.get('lapangan')
    time_slot = request.form.get('time')
    payment_method = request.form.get('payment_method')

    initialize_day(date_str)
    slot = bookings[date_str][lapangan_name][time_slot]

    if not slot:
        flash('Slot booking tidak ditemukan.', 'danger')
        return redirect(url_for('show_schedule', date_str=date_str))

    # --- OTORISASI: Mencegah pembayaran pesanan akun lain ---
    if slot['user_name'] != current_user.full_name:
        flash('Anda tidak memiliki izin untuk membayar pesanan akun lain.', 'danger')
        return redirect(url_for('show_schedule', date_str=date_str))
    # -----------------------------------------------------------

    if slot['status'] == 'Booked':
        slot['status'] = 'Paid'
        slot['payment_method'] = payment_method
        save_bookings() 
        flash(f'Pembayaran **berhasil** untuk {lapangan_name} jam {time_slot} ({payment_method}).', 'success')
        return redirect(url_for('receipt', date_str=date_str, lapangan_name=lapangan_name, time_slot=time_slot))
    else:
        flash('Slot sudah dibayar atau status tidak valid.', 'danger')
        
    return redirect(url_for('show_schedule', date_str=date_str))

@app.route('/receipt/<date_str>/<lapangan_name>/<time_slot>')
@login_required 
def receipt(date_str, lapangan_name, time_slot):
    """Menampilkan Resit Pembayaran. (Fitur Otorisasi)"""
    initialize_day(date_str)
    slot = bookings[date_str][lapangan_name][time_slot]

    if not slot:
        flash('Resit tidak dapat ditampilkan: Slot booking tidak ditemukan.', 'danger')
        return redirect(url_for('show_schedule', date_str=date_str))

    # --- OTORISASI: Mencegah melihat resit akun lain ---
    if slot['user_name'] != current_user.full_name:
        flash('Anda tidak memiliki izin untuk melihat resit pesanan akun lain.', 'danger')
        return redirect(url_for('show_schedule', date_str=date_str))
    # ---------------------------------------------------------------------
    
    if slot['status'] == 'Paid':
        return render_template(
            'receipt.html',
            date_str=date_str,
            lapangan_name=lapangan_name,
            time_slot=time_slot,
            slot=slot,
            web_name=WEB_NAME
        )
    else:
        flash('Resit tidak dapat ditampilkan karena pesanan belum dibayar.', 'danger')
        return redirect(url_for('show_schedule', date_str=date_str))

@app.route('/cancel/<date_str>/<lapangan_name>/<time_slot>')
@login_required 
def cancel(date_str, lapangan_name, time_slot):
    """Membatalkan booking dan membuat resit pembatalan. (Fitur Otorisasi)"""
    initialize_day(date_str)
    slot = bookings[date_str][lapangan_name][time_slot]

    if not slot:
        flash('Slot booking tidak ditemukan.', 'danger')
        return redirect(url_for('show_schedule', date_str=date_str))

    # --- OTORISASI: Mencegah pembatalan pesanan akun lain ---
    if slot['user_name'] != current_user.full_name:
        flash('Anda tidak memiliki izin untuk membatalkan pesanan akun lain.', 'danger')
        return redirect(url_for('show_schedule', date_str=date_str))
    # ---------------------------------------------------------------
    
    if slot['status'] != 'Cancelled':
        cancelled_data = slot.copy()
        
        # Hapus data booking dari memori
        bookings[date_str][lapangan_name][time_slot] = None 
        save_bookings() 
        
        flash(f'Booking **berhasil dibatalkan** untuk {lapangan_name} jam {time_slot}.', 'success')
        
        return redirect(url_for('cancellation_receipt', 
            date_str=date_str, 
            lapangan_name=lapangan_name, 
            time_slot=time_slot, 
            user_name=cancelled_data['user_name'],
            booking_id=cancelled_data['id']
        ))
    else:
        flash('Slot sudah dibatalkan sebelumnya.', 'danger')
        
    return redirect(url_for('show_schedule', date_str=date_str))

@app.route('/cancellation_receipt')
@login_required 
def cancellation_receipt():
    """Menampilkan Resit Pembatalan."""
    date_str = request.args.get('date_str')
    
    if not date_str:
        flash('Data resit pembatalan tidak lengkap.', 'danger')
        return redirect(url_for('index'))
        
    return render_template(
        'cancellation_receipt.html',
        date_str=date_str,
        lapangan_name=request.args.get('lapangan_name'),
        time_slot=request.args.get('time_slot'),
        user_name=request.args.get('user_name'),
        booking_id=request.args.get('booking_id'),
        cancellation_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        web_name=WEB_NAME
    )

# Menjalankan aplikasi
if __name__ == '__main__':
    load_bookings() 
    app.run(debug=True)