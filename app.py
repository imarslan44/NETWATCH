"""
NetWatch P2P - Simple Device Connection Monitor
Two devices monitor each other's internet connection with in-app notifications.
"""

from flask import Flask, render_template, redirect, url_for, request, jsonify, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import threading
import time
import subprocess
import platform
import os
import requests
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── Configuration ───────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'netwatch-dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'netwatch.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ─── Database Models ──────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    device_name = db.Column(db.String(100), default='My Device')
    device_ip = db.Column(db.String(50), nullable=True)
    last_status = db.Column(db.String(20), default='unknown')  # online/offline/unknown
    last_status_change = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Email settings
    email = db.Column(db.String(120), nullable=True)
    email_enabled = db.Column(db.Boolean, default=False)
    
    peers = db.relationship('Peer', backref='owner', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade='all, delete-orphan')
    events = db.relationship('ConnectionEvent', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Peer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    peer_username = db.Column(db.String(80), nullable=False)
    peer_device_name = db.Column(db.String(100), nullable=False)
    peer_ip = db.Column(db.String(50), nullable=False)
    peer_port = db.Column(db.Integer, default=5000)
    api_key = db.Column(db.String(100), nullable=False)  # For authentication
    is_active = db.Column(db.Boolean, default=True)
    last_connected = db.Column(db.DateTime, nullable=True)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    from_device = db.Column(db.String(100), nullable=False)
    event_type = db.Column(db.String(30), nullable=False)  # 'connected', 'disconnected'
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ConnectionEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_type = db.Column(db.String(20), nullable=False)  # 'connected', 'disconnected'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class ConnectionRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    from_user = db.relationship('User', foreign_keys=[from_user_id], backref='requests_sent')
    to_user = db.relationship('User', foreign_keys=[to_user_id], backref='requests_received')


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ─── Internet Monitoring ──────────────────────────────────────────────────────

def is_connected_to_internet() -> bool:
    """Check if device has internet connection by pinging Google DNS"""
    try:
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'
        # Ping with 5000ms (5 second) timeout - gives enough time for response
        result = subprocess.run(
            ['ping', param, '1', timeout_param, '5000', '8.8.8.8'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10
        )
        is_online = result.returncode == 0
        print(f"[Monitor] Internet check: {'ONLINE' if is_online else 'OFFLINE'}")
        return is_online
    except Exception as e:
        print(f"[Monitor] Ping failed: {e}")
        return False


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send email notification using Gmail SMTP"""
    try:
        print(f"[Email] Attempting to send to {to_email}...")
        # Using Gmail SMTP (you can change to another provider)
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        sender_email = "imarslan444@gmail.com"  # Change this to your email
        sender_password = "jqhw dsbn lflg wxjf"  # For Gmail: use app-specific password
        
        # Create message
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = to_email
        message["Subject"] = subject
        
        message.attach(MIMEText(body, "plain"))
        
        # Send email
        print(f"[Email] Connecting to {smtp_server}:{smtp_port}...")
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            print(f"[Email] Starting TLS...")
            server.starttls()
            print(f"[Email] Logging in...")
            server.login(sender_email, sender_password)
            print(f"[Email] Sending message...")
            server.send_message(message)
        
        print(f"[Email] ✓ Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        print(f"[Email] ✗ Failed to send email to {to_email}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def notify_peers(user_id, event_type, message):
    """Send notification to all connected peers (in-app + email)"""
    user = User.query.get(user_id)
    if not user:
        return

    # Send email to the user if enabled
    if user.email_enabled and user.email:
        email_subject = f"NetWatch: {user.device_name} went {'ONLINE' if event_type == 'connected' else 'OFFLINE'}"
        email_body = f"""
Device: {user.device_name}
Status: {event_type.upper()}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{message}
"""
        threading.Thread(target=send_email, args=(user.email, email_subject, email_body), daemon=True).start()

    peers = Peer.query.filter_by(user_id=user_id, is_active=True).all()

    for peer in peers:
        try:
            # Call peer's API endpoint
            url = f"http://{peer.peer_ip}:{peer.peer_port}/api/notify"
            payload = {
                'from_device': user.device_name,
                'event_type': event_type,
                'message': message,
                'api_key': peer.api_key
            }
            requests.post(url, json=payload, timeout=10)
            peer.last_connected = datetime.utcnow()
            db.session.commit()
        except Exception as e:
            print(f"Failed to notify peer {peer.peer_username}: {e}")


_monitor_running = False
_monitor_thread = None


def monitor_loop():
    """Monitor device's own internet connection"""
    global _monitor_running
    print("Internet monitor started")

    # Track previous status per user
    user_previous_status = {}

    while _monitor_running:
        try:
            with app.app_context():
                # Check all users
                for user in User.query.all():
                    is_online = is_connected_to_internet()
                    current_status = 'online' if is_online else 'offline'
                    
                    # Get previous status for this specific user
                    previous_status = user_previous_status.get(user.id, 'unknown')

                    # Status changed
                    if current_status != previous_status and previous_status != 'unknown':
                        user.last_status = current_status
                        user.last_status_change = datetime.utcnow()

                        event = ConnectionEvent(
                            user_id=user.id,
                            event_type='connected' if is_online else 'disconnected'
                        )
                        db.session.add(event)
                        db.session.commit()

                        message = f"{user.device_name} is now {'ONLINE' if is_online else 'OFFLINE'}"
                        notify_peers(user.id, event_type='connected' if is_online else 'disconnected', message=message)
                        print(f"[{user.username}] {message}")
                    else:
                        # Just update status without notifying (no change)
                        user.last_status = current_status
                        db.session.commit()
                    
                    # Store status for next iteration
                    user_previous_status[user.id] = current_status

            time.sleep(30)  # Check every 30 seconds

        except Exception as e:
            print(f"Monitor error: {e}")
            time.sleep(10)

    print("Internet monitor stopped")


def start_monitor():
    """Start the monitoring thread"""
    global _monitor_thread, _monitor_running
    if _monitor_running:
        return
    _monitor_running = True
    _monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    _monitor_thread.start()


def stop_monitor():
    """Stop the monitoring thread"""
    global _monitor_running
    _monitor_running = False


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        device_name = request.form.get('device_name', 'My Device')

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('register'))

        user = User(username=username, device_name=device_name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Account created! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/dashboard')
@login_required
def dashboard():
    peers = Peer.query.filter_by(user_id=current_user.id, is_active=True).all()
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    recent_events = ConnectionEvent.query.filter_by(user_id=current_user.id).order_by(ConnectionEvent.timestamp.desc()).limit(10).all()
    pending_requests = ConnectionRequest.query.filter_by(to_user_id=current_user.id, status='pending').all()

    return render_template('dashboard.html', 
                          user=current_user,
                          peers=peers,
                          notifications=notifications,
                          recent_events=recent_events,
                          pending_requests=pending_requests)


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        current_user.device_name = request.form.get('device_name', current_user.device_name)
        current_user.email = request.form.get('email', current_user.email)
        current_user.email_enabled = request.form.get('email_enabled') == 'on'
        db.session.commit()
        flash('Settings updated', 'success')
        return redirect(url_for('settings'))

    return render_template('settings.html', user=current_user)


@app.route('/add-peer', methods=['POST'])
@login_required
def add_peer():
    peer_ip = request.form.get('peer_ip')
    peer_device_name = request.form.get('peer_device_name')

    if not peer_ip or not peer_device_name:
        flash('Please provide peer IP and device name', 'error')
        return redirect(url_for('settings'))

    # Try to connect and get peer info
    try:
        response = requests.get(f"http://{peer_ip}:5000/api/info", timeout=5)
        if response.status_code == 200:
            peer_data = response.json()
            api_key = os.urandom(32).hex()  # Generate unique API key for this peer

            peer = Peer(
                user_id=current_user.id,
                peer_username=peer_data.get('username'),
                peer_device_name=peer_device_name,
                peer_ip=peer_ip,
                api_key=api_key,
                is_active=True
            )
            db.session.add(peer)
            db.session.commit()

            flash(f'Peer {peer_device_name} added successfully', 'success')
        else:
            flash('Could not reach peer device', 'error')
    except Exception as e:
        flash(f'Error connecting to peer: {str(e)}', 'error')

    return redirect(url_for('settings'))


@app.route('/devices')
@login_required
def devices():
    """List all registered devices for connection"""
    all_users = User.query.filter(User.id != current_user.id).all()
    
    # Get current connections (peers)
    current_peers = db.session.query(Peer.peer_username).filter_by(user_id=current_user.id).all()
    current_peer_usernames = [p[0] for p in current_peers]
    
    # Get pending requests sent by current user
    pending_requests_sent = db.session.query(ConnectionRequest.to_user_id).filter_by(
        from_user_id=current_user.id, status='pending'
    ).all()
    pending_sent_ids = [r[0] for r in pending_requests_sent]
    
    # Get pending requests received by current user
    pending_requests_received = ConnectionRequest.query.filter_by(
        to_user_id=current_user.id, status='pending'
    ).all()
    
    return render_template('devices.html', 
                          all_users=all_users,
                          current_peer_usernames=current_peer_usernames,
                          pending_sent_ids=pending_sent_ids,
                          pending_requests=pending_requests_received)


@app.route('/send-request/<int:user_id>', methods=['POST'])
@login_required
def send_request(user_id):
    """Send connection request to another device"""
    if user_id == current_user.id:
        flash('Cannot send request to yourself', 'error')
        return redirect(url_for('devices'))
    
    # Check if request already exists
    existing_request = ConnectionRequest.query.filter(
        ((ConnectionRequest.from_user_id == current_user.id) & (ConnectionRequest.to_user_id == user_id)) |
        ((ConnectionRequest.from_user_id == user_id) & (ConnectionRequest.to_user_id == current_user.id))
    ).first()
    
    if existing_request:
        flash('Request already exists with this device', 'error')
        return redirect(url_for('devices'))
    
    # Check if already connected
    existing_peer = Peer.query.filter_by(user_id=current_user.id).filter(
        Peer.peer_username == User.query.get(user_id).username
    ).first()
    
    if existing_peer:
        flash('Already connected to this device', 'error')
        return redirect(url_for('devices'))
    
    conn_request = ConnectionRequest(
        from_user_id=current_user.id,
        to_user_id=user_id,
        status='pending'
    )
    db.session.add(conn_request)
    db.session.commit()
    
    flash('Connection request sent!', 'success')
    return redirect(url_for('devices'))


@app.route('/respond-request/<int:request_id>/<action>', methods=['POST'])
@login_required
def respond_request(request_id, action):
    """Accept or reject connection request"""
    conn_request = ConnectionRequest.query.get(request_id)
    
    if not conn_request or conn_request.to_user_id != current_user.id:
        flash('Invalid request', 'error')
        return redirect(url_for('dashboard'))
    
    if action == 'accept':
        # Get the requesting user's info
        from_user = User.query.get(conn_request.from_user_id)
        
        # Create API key for secure communication
        api_key = os.urandom(32).hex()
        
        # Add as peer (mutual connection)
        peer = Peer(
            user_id=current_user.id,
            peer_username=from_user.username,
            peer_device_name=from_user.device_name,
            peer_ip='',  # Will be determined when notifying
            api_key=api_key,
            is_active=True
        )
        db.session.add(peer)
        
        conn_request.status = 'accepted'
        db.session.commit()
        
        flash(f'Connected to {from_user.device_name}!', 'success')
    
    elif action == 'reject':
        conn_request.status = 'rejected'
        db.session.commit()
        flash('Request rejected', 'success')
    
    return redirect(url_for('dashboard'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ─── API Endpoints (for peer communication) ───────────────────────────────────

@app.route('/api/info')
def api_info():
    """Return basic info about this device"""
    return jsonify({
        'username': current_user.username if current_user.is_authenticated else None,
        'device_name': current_user.device_name if current_user.is_authenticated else None,
        'status': current_user.last_status if current_user.is_authenticated else 'unknown'
    })


@app.route('/api/notify', methods=['POST'])
def api_notify():
    """Receive notification from peer"""
    data = request.json
    api_key = data.get('api_key')
    from_device = data.get('from_device')
    event_type = data.get('event_type')
    message = data.get('message')

    # Find peer and user by API key
    peer = Peer.query.filter_by(api_key=api_key).first()
    if not peer:
        return jsonify({'error': 'Invalid API key'}), 401

    # Create notification for the user
    notification = Notification(
        user_id=peer.user_id,
        from_device=from_device,
        event_type=event_type,
        message=message
    )
    db.session.add(notification)
    db.session.commit()

    return jsonify({'success': True}), 200


# ─── Main ───────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        start_monitor()

    try:
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False)
    except KeyboardInterrupt:
        stop_monitor()
        print("Shutting down...")
