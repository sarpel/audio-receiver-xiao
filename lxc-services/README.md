# LXC Services - Audio Receiver & Web UI

Server-side components for ESP32-S3 audio streaming system.

**Aligned with**: `audio-streamer-xiao` firmware v2.0

## Quick Links

- [Architecture](#architecture) | [Compression](#compression-features) | [Installation](#installation) | [Configuration](#configuration)
- [Services](#services) | [Environment Variables](#environment-variables) | [Monitoring](#monitoring)
- **[📚 Compression Guide](COMPRESSION_GUIDE.md)** - Detailed compression documentation

## Architecture

### System Overview

```
ESP32-S3 (XIAO)                    LXC Container / Server
┌──────────────────┐               ┌──────────────────────────────┐
│ INMP441 Mic      │               │                              │
│   ↓ I2S          │               │  ┌────────────────────┐      │
│ 16kHz/16-bit     │   WiFi/TCP    │  │ receiver.py        │      │
│ Mono Audio       │───────────────┼─→│ TCP Server :9000   │      │
│                  │   Port 9000   │  │ Saves WAV segments │      │
│ Ring Buffer      │               │  └─────────┬──────────┘      │
│ (96 KB SRAM)     │               │            ↓                 │
│                  │               │  /data/audio/                │
│ TCP Chunks:      │               │    └─ 2025-01-08/            │
│ 9600 samples     │               │       ├─ 2025-01-08_1200.wav │
│ × 2 bytes        │               │       └─ 2025-01-08_1210.wav │
│ = 19200 bytes    │               │            ↑                 │
│ every 200ms      │               │  ┌─────────┴──────────┐      │
└──────────────────┘               │  │ app.py             │      │
                                   │  │ Web UI :8080       │      │
                                   │  │ Browse & Play      │      │
                                   │  │ HTTP Basic Auth    │      │
                                   │  └────────────────────┘      │
                                   └──────────────────────────────┘
```

### Audio Format Alignment

**ESP32-S3 Firmware Configuration** (`config.h`):

```cpp
#define SAMPLE_RATE 16000        // 16 kHz
#define BITS_PER_SAMPLE 16       // 16-bit
#define CHANNELS 1               // Mono
#define BYTES_PER_SAMPLE 2       // 2 bytes per sample

// TCP streaming: 9600 samples every 200ms
const size_t send_samples = 9600;
// Network bandwidth: 256 kbps (16000 Hz × 16 bits × 1 channel)
```

**Server Configuration** (aligned):

```python
# receiver.py & app.py
SAMPLE_RATE = 16000          # 16 kHz (matches firmware)
BITS_PER_SAMPLE = 16         # 16-bit (matches firmware)
CHANNELS = 1                 # Mono (matches firmware)
BYTES_PER_SAMPLE = 2         # 2 bytes (matches firmware)
TCP_CHUNK_SIZE = 19200       # 9600 samples × 2 bytes (matches firmware)
SEGMENT_DURATION = 600       # 10 minutes per WAV file
```

### Performance Characteristics

**Network:**

- Raw bandwidth: 256 kbps (16000 Hz × 16 bits)
- TCP overhead: ~280 kbps actual
- Chunk rate: 5 chunks/second (200ms intervals)
- Bytes per second: 32000 bytes/sec
- Latency: 200-500ms (buffering + network)

**Storage:**

- File size: ~19.2 MB per 10-minute segment
- Hourly: ~115 MB
- Daily: ~2.76 GB
- Monthly: ~82.9 GB

**Memory:**

- ESP32: 96 KB ring buffer (internal SRAM)
- Server: 64 KB TCP receive buffer

## Compression Features

**NEW:** Automatic audio compression to save storage space with minimal quality loss!

### Overview

The receiver now automatically compresses completed 10-minute WAV segments using ffmpeg. After a segment is written, the system:

1. Waits 10 seconds to ensure file is fully written
2. Compresses in background thread (non-blocking)
3. Deletes original WAV (optional)
4. Logs compression statistics

### Supported Formats

**FLAC (Default - Recommended):**
- **Type:** Lossless compression
- **Reduction:** ~50% (19.2 MB → ~9.6 MB)
- **Quality:** Perfect (bit-for-bit identical)
- **Speed:** ~3 seconds per 10-minute segment
- **Storage:** ~41.5 GB/month (vs 82.9 GB uncompressed)

**Opus (Maximum Compression):**
- **Type:** Lossy compression (VoIP optimized)
- **Reduction:** ~98% at 64kbps (19.2 MB → ~0.5 MB)
- **Quality:** Excellent for speech, transparent at 96kbps
- **Speed:** ~5 seconds per 10-minute segment
- **Storage:** ~2.1 GB/month (vs 82.9 GB uncompressed)

### Quick Start

**1. Install ffmpeg:**
```bash
sudo apt install ffmpeg
```

**2. Configuration (receiver.py):**
```python
ENABLE_COMPRESSION = True           # Enable/disable
COMPRESSION_FORMAT = 'flac'         # 'flac' or 'opus'
COMPRESSION_DELAY = 10              # Wait 10s after segment
DELETE_ORIGINAL_WAV = True          # Remove WAV after compression
```

**3. Format-specific settings:**
```python
# FLAC (lossless)
FLAC_COMPRESSION_LEVEL = 5          # 0-8 (default: 5)

# Opus (lossy)
OPUS_BITRATE = 64                   # kbps (64 for speech, 96 for music)
```

**For complete documentation, see [COMPRESSION_GUIDE.md](COMPRESSION_GUIDE.md)**

## Services

### 1. Audio Receiver (`receiver.py`)

TCP server that receives raw audio from ESP32 and saves as WAV segments.

**Features:**

- TCP server on port 9000
- Receives 16-bit PCM audio at 16 kHz
- Saves 10-minute WAV segments
- Organized by date (YYYY-MM-DD folders)
- Automatic reconnection handling
- Logging to `/var/log/audio-receiver.log`

**File Organization:**

```
/data/audio/
├── 2025-01-08/
│   ├── 2025-01-08_1200.wav  (10 min, ~19.2 MB)
│   ├── 2025-01-08_1210.wav
│   └── 2025-01-08_1220.wav
└── 2025-01-09/
    ├── 2025-01-09_0800.wav
    └── ...
```

**WAV Format:**

- PCM uncompressed
- 16-bit samples (little-endian)
- 16000 Hz sample rate
- Mono (1 channel)
- Standard WAV header with data chunk

### 2. Web UI (`app.py`)

Flask web interface for browsing and playing archived audio.

**Features:**

- Browse recordings by date
- In-browser audio playback
- Download WAV files
- Statistics API
- HTTP Basic Authentication
- Responsive design

**Endpoints:**

- `GET /` - Main page (date list)
- `GET /date/<YYYY-MM-DD>` - Files for specific date
- `GET /stream/<date>/<file>` - Stream audio for playback
- `GET /download/<date>/<file>` - Download WAV file
- `GET /api/stats` - System statistics
- `GET /api/latest` - Latest recordings

**Security:**

- HTTP Basic Authentication on all endpoints
- Path traversal protection
- File access validation
- Environment variable credentials

## Installation

### Quick Start (Recommended - LXC Container)

```bash
# 1. Clone the repository
git clone https://github.com/sarpel/audio-receiver-xiao.git
cd audio-receiver-xiao

# 2. Run setup script (installs dependencies and creates directories)
sudo bash setup.sh

# 3. Configure credentials (IMPORTANT - change default password!)
export WEB_UI_USERNAME="admin"
export WEB_UI_PASSWORD="your-secure-password-here"

# 4. Deploy services (copies files and starts systemd services)
sudo bash deploy.sh

# 5. Verify services are running
sudo systemctl status audio-receiver
sudo systemctl status web-ui
```

### Option 1: Direct Python (for testing)

```bash
# Clone repository
git clone https://github.com/sarpel/audio-receiver-xiao.git
cd audio-receiver-xiao

# Install dependencies
pip install -r audio-receiver/requirements.txt
pip install -r web-ui/requirements.txt

# Set environment variables
export WEB_UI_USERNAME="admin"
export WEB_UI_PASSWORD="your-secure-password"

# Create data directory
mkdir -p /data/audio

# Run receiver (terminal 1)
cd audio-receiver
python3 receiver.py

# Run web UI (terminal 2)
cd web-ui
python3 app.py
```

### Option 2: Systemd Services (production)

```bash
# Clone repository
git clone https://github.com/sarpel/audio-receiver-xiao.git
cd audio-receiver-xiao

# Run setup script (installs dependencies)
sudo bash setup.sh

# Set environment variables before deploying
export WEB_UI_USERNAME="admin"
export WEB_UI_PASSWORD="your-secure-password-here"

# Deploy services (uses the automated deploy.sh script)
sudo bash deploy.sh

# Check status
sudo systemctl status audio-receiver
sudo systemctl status web-ui
```

### Option 3: LXC Container (recommended for production)

```bash
# On host: Create LXC container
lxc-create -t download -n audio-server -- -d debian -r bookworm -a amd64

# Start container
lxc-start -n audio-server

# Attach to container
lxc-attach -n audio-server

# Inside container: Clone repository
apt update && apt install -y git
git clone https://github.com/sarpel/audio-receiver-xiao.git
cd audio-receiver-xiao

# Run setup script
bash setup.sh

# Set credentials and deploy
export WEB_UI_USERNAME="admin"
export WEB_UI_PASSWORD="your-secure-password-here"
bash deploy.sh

# Exit container
exit

# On host: Check container IP
lxc-ls --fancy

# Access web UI at: http://[container-ip]:8080
```

## Configuration

### Environment Variables

**Required for Web UI:**

```bash
# Authentication credentials (REQUIRED for security)
export WEB_UI_USERNAME="admin"                    # Default: admin
export WEB_UI_PASSWORD="your-secure-password"     # Default: changeme (CHANGE THIS!)
```

**Optional for ESP32 Firmware** (build-time):

```bash
# WiFi credentials (optional, can be set in config.h instead)
export WIFI_SSID="YourNetworkName"
export WIFI_PASSWORD="YourNetworkPassword"
```

### Audio Receiver Configuration

Edit `audio-receiver/receiver.py`:

```python
SAMPLE_RATE = 16000          # Must match ESP32 firmware
BITS_PER_SAMPLE = 16         # Must match ESP32 firmware
CHANNELS = 1                 # Mono
SEGMENT_DURATION = 600       # Seconds per file (10 minutes)
DATA_DIR = '/data/audio'     # Storage location
TCP_PORT = 9000              # Server port
TCP_HOST = '0.0.0.0'         # Listen on all interfaces
```

### Web UI Configuration

Edit `web-ui/app.py`:

```python
DATA_DIR = Path('/data/audio')   # Must match receiver
PORT = 8080                      # Web UI port
HOST = '0.0.0.0'                 # Listen on all interfaces
```

### Firewall Configuration

```bash
# Allow TCP connections
sudo ufw allow 9000/tcp  comment "ESP32 audio streaming"
sudo ufw allow 8080/tcp  comment "Audio web UI"
```

## Monitoring

### Check Service Status

```bash
# Systemd services
sudo systemctl status audio-receiver
sudo systemctl status audio-web-ui

# View logs
sudo journalctl -u audio-receiver -f
sudo journalctl -u audio-web-ui -f

# Check log files
tail -f /var/log/audio-receiver.log
```

### Test Receiver Connection

```bash
# Check if receiver is listening
netstat -tuln | grep 9000

# Test from ESP32 IP (should see audio data streaming)
nc 192.168.1.50 9000 | xxd | head -100

# Verify WAV files are being created
ls -lh /data/audio/$(date +%Y-%m-%d)/
```

### Monitor ESP32 Connection

```bash
# View receiver logs (shows ESP32 IP and connection status)
tail -f /var/log/audio-receiver.log

# Example output:
# 2025-01-08 12:00:00 - AudioReceiver - INFO - Connected: ('192.168.1.27', 54321)
# 2025-01-08 12:10:00 - AudioReceiver - INFO - Segment complete: /data/audio/2025-01-08/2025-01-08_1200.wav
```

### Storage Monitoring

```bash
# Check disk usage
df -h /data/audio

# Count recordings
find /data/audio -name "*.wav" | wc -l

# Total storage used
du -sh /data/audio

# Oldest recording
find /data/audio -name "*.wav" -type f -printf '%T+ %p\n' | sort | head -1

# Latest recording
find /data/audio -name "*.wav" -type f -printf '%T+ %p\n' | sort | tail -1
```

### Performance Monitoring

```bash
# Network throughput (should show ~280 kbps when streaming)
iftop -i eth0

# CPU usage
top -p $(pgrep -f receiver.py)

# Memory usage
ps aux | grep -E "receiver.py|app.py"

# TCP connections
netstat -anp | grep :9000
```

### API Statistics

```bash
# Get system statistics
curl -u admin:password http://localhost:8080/api/stats

# Example response:
{
  "total_dates": 5,
  "total_files": 144,
  "total_size": 2764800000,
  "total_size_formatted": "2.6 GB"
}

# Get latest recordings
curl -u admin:password http://localhost:8080/api/latest
```

## Troubleshooting

### Receiver Issues

**Problem: Receiver won't start**

```bash
# Check if port is already in use
sudo netstat -tuln | grep 9000

# Kill existing process
sudo pkill -f receiver.py

# Restart service
sudo systemctl restart audio-receiver
```

**Problem: ESP32 can't connect**

```bash
# Verify server IP is reachable from ESP32
ping 192.168.1.50

# Check firewall
sudo ufw status

# Test manual connection
nc -l 9000
```

**Problem: No WAV files created**

```bash
# Check data directory permissions
ls -ld /data/audio
sudo chmod 755 /data/audio

# Check disk space
df -h /data

# Verify receiver is receiving data
sudo tcpdump -i eth0 port 9000 -X
```

**Problem: Corrupted audio / wrong format**

```bash
# Verify receiver configuration matches ESP32
grep SAMPLE_RATE audio-receiver/receiver.py  # Should be 16000
grep BITS_PER_SAMPLE audio-receiver/receiver.py  # Should be 16

# Test WAV file
ffmpeg -i /data/audio/2025-01-08/2025-01-08_1200.wav
# Should show: 16000 Hz, mono, s16le (16-bit PCM)
```

### Web UI Issues

**Problem: Can't access web UI**

```bash
# Check if service is running
sudo systemctl status audio-web-ui

# Check port
netstat -tuln | grep 8080

# Test local access
curl http://localhost:8080
```

**Problem: Authentication fails**

```bash
# Check environment variables
echo $WEB_UI_USERNAME
echo $WEB_UI_PASSWORD

# Verify credentials in service file
sudo cat /etc/default/audio-services

# Restart service after changing credentials
sudo systemctl restart audio-web-ui
```

**Problem: Files don't show in UI**

```bash
# Check DATA_DIR matches receiver
grep DATA_DIR web-ui/app.py
grep DATA_DIR audio-receiver/receiver.py

# Verify permissions
ls -l /data/audio/2025-01-08/

# Check logs
sudo journalctl -u audio-web-ui -f
```

### Network Issues

**Problem: Frequent disconnections**

```bash
# Check WiFi signal strength on ESP32 (serial monitor)
# Should be > -70 dBm

# Test network stability
ping -c 100 192.168.1.27  # ESP32 IP

# Check for packet loss
sudo tcpdump -i eth0 port 9000 -c 1000 | grep "length 19200"

# Monitor TCP connections
watch -n1 'netstat -ant | grep 9000'
```

**Problem: Buffer overflows on ESP32**

```bash
# Check ESP32 serial monitor logs for overflow warnings
# Increase ring buffer size in firmware config.h if needed

# Reduce network latency
ping 192.168.1.27  # Should be < 10ms

# Check server TCP receive buffer
ss -tmi | grep :9000
```

## Maintenance

### Automatic Cleanup (optional)

```bash
# Create cleanup script
cat > /usr/local/bin/cleanup-old-audio.sh << 'EOF'
#!/bin/bash
# Delete audio recordings older than 30 days
find /data/audio -name "*.wav" -mtime +30 -delete
find /data/audio -type d -empty -delete
EOF

chmod +x /usr/local/bin/cleanup-old-audio.sh

# Add to crontab (runs daily at 3 AM)
(crontab -l 2>/dev/null; echo "0 3 * * * /usr/local/bin/cleanup-old-audio.sh") | crontab -
```

### Backup Strategy

```bash
# Backup to remote server
rsync -avz --delete /data/audio/ backup-server:/backup/audio/

# Backup to external drive
rsync -avz /data/audio/ /mnt/external/audio-backup/

# Compress old recordings
find /data/audio -name "*.wav" -mtime +7 -exec gzip {} \;
```

### Log Rotation

```bash
# Configure logrotate
sudo cat > /etc/logrotate.d/audio-receiver << EOF
/var/log/audio-receiver.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
}
EOF
```

## Systemd Service Files

### `/etc/systemd/system/audio-receiver.service`

```ini
[Unit]
Description=ESP32 Audio Stream Receiver
After=network.target

[Service]
Type=simple
User=audio
Group=audio
WorkingDirectory=/opt/lxc-services/audio-receiver
EnvironmentFile=/etc/default/audio-services
ExecStart=/usr/bin/python3 /opt/lxc-services/audio-receiver/receiver.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### `/etc/systemd/system/audio-web-ui.service`

```ini
[Unit]
Description=Audio Archive Web UI
After=network.target

[Service]
Type=simple
User=audio
Group=audio
WorkingDirectory=/opt/lxc-services/web-ui
EnvironmentFile=/etc/default/audio-services
ExecStart=/usr/bin/python3 /opt/lxc-services/web-ui/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### `/etc/default/audio-services`

```bash
# Audio Services Configuration
# Environment variables for audio-receiver and audio-web-ui

# Web UI Authentication (REQUIRED - change default password!)
WEB_UI_USERNAME=admin
WEB_UI_PASSWORD=changeme

# Uncomment to override default paths
# DATA_DIR=/data/audio
# TCP_PORT=9000
# WEB_UI_PORT=8080
```

## Environment Variable Reference

### ESP32 Firmware (build-time, optional)

| Variable        | Description       | Default               | Required |
| --------------- | ----------------- | --------------------- | -------- |
| `WIFI_SSID`     | WiFi network name | (defined in config.h) | No       |
| `WIFI_PASSWORD` | WiFi password     | (defined in config.h) | No       |

**Usage:**

```bash
# Option 1: Build with environment variables
export WIFI_SSID="MyNetwork"
export WIFI_PASSWORD="MyPassword"
idf.py build

# Option 2: Define in src/config.h (default)
#define WIFI_SSID "MyNetwork"
#define WIFI_PASSWORD "MyPassword"
```

### Server Services (runtime, required for web UI)

| Variable          | Description     | Default    | Required               |
| ----------------- | --------------- | ---------- | ---------------------- |
| `WEB_UI_USERNAME` | Web UI username | `admin`    | Yes (for security)     |
| `WEB_UI_PASSWORD` | Web UI password | `changeme` | **Yes** (MUST change!) |

**Usage:**

```bash
# Option 1: Export in shell
export WEB_UI_USERNAME="admin"
export WEB_UI_PASSWORD="secure-password-here"
python3 app.py

# Option 2: Systemd environment file
# /etc/default/audio-services
WEB_UI_USERNAME=admin
WEB_UI_PASSWORD=secure-password-here

# Option 3: Inline
WEB_UI_USERNAME=admin WEB_UI_PASSWORD=secure python3 app.py
```

**Security Note:** Always change the default password in production!

## Performance Optimization

### Server TCP Settings

```bash
# Increase TCP buffer sizes for high-throughput streaming
sudo sysctl -w net.core.rmem_max=16777216
sudo sysctl -w net.core.wmem_max=16777216
sudo sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"
sudo sysctl -w net.ipv4.tcp_wmem="4096 65536 16777216"

# Make persistent
sudo tee -a /etc/sysctl.conf << EOF
net.core.rmem_max=16777216
net.core.wmem_max=16777216
net.ipv4.tcp_rmem=4096 87380 16777216
net.ipv4.tcp_wmem=4096 65536 16777216
EOF
```

### Flask Production Deployment

For production, use a WSGI server instead of Flask's development server:

```bash
# Install gunicorn
pip install gunicorn

# Run with gunicorn (better performance)
cd web-ui
gunicorn -w 4 -b 0.0.0.0:8080 --timeout 120 app:app
```

### Storage Optimization

```bash
# Use tmpfs for temporary files (faster writes)
sudo mount -t tmpfs -o size=512M tmpfs /tmp/audio-temp

# Compress old recordings (saves ~50% space)
find /data/audio -name "*.wav" -mtime +7 -exec gzip {} \;
```

## License

MIT License - See LICENSE file for details

## Version History

**v2.0** (Current)

- Aligned with ESP32-S3 firmware v2.0
- Changed from 24-bit/48kHz to 16-bit/16kHz
- Updated TCP chunk size to 19200 bytes (200ms at 16kHz)
- Added comprehensive configuration documentation
- Added environment variable support for credentials
- Optimized TCP buffer sizes
- Added threading support to Flask

**v1.0**

- Initial release
- 24-bit/48kHz audio support
- Basic TCP receiver and web UI
