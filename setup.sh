#!/bin/bash
# LXC Container Setup Script for Audio Streaming System
# Run this script inside the Debian 12 LXC container
# Usage: sudo bash setup.sh

set -e

echo "=== Audio Streaming LXC Container Setup ==="
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run as root"
    exit 1
fi

# Update system
echo "[1/7] Updating system packages..."
apt update
apt upgrade -y

# Install required packages
echo "[2/7] Installing required packages..."
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    ntp \
    tzdata \
    logrotate \
    curl \
    htop \
    vim \
    git

# Install Python dependencies
echo "[3/7] Installing Python dependencies..."
pip3 install flask>=2.3.0  Flask-HTTPAuth>=4.8.0 Werkzeug>=2.3.0 --break-system-packages

# Create directories
echo "[4/7] Creating directories..."
mkdir -p /opt/audio-receiver
mkdir -p /opt/web-ui/templates
mkdir -p /data/audio
mkdir -p /var/log

# Set permissions
echo "[5/7] Setting permissions..."
chmod 755 /opt/audio-receiver
chmod 755 /opt/web-ui
chmod 755 /data/audio

# Copy service files (assuming they're in current directory)
echo "[6/7] Setting up systemd services..."

# Note: In actual deployment, copy your service files here
# cp audio-receiver.service /etc/systemd/system/
# cp web-ui.service /etc/systemd/system/

# Setup logrotate
echo "[7/7] Setting up log rotation..."
cat > /etc/logrotate.d/audio-receiver << 'EOF'
/var/log/audio-receiver.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
}
EOF

echo
echo "=== Setup Complete ==="
echo
echo "Next steps:"
echo "1. Clone or copy the lxc-services repository to the container"
echo "2. cd to the repository root directory"
echo "3. Run: sudo bash deploy.sh"
echo ""
echo "The deploy.sh script will:"
echo "  - Copy receiver.py to /opt/audio-receiver/"
echo "  - Copy web UI files to /opt/web-ui/"
echo "  - Copy systemd service files to /etc/systemd/system/"
echo "  - Enable and start both services"
echo
echo "Data will be stored in: /data/audio"
echo "TCP receiver listening on: port 9000"
echo "Web UI accessible on: http://[container-ip]:8080"
echo
echo "Web UI accessible on: http://[container-ip]:8080"
echo
