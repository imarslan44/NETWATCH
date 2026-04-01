#!/bin/bash
# ─────────────────────────────────────────────────────────────────
#  NetWatch — Linux Install Script
#  Installs dependencies and sets up as a systemd service
# ─────────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_FILE="$SCRIPT_DIR/app.py"
SERVICE_NAME="netwatch"
PYTHON="python3"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║         NetWatch Linux Installer         ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Check Python ──
if ! command -v python3 &>/dev/null; then
  echo "❌ Python 3 not found. Install it with: sudo apt install python3 python3-pip"
  exit 1
fi

PYVER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✅ Python $PYVER found"

# ── Install Python packages ──
echo ""
echo "📦 Installing Python packages..."
$PYTHON -m pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
echo "✅ Packages installed"

# ── Quick run (no service) option ──
if [[ "$1" == "--run" ]]; then
  echo ""
  echo "🚀 Starting NetWatch..."
  echo "   Open http://localhost:5000 in your browser"
  echo "   Default login: admin / netwatch123"
  echo "   Press Ctrl+C to stop"
  echo ""
  $PYTHON "$APP_FILE"
  exit 0
fi

# ── Install as systemd service ──
echo ""
echo "⚙  Installing as systemd service (requires sudo)..."

PYTHON_PATH=$(which $PYTHON)
USERNAME=$(whoami)

SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=NetWatch Device Internet Monitor
After=network.target

[Service]
Type=simple
User=${USERNAME}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${PYTHON_PATH} ${APP_FILE}
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl start $SERVICE_NAME

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║          ✅  Install Complete!           ║"
echo "╠══════════════════════════════════════════╣"
echo "║  Dashboard: http://localhost:5000        ║"
echo "║  Username:  admin                        ║"
echo "║  Password:  netwatch123                  ║"
echo "║                                          ║"
echo "║  Useful commands:                        ║"
echo "║  sudo systemctl status netwatch          ║"
echo "║  sudo systemctl restart netwatch         ║"
echo "║  sudo systemctl stop netwatch            ║"
echo "║  journalctl -u netwatch -f               ║"
echo "╚══════════════════════════════════════════╝"
echo ""
