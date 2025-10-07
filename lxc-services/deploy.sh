#!/bin/bash
# Deployment script for LXC services
# Run this after setup.sh to deploy the services
# Usage: sudo bash deploy.sh (from repository root)

set -e

echo "=== Deploying Audio Streaming Services ==="
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run as root"
    exit 1
fi

# Validate we're in the correct directory
if [ ! -f "audio-receiver/receiver.py" ] || [ ! -f "web-ui/app.py" ]; then
    echo "ERROR: This script must be run from the lxc-services repository root"
    echo "Current directory: $(pwd)"
    echo "Expected files: audio-receiver/receiver.py, web-ui/app.py"
    exit 1
fi

echo "Running from: $(pwd)"
echo

# Copy receiver files
echo "[1/4] Deploying audio receiver..."
cp audio-receiver/receiver.py /opt/audio-receiver/ # Deployment script for LXC services
# Run this after setup.sh to deploy the services

set -e

echo "=== Deploying Audio Streaming Services ==="
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root"
    exit 1
fi

# Copy receiver files
echo "[1/4] Deploying audio receiver..."
cp audio-receiver/receiver.py /opt/audio-receiver/
chmod +x /opt/audio-receiver/receiver.py
cp audio-receiver/audio-receiver.service /etc/systemd/system/

# Copy web UI files
echo "[2/4] Deploying web UI..."
cp web-ui/app.py /opt/web-ui/
chmod +x /opt/web-ui/app.py
cp -r web-ui/templates /opt/web-ui/
cp web-ui/web-ui.service /etc/systemd/system/

# Reload systemd
echo "[3/4] Reloading systemd..."
systemctl daemon-reload

# Enable and start services
echo "[4/4] Enabling and starting services..."
systemctl enable audio-receiver
systemctl enable web-ui
systemctl restart audio-receiver
systemctl restart web-ui

echo
echo "=== Deployment Complete ==="
echo

# Check service status
echo "Service Status:"
echo "---------------"
systemctl status audio-receiver --no-pager || true
echo
systemctl status web-ui --no-pager || true
echo

echo "Check logs with:"
echo "  journalctl -u audio-receiver -f"
echo "  journalctl -u web-ui -f"
echo
