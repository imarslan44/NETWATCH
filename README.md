# 📡 NetWatch — Device Internet Monitor with SMS Alerts

Monitor any device on your network. Get **SMS alerts** the moment a device
connects or disconnects from the internet. View weekly uptime charts on a
clean, dark web dashboard.

---

## ✨ Features

| Feature | Details |
|---|---|
| **SMS Alerts** | Auto-send SMS on connect / disconnect |
| **SMS Providers** | Twilio (worldwide) or Fast2SMS (India 🇮🇳) |
| **Dashboard** | Real-time device status with live updates |
| **Weekly Chart** | Bar chart of daily online time for last 7 days |
| **Event Log** | Full history of connects & disconnects |
| **Always On** | Runs as a systemd service (Linux) or Task Scheduler (Windows) |
| **Login** | Secure login — change password from dashboard |
| **Multi-device** | Monitor multiple devices simultaneously |

---

## 🚀 Quick Start

### Option A — Run directly (any OS)
```bash
pip install -r requirements.txt
python app.py
# Open http://localhost:5000
```

### Option B — Linux auto-start (runs on boot)
```bash
chmod +x install.sh
./install.sh           # installs as systemd service
# OR
./install.sh --run     # just run without installing service
```

### Option C — Windows auto-start
Double-click `install.bat` — sets up Task Scheduler to run on every login.

---

## 🔑 Default Login

| Field | Value |
|---|---|
| URL | http://localhost:5000 |
| Username | admin |
| Password | netwatch123 |

**Change your password** in Settings → Change Password immediately after setup.

---

## 📲 SMS Setup

### Twilio (Worldwide)
1. Sign up free at https://console.twilio.com
2. Get Account SID + Auth Token from dashboard
3. Buy/get a Twilio phone number (free trial number available)
4. Fill in Settings → SMS Alert Settings

### Fast2SMS (India only — cheaper for Indian numbers)
1. Register at https://www.fast2sms.com
2. Go to Dev API → API Key
3. Select Fast2SMS in Settings → SMS Provider
4. Paste your API Key

---

## 📋 Adding Devices to Monitor

1. Open **Settings** → **Monitored Devices**
2. Enter a friendly name (e.g. "Dad's Phone") and the device's IP address
3. To find a device's IP:
   - **Router admin page** (usually 192.168.1.1 or 192.168.0.1)
   - **Windows**: Run `arp -a` in Command Prompt
   - **Linux/Mac**: Run `arp -a` or `nmap -sn 192.168.1.0/24`
   - **Android/iOS**: Settings → Wi-Fi → Device info → IP Address

> **Tip**: Set a static/reserved IP for each device in your router settings
> so the IP doesn't change.

---

## 📊 SMS Template Variables

| Variable | Description |
|---|---|
| `{name}` | Device name |
| `{host}` | IP address / hostname |
| `{time}` | Event timestamp |
| `{duration}` | How long device was online (disconnect only) |

**Example**: `{name} is now online! Time: {time}`

---

## 🛠 Management Commands (Linux)

```bash
sudo systemctl status netwatch     # Check if running
sudo systemctl restart netwatch    # Restart
sudo systemctl stop netwatch       # Stop
sudo systemctl disable netwatch    # Disable auto-start
journalctl -u netwatch -f          # View live logs
```

---

## 📁 Files

```
netwatch/
├── app.py              ← Main application (Flask + monitor)
├── requirements.txt    ← Python dependencies
├── install.sh          ← Linux installer
├── install.bat         ← Windows installer
├── netwatch.db         ← SQLite database (auto-created)
└── templates/
    ├── base.html       ← Layout + sidebar
    ├── login.html      ← Login page
    ├── dashboard.html  ← Main dashboard
    └── settings.html   ← All settings
```

---

## ⚙ Configuration

All settings are stored in the dashboard. No config files to edit.

- **Check Interval**: How often to ping devices (default 30s)
- **SMS Provider**: Twilio or Fast2SMS
- **Alert Phone**: The number that receives SMS alerts
- **SMS Templates**: Customize the message content

---

## 🔒 Security Notes

- Change the default password immediately
- The dashboard is accessible on your local network (port 5000)
- For external access, use a reverse proxy (nginx/caddy) with HTTPS
- Keep your SMS API credentials safe

---

## 📝 License

MIT — Free to use and modify.
