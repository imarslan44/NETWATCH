"""
NetWatch - Device Internet Monitor with SMS Alerts
Run: python app.py
Dashboard: http://localhost:5000
Default login: admin / netwatch123
"""

from flask import Flask, render_template, redirect, url_for, request, jsonify, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import threading
import time
import subprocess
import platform
import os
import json
import requests
import socket
import re

# ─── App Setup ───────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'netwatch-change-this-in-production-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'netwatch.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ─── Models ──────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    host = db.Column(db.String(200), nullable=False)   # IP or hostname
    is_active = db.Column(db.Boolean, default=True)
    last_status = db.Column(db.String(20), default='unknown')  # online / offline / unknown
    last_seen = db.Column(db.DateTime, nullable=True)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    events = db.relationship('ConnectionEvent', backref='device', lazy=True, cascade='all, delete-orphan')


class ConnectionEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'), nullable=False)
    event_type = db.Column(db.String(20), nullable=False)   # connected / disconnected
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    duration_seconds = db.Column(db.Integer, nullable=True)  # how long it was online before going offline


class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ─── Settings Helpers ────────────────────────────────────────────────────────

def get_setting(key, default=None):
    s = Settings.query.filter_by(key=key).first()
    return s.value if s else default


def set_setting(key, value):
    s = Settings.query.filter_by(key=key).first()
    if s:
        s.value = value
    else:
        s = Settings(key=key, value=value)
        db.session.add(s)
    db.session.commit()


# ─── SMS Service ─────────────────────────────────────────────────────────────

def send_sms(message: str):
    """Send SMS via configured provider (Twilio or Fast2SMS)."""
    provider = get_setting('sms_provider', 'twilio')

    if provider == 'twilio':
        account_sid = get_setting('twilio_account_sid', '')
        auth_token = get_setting('twilio_auth_token', '')
        from_number = get_setting('twilio_from_number', '')
        to_number = get_setting('alert_phone', '')

        if not all([account_sid, auth_token, from_number, to_number]):
            log_event("SMS not sent: Twilio credentials missing")
            return False

        try:
            response = requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
                data={"From": from_number, "To": to_number, "Body": message},
                auth=(account_sid, auth_token),
                timeout=10
            )
            if response.status_code == 201:
                log_event(f"SMS sent to {to_number}: {message[:50]}")
                return True
            else:
                log_event(f"SMS failed: {response.text[:100]}")
                return False
        except Exception as e:
            log_event(f"SMS error: {str(e)[:100]}")
            return False

    elif provider == 'fast2sms':
        api_key = get_setting('fast2sms_api_key', '')
        to_number = get_setting('alert_phone', '')

        if not all([api_key, to_number]):
            log_event("SMS not sent: Fast2SMS credentials missing")
            return False

        # Strip +91 or 0 prefix for Fast2SMS
        clean_number = re.sub(r'^(\+91|91|0)', '', str(to_number)).strip()

        try:
            response = requests.post(
                "https://www.fast2sms.com/dev/bulkV2",
                headers={"authorization": api_key},
                data={
                    "route": "q",
                    "message": message,
                    "language": "english",
                    "flash": 0,
                    "numbers": clean_number
                },
                timeout=10
            )
            data = response.json()
            if data.get('return'):
                log_event(f"SMS sent via Fast2SMS to {clean_number}")
                return True
            else:
                log_event(f"Fast2SMS failed: {data}")
                return False
        except Exception as e:
            log_event(f"Fast2SMS error: {str(e)[:100]}")
            return False

    return False


# ─── Ping / Monitor ──────────────────────────────────────────────────────────

def ping_host(host: str) -> bool:
    """Returns True if host responds to ping."""
    try:
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'
        result = subprocess.run(
            ['ping', param, '1', timeout_param, '2', host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def resolve_host(host: str) -> str:
    """Try to resolve hostname to IP."""
    try:
        return socket.gethostbyname(host)
    except Exception:
        return host


# In-memory state to track when each device came online
_online_since: dict = {}   # device_id -> datetime

_monitor_thread = None
_monitor_running = False
_log_buffer = []  # recent log lines (in-memory)


def log_event(msg: str):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    _log_buffer.append(line)
    if len(_log_buffer) > 200:
        _log_buffer.pop(0)
    print(line)


def monitor_loop():
    global _monitor_running
    log_event("Monitor started.")
    while _monitor_running:
        try:
            with app.app_context():
                devices = Device.query.filter_by(is_active=True).all()
                interval = int(get_setting('check_interval', '30'))

                for device in devices:
                    is_up = ping_host(device.host)
                    prev_status = device.last_status

                    if is_up:
                        device.last_seen = datetime.utcnow()

                    # ── State changed: came online ──
                    if is_up and prev_status != 'online':
                        device.last_status = 'online'
                        _online_since[device.id] = datetime.utcnow()

                        event = ConnectionEvent(
                            device_id=device.id,
                            event_type='connected',
                            timestamp=datetime.utcnow()
                        )
                        db.session.add(event)
                        db.session.commit()

                        msg = get_setting('sms_connected_template',
                                          '✅ {name} is now ONLINE. Time: {time}')
                        msg = msg.replace('{name}', device.name) \
                                 .replace('{host}', device.host) \
                                 .replace('{time}', datetime.now().strftime('%d %b %Y %I:%M %p'))
                        if get_setting('sms_on_connect', 'true') == 'true':
                            threading.Thread(target=send_sms, args=(msg,), daemon=True).start()
                        log_event(f"CONNECTED: {device.name} ({device.host})")

                    # ── State changed: went offline ──
                    elif not is_up and prev_status == 'online':
                        device.last_status = 'offline'
                        duration = None
                        if device.id in _online_since:
                            duration = int((datetime.utcnow() - _online_since.pop(device.id)).total_seconds())

                        event = ConnectionEvent(
                            device_id=device.id,
                            event_type='disconnected',
                            timestamp=datetime.utcnow(),
                            duration_seconds=duration
                        )
                        db.session.add(event)
                        db.session.commit()

                        dur_str = f"{duration // 60}m {duration % 60}s" if duration else "unknown"
                        msg = get_setting('sms_disconnected_template',
                                          '❌ {name} went OFFLINE. Was online for {duration}. Time: {time}')
                        msg = msg.replace('{name}', device.name) \
                                 .replace('{host}', device.host) \
                                 .replace('{duration}', dur_str) \
                                 .replace('{time}', datetime.now().strftime('%d %b %Y %I:%M %p'))
                        if get_setting('sms_on_disconnect', 'true') == 'true':
                            threading.Thread(target=send_sms, args=(msg,), daemon=True).start()
                        log_event(f"DISCONNECTED: {device.name} ({device.host}), was up for {dur_str}")

                    elif not is_up and prev_status == 'unknown':
                        device.last_status = 'offline'
                        db.session.commit()

                db.session.commit()

            time.sleep(interval)
        except Exception as e:
            log_event(f"Monitor error: {e}")
            time.sleep(10)

    log_event("Monitor stopped.")


def start_monitor():
    global _monitor_thread, _monitor_running
    if _monitor_running:
        return
    _monitor_running = True
    _monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    _monitor_thread.start()


def stop_monitor():
    global _monitor_running
    _monitor_running = False


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    return redirect(url_for('dashboard'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    devices = Device.query.all()
    return render_template('dashboard.html', devices=devices)


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'save_sms':
            for key in ['sms_provider', 'alert_phone',
                        'twilio_account_sid', 'twilio_auth_token', 'twilio_from_number',
                        'fast2sms_api_key',
                        'sms_on_connect', 'sms_on_disconnect',
                        'sms_connected_template', 'sms_disconnected_template']:
                val = request.form.get(key)
                if val is not None:
                    set_setting(key, val.strip())
            # checkboxes
            set_setting('sms_on_connect', 'true' if request.form.get('sms_on_connect') else 'false')
            set_setting('sms_on_disconnect', 'true' if request.form.get('sms_on_disconnect') else 'false')
            flash('SMS settings saved!', 'success')

        elif action == 'save_monitor':
            set_setting('check_interval', request.form.get('check_interval', '30'))
            flash('Monitor settings saved!', 'success')

        elif action == 'add_device':
            name = request.form.get('device_name', '').strip()
            host = request.form.get('device_host', '').strip()
            if name and host:
                device = Device(name=name, host=host)
                db.session.add(device)
                db.session.commit()
                flash(f'Device "{name}" added!', 'success')
            else:
                flash('Device name and IP/hostname are required.', 'error')

        elif action == 'delete_device':
            device_id = request.form.get('device_id')
            device = db.session.get(Device, int(device_id))
            if device:
                db.session.delete(device)
                db.session.commit()
                flash(f'Device "{device.name}" deleted.', 'success')

        elif action == 'toggle_device':
            device_id = request.form.get('device_id')
            device = db.session.get(Device, int(device_id))
            if device:
                device.is_active = not device.is_active
                db.session.commit()

        elif action == 'change_password':
            old_pw = request.form.get('old_password', '')
            new_pw = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_password', '')
            if not current_user.check_password(old_pw):
                flash('Current password is incorrect.', 'error')
            elif new_pw != confirm_pw:
                flash('New passwords do not match.', 'error')
            elif len(new_pw) < 6:
                flash('Password must be at least 6 characters.', 'error')
            else:
                current_user.set_password(new_pw)
                db.session.commit()
                flash('Password changed successfully!', 'success')

        elif action == 'test_sms':
            result = send_sms(f"🔔 NetWatch Test SMS - {datetime.now().strftime('%d %b %Y %I:%M %p')}")
            if result:
                flash('Test SMS sent successfully!', 'success')
            else:
                flash('SMS failed. Check credentials and logs.', 'error')

        return redirect(url_for('settings'))

    s = {row.key: row.value for row in Settings.query.all()}
    devices = Device.query.all()
    return render_template('settings.html', settings=s, devices=devices)


# ─── API Endpoints ───────────────────────────────────────────────────────────

@app.route('/api/status')
@login_required
def api_status():
    devices = Device.query.all()
    return jsonify([{
        'id': d.id,
        'name': d.name,
        'host': d.host,
        'status': d.last_status,
        'is_active': d.is_active,
        'last_seen': d.last_seen.isoformat() if d.last_seen else None
    } for d in devices])


@app.route('/api/chart/<int:device_id>')
@login_required
def api_chart(device_id):
    """Return last 7 days of online time in minutes per day."""
    today = datetime.utcnow().date()
    labels = []
    data = []

    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        labels.append(day.strftime('%a %d'))
        day_start = datetime.combine(day, datetime.min.time())
        day_end = day_start + timedelta(days=1)

        # Sum duration of 'disconnected' events that day (duration = time was online)
        events = ConnectionEvent.query.filter(
            ConnectionEvent.device_id == device_id,
            ConnectionEvent.event_type == 'disconnected',
            ConnectionEvent.timestamp >= day_start,
            ConnectionEvent.timestamp < day_end,
            ConnectionEvent.duration_seconds.isnot(None)
        ).all()
        total_seconds = sum(e.duration_seconds for e in events)
        data.append(round(total_seconds / 60, 1))  # minutes

    return jsonify({'labels': labels, 'data': data})


@app.route('/api/events/<int:device_id>')
@login_required
def api_events(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify([])
    events = ConnectionEvent.query.filter_by(device_id=device_id) \
        .order_by(ConnectionEvent.timestamp.desc()).limit(50).all()
    return jsonify([{
        'type': e.event_type,
        'timestamp': e.timestamp.strftime('%d %b %Y %I:%M:%S %p'),
        'duration': f"{e.duration_seconds // 60}m {e.duration_seconds % 60}s" if e.duration_seconds else '—'
    } for e in events])


@app.route('/api/logs')
@login_required
def api_logs():
    return jsonify({'logs': list(reversed(_log_buffer[-50:]))})


@app.route('/api/monitor/toggle', methods=['POST'])
@login_required
def api_monitor_toggle():
    global _monitor_running
    if _monitor_running:
        stop_monitor()
        return jsonify({'status': 'stopped'})
    else:
        start_monitor()
        return jsonify({'status': 'running'})


@app.route('/api/monitor/status')
@login_required
def api_monitor_status():
    return jsonify({'running': _monitor_running})


# ─── Init & Run ──────────────────────────────────────────────────────────────

def init_db():
    with app.app_context():
        db.create_all()
        # Create default admin user
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin')
            admin.set_password('netwatch123')
            db.session.add(admin)
            db.session.commit()
            print("✅ Default user created: admin / netwatch123")
        # Default settings
        defaults = {
            'sms_provider': 'twilio',
            'alert_phone': '',
            'sms_on_connect': 'true',
            'sms_on_disconnect': 'true',
            'check_interval': '30',
            'sms_connected_template': '✅ {name} is now ONLINE. Time: {time}',
            'sms_disconnected_template': '❌ {name} went OFFLINE. Was online for {duration}. Time: {time}',
        }
        for k, v in defaults.items():
            if not Settings.query.filter_by(key=k).first():
                db.session.add(Settings(key=k, value=v))
        db.session.commit()


if __name__ == '__main__':
    init_db()
    start_monitor()
    print("\n🌐 NetWatch running at http://localhost:5000")
    print("📋 Default login: admin / netwatch123\n")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
