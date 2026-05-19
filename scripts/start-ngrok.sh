#!/usr/bin/env bash
set -uo pipefail

# ---- Config ----
NGROK_TOKEN="3B8Up7sSRkgVXt8GXHiuSPrJdJR_5GyFY72y7gkW6Gm2geBfU"
DOMAIN="sniffish-plasmodial-gabriel.ngrok-free.dev"
PORT=8080

PYTHON="${PYTHON:-$(command -v python3)}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="/tmp/firewall-web.log"
SERVER_PATH="$PROJECT_DIR/web/server.py"

# ---- Cleanup on exit ----
cleanup() {
    echo ""
    echo "[cleanup] Stopping web server..."
    sudo pkill -f "$SERVER_PATH" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ---- Banner ----
echo "================================================================"
echo "  Public URL: https://$DOMAIN"
echo "================================================================"
echo ""

# ---- 1. Start web server in background ----
echo "[1/3] Starting web server (sudo needed for namespaces)..."
sudo "$PYTHON" "$SERVER_PATH" > "$LOG" 2>&1 &
sleep 2

if ! pgrep -f "$SERVER_PATH" > /dev/null; then
    echo "ERROR: web server failed to start. Last log lines:"
    tail -20 "$LOG"
    exit 1
fi
echo "      OK — web server running (log: $LOG)"

# ---- 2. Configure ngrok token ----
echo "[2/3] Configuring ngrok token..."
/usr/local/bin/ngrok config add-authtoken "$NGROK_TOKEN" > /dev/null
echo "      OK"

# ---- 3. Start ngrok tunnel ----
echo "[3/3] Starting ngrok tunnel on port $PORT..."
echo ""
echo "  >>>  https://$DOMAIN  <<<"
echo ""
/usr/local/bin/ngrok http --domain="$DOMAIN" "$PORT"
