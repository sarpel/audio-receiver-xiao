# Audio Compression Guide

**Feature:** Automatic compression of 10-minute WAV segments to FLAC or Opus formats
**Purpose:** Save storage space with minimal quality loss

## Overview

The audio receiver now automatically compresses completed 10-minute WAV segments in the background using ffmpeg. After a segment is written to disk, the system:

1. Waits 10 seconds to ensure file is fully written
2. Compresses using FLAC (lossless) or Opus (near-transparent)
3. Deletes the original WAV file (optional)
4. Logs compression statistics

This happens in a background thread, so it doesn't block audio reception.

## Compression Formats

### FLAC (Default, Recommended)

**Format:** Free Lossless Audio Codec
**Compression:** ~50% size reduction (19.2 MB → ~9.6 MB)
**Quality:** Perfect (lossless, bit-for-bit identical to original)
**Speed:** Fast compression (~2-5 seconds per 10-minute segment)
**Best for:** Archival, highest quality, moderate space savings

**Storage Impact:**
- Hourly: ~58 MB (vs 115 MB uncompressed)
- Daily: ~1.38 GB (vs 2.76 GB uncompressed)
- Monthly: ~41.5 GB (vs 82.9 GB uncompressed)

**Configuration:**
```python
COMPRESSION_FORMAT = 'flac'
FLAC_COMPRESSION_LEVEL = 5  # 0-8, higher = better compression but slower
```

### Opus (Maximum Compression)

**Format:** Opus Interactive Audio Codec
**Compression:** ~98% size reduction (19.2 MB → ~0.5 MB at 64kbps)
**Quality:** Excellent for speech at 64kbps, transparent at 96kbps
**Speed:** Fast compression (~3-7 seconds per 10-minute segment)
**Best for:** Speech recording, maximum space savings

**Storage Impact (64 kbps):**
- Hourly: ~2.9 MB (vs 115 MB uncompressed)
- Daily: ~70 MB (vs 2.76 GB uncompressed)
- Monthly: ~2.1 GB (vs 82.9 GB uncompressed)

**Configuration:**
```python
COMPRESSION_FORMAT = 'opus'
OPUS_BITRATE = 64  # kbps, recommended: 64 for speech, 96 for music, 128 for high quality
```

**Opus Quality Guide:**
- **32 kbps:** Acceptable for speech (99% reduction)
- **64 kbps:** Excellent for speech, good for music (98% reduction) ← **Recommended for voice**
- **96 kbps:** Transparent for speech, excellent for music (97% reduction)
- **128 kbps:** Transparent for most content (96% reduction)

## Configuration Options

All settings are in `receiver.py`:

```python
# Enable/disable compression
ENABLE_COMPRESSION = True           # Set to False to disable compression

# Compression format
COMPRESSION_FORMAT = 'flac'         # Options: 'flac' or 'opus'

# Timing
COMPRESSION_DELAY = 10              # Wait 10 seconds after segment completion

# Cleanup
DELETE_ORIGINAL_WAV = True          # Delete uncompressed WAV after successful compression

# FLAC-specific
FLAC_COMPRESSION_LEVEL = 5          # 0-8 (default: 5)

# Opus-specific
OPUS_BITRATE = 64                   # kbps (recommended: 64 for speech)
```

## Requirements

### Install ffmpeg

**Debian/Ubuntu:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**RHEL/CentOS:**
```bash
sudo yum install epel-release
sudo yum install ffmpeg
```

**Verify installation:**
```bash
ffmpeg -version
```

The receiver automatically checks for ffmpeg on startup and logs a warning if not found.

## How It Works

### Trigger Logic

1. **Segment Completion:** When a 10-minute WAV segment is complete:
   - File is closed
   - Compression thread is spawned (daemon, non-blocking)
   - Next segment starts immediately

2. **Compression Delay:** Thread waits 10 seconds to ensure:
   - File is fully written to disk
   - File system has flushed all buffers
   - No race conditions with file access

3. **File Size Check:** Only compresses files ≥ 9.6 MB (≥ 5 minutes)
   - Skips partial segments from connection interruptions
   - Avoids wasting CPU on tiny files

4. **Compression:** Runs ffmpeg with optimized settings
   - FLAC: Lossless compression with level 5
   - Opus: VoIP-optimized encoding with VBR

5. **Cleanup:** If `DELETE_ORIGINAL_WAV = True`:
   - Deletes original WAV after successful compression
   - Keeps WAV if compression fails

6. **Logging:** Records compression statistics:
   - Original size
   - Compressed size
   - Reduction percentage
   - Compression time

### Threading Model

```
Main Thread                     Background Compression Thread
───────────                     ─────────────────────────────
Receive audio
Write to WAV segment
...
Segment complete! ───────────┐
Close file                   │
Start new segment            │
Continue receiving           │  Thread spawned
...                          │  Wait 10 seconds
...                          │  Check file exists
...                          │  Check file size ≥ 9.6 MB
...                          │  Run ffmpeg compression
...                          │  Log statistics
...                          │  Delete original WAV (optional)
...                          └─ Thread exits
```

**Benefits:**
- Non-blocking: Audio reception continues uninterrupted
- Parallel: Multiple segments can compress simultaneously
- Daemon threads: Auto-cleanup on program exit

## Usage Examples

### Example 1: Default FLAC Compression

```python
# Configuration in receiver.py
ENABLE_COMPRESSION = True
COMPRESSION_FORMAT = 'flac'
FLAC_COMPRESSION_LEVEL = 5
DELETE_ORIGINAL_WAV = True
```

**Log Output:**
```
2025-01-08 12:10:00 - AudioReceiver - INFO - Segment complete: /data/audio/2025-01-08/2025-01-08_1200.wav
2025-01-08 12:10:00 - AudioReceiver - INFO -   Duration: 600.0s, Size: 19.20 MB
2025-01-08 12:10:00 - AudioReceiver - INFO - Compression scheduled for /data/audio/2025-01-08/2025-01-08_1200.wav in 10 seconds
2025-01-08 12:10:10 - AudioReceiver - INFO - Compressing 2025-01-08_1200.wav to FLAC...
2025-01-08 12:10:13 - AudioReceiver - INFO - Compression complete: 2025-01-08_1200.flac
2025-01-08 12:10:13 - AudioReceiver - INFO -   Original: 19.20 MB
2025-01-08 12:10:13 - AudioReceiver - INFO -   Compressed: 9.63 MB
2025-01-08 12:10:13 - AudioReceiver - INFO -   Reduction: 49.8% (3.2s)
2025-01-08 12:10:13 - AudioReceiver - INFO - Deleted original WAV: 2025-01-08_1200.wav
```

### Example 2: Opus Maximum Compression

```python
# Configuration in receiver.py
ENABLE_COMPRESSION = True
COMPRESSION_FORMAT = 'opus'
OPUS_BITRATE = 64
DELETE_ORIGINAL_WAV = True
```

**Log Output:**
```
2025-01-08 12:10:00 - AudioReceiver - INFO - Segment complete: /data/audio/2025-01-08/2025-01-08_1200.wav
2025-01-08 12:10:00 - AudioReceiver - INFO -   Duration: 600.0s, Size: 19.20 MB
2025-01-08 12:10:00 - AudioReceiver - INFO - Compression scheduled for /data/audio/2025-01-08/2025-01-08_1200.wav in 10 seconds
2025-01-08 12:10:10 - AudioReceiver - INFO - Compressing 2025-01-08_1200.wav to Opus...
2025-01-08 12:10:15 - AudioReceiver - INFO - Compression complete: 2025-01-08_1200.opus
2025-01-08 12:10:15 - AudioReceiver - INFO -   Original: 19.20 MB
2025-01-08 12:10:15 - AudioReceiver - INFO -   Compressed: 0.47 MB
2025-01-08 12:10:15 - AudioReceiver - INFO -   Reduction: 97.6% (4.8s)
2025-01-08 12:10:15 - AudioReceiver - INFO - Deleted original WAV: 2025-01-08_1200.wav
```

### Example 3: Disabled Compression (Keep WAV)

```python
# Configuration in receiver.py
ENABLE_COMPRESSION = False
```

**Log Output:**
```
2025-01-08 12:10:00 - AudioReceiver - INFO - Segment complete: /data/audio/2025-01-08/2025-01-08_1200.wav
2025-01-08 12:10:00 - AudioReceiver - INFO -   Duration: 600.0s, Size: 19.20 MB
# No compression happens
```

### Example 4: Keep Original WAV After Compression

```python
# Configuration in receiver.py
ENABLE_COMPRESSION = True
COMPRESSION_FORMAT = 'flac'
DELETE_ORIGINAL_WAV = False  # Keep both WAV and FLAC
```

**Result:**
```
/data/audio/2025-01-08/
├── 2025-01-08_1200.wav   (19.20 MB - original)
└── 2025-01-08_1200.flac  (9.63 MB - compressed)
```

## Troubleshooting

### Problem: Compression not happening

**Check 1: Is compression enabled?**
```python
# In receiver.py
ENABLE_COMPRESSION = True  # Must be True
```

**Check 2: Is ffmpeg installed?**
```bash
ffmpeg -version
```

**Check 3: Check logs for errors**
```bash
tail -f /var/log/audio-receiver.log | grep -i compress
```

### Problem: ffmpeg not found

**Error:**
```
ERROR - ffmpeg: NOT FOUND
ERROR - Install ffmpeg: apt install ffmpeg
WARNING - Compression will fail without ffmpeg!
```

**Solution:**
```bash
sudo apt update
sudo apt install ffmpeg
# Restart receiver
sudo systemctl restart audio-receiver
```

### Problem: Compression failing

**Check logs for errors:**
```bash
journalctl -u audio-receiver -f | grep -i "compression failed"
```

**Common causes:**
1. **Disk full:** Check `df -h /data/audio`
2. **Permission denied:** Check file permissions
3. **Corrupted WAV:** File might be damaged
4. **Opus codec missing:** Install `libopus-dev`

**Debug specific file:**
```bash
# Test compression manually
cd /data/audio/2025-01-08

# FLAC test
ffmpeg -i 2025-01-08_1200.wav -compression_level 5 test.flac

# Opus test
ffmpeg -i 2025-01-08_1200.wav -c:a libopus -b:a 64k test.opus
```

### Problem: Partial segments being compressed

The system automatically skips files < 9.6 MB (< 5 minutes).

**Log message:**
```
INFO - Skipping compression of partial segment: 2025-01-08_1230.wav (2.45 MB)
```

This is normal behavior when connection is interrupted.

### Problem: Compression too slow

**FLAC:**
- Reduce compression level: `FLAC_COMPRESSION_LEVEL = 0` (fastest) to `3`
- Level 0: ~1s compression time, 55% size
- Level 5: ~3s compression time, 50% size (default)
- Level 8: ~8s compression time, 48% size

**Opus:**
- Already very fast (~3-7 seconds)
- Compression speed doesn't significantly impact quality

**System load:**
```bash
# Check CPU usage
top

# Check if compression is bottlenecked
ps aux | grep ffmpeg
```

## Web UI Integration

The web UI automatically supports all compressed formats:

**Supported Formats:**
- `.wav` - Uncompressed PCM
- `.flac` - FLAC compressed
- `.opus` - Opus compressed

**Browser Compatibility:**
- **WAV:** All browsers
- **FLAC:** Chrome, Firefox, Edge, Safari (partial)
- **Opus:** Chrome, Firefox, Edge, Safari 14+

**Playback:**
Files are automatically played with correct MIME type:
- `audio/wav` for WAV files
- `audio/flac` for FLAC files
- `audio/opus` for Opus files

**Download:**
Both compressed and uncompressed files can be downloaded via the web UI.

## Performance Impact

### CPU Usage

**FLAC Compression:**
- Duration: ~2-5 seconds per 10-minute segment
- CPU: ~20-40% of single core (brief spike)
- Impact: Negligible (runs in background thread)

**Opus Compression:**
- Duration: ~3-7 seconds per 10-minute segment
- CPU: ~30-50% of single core (brief spike)
- Impact: Negligible (runs in background thread)

**Real-time factor:** ~0.5% (3 seconds to compress 600 seconds of audio)

### Memory Usage

- **Additional memory:** ~5-10 MB per compression thread
- **Max concurrent:** Usually 1-2 threads (10-minute segments)
- **Total impact:** < 20 MB

### Disk I/O

**Read:** 19.2 MB per segment (original WAV)
**Write:** 9.6 MB (FLAC) or 0.5 MB (Opus)
**Delete:** 19.2 MB (if `DELETE_ORIGINAL_WAV = True`)

**I/O pattern:**
- Sequential read (efficient)
- Sequential write (efficient)
- Happens during inter-segment gap (minimal impact)

### Storage Savings

**Scenario:** 24/7 recording for 30 days

| Format | Size | Savings |
|--------|------|---------|
| **Uncompressed WAV** | 82.9 GB | 0% (baseline) |
| **FLAC (lossless)** | 41.5 GB | 50% (41.4 GB saved) |
| **Opus 64kbps** | 2.1 GB | 97.5% (80.8 GB saved) |
| **Opus 96kbps** | 3.2 GB | 96.1% (79.7 GB saved) |

## Quality Comparison

### FLAC vs Original WAV

**Quality:** Bit-perfect lossless
- Frequency response: Identical
- Dynamic range: Identical
- Signal-to-noise ratio: Identical
- Artifacts: None

**Result:** Indistinguishable from original (mathematically identical)

### Opus Quality Levels

**32 kbps (VoIP quality):**
- Speech: Clear, some artifacts on complex sounds
- Music: Noticeable quality loss
- Use case: Low-quality voice notes

**64 kbps (Recommended for speech):**
- Speech: Excellent quality, transparent for most voices
- Music: Good quality, some loss on complex passages
- Use case: Voice recording, podcasts, meetings

**96 kbps (Near-transparent):**
- Speech: Perfect, indistinguishable from original
- Music: Excellent quality, minimal artifacts
- Use case: High-quality voice recording, music

**128 kbps (Transparent):**
- Speech: Perfect
- Music: Transparent for most content
- Use case: Archival, critical audio

### Testing Audio Quality

**Generate test file:**
```bash
# Extract 30 seconds from original WAV
ffmpeg -i original.wav -t 30 test.wav

# Compress to different formats
ffmpeg -i test.wav -compression_level 5 test.flac
ffmpeg -i test.wav -c:a libopus -b:a 64k test_64k.opus
ffmpeg -i test.wav -c:a libopus -b:a 96k test_96k.opus

# Play and compare
mpv test.wav test.flac test_64k.opus test_96k.opus
```

**Objective quality measurement (PESQ):**
```bash
# Install pesq tool
pip install pesq

# Compare quality
python -c "
from scipy.io import wavfile
from pesq import pesq
import subprocess

# Convert Opus to WAV for comparison
subprocess.run(['ffmpeg', '-i', 'test_64k.opus', '-ar', '16000', 'test_64k_converted.wav'])

# Load files
rate_ref, ref = wavfile.read('test.wav')
rate_deg, deg = wavfile.read('test_64k_converted.wav')

# Calculate PESQ score (1.0-4.5, higher is better)
score = pesq(rate_ref, ref, deg, 'wb')
print(f'PESQ score: {score}')  # > 4.0 = excellent for 64kbps Opus on speech
"
```

## Recommendations

### For Voice/Speech Recording (Default)

```python
ENABLE_COMPRESSION = True
COMPRESSION_FORMAT = 'flac'
FLAC_COMPRESSION_LEVEL = 5
COMPRESSION_DELAY = 10
DELETE_ORIGINAL_WAV = True
```

**Why:**
- Perfect quality preservation (lossless)
- 50% storage savings
- Fast compression
- Widely compatible
- Can be converted to any format later

### For Maximum Storage Savings

```python
ENABLE_COMPRESSION = True
COMPRESSION_FORMAT = 'opus'
OPUS_BITRATE = 64
COMPRESSION_DELAY = 10
DELETE_ORIGINAL_WAV = True
```

**Why:**
- 98% storage savings
- Excellent quality for speech at 64kbps
- Very efficient codec (better than MP3/AAC for speech)
- Supported by modern browsers

### For Archival/Critical Audio

```python
ENABLE_COMPRESSION = True
COMPRESSION_FORMAT = 'flac'
FLAC_COMPRESSION_LEVEL = 8
COMPRESSION_DELAY = 10
DELETE_ORIGINAL_WAV = False  # Keep both for safety
```

**Why:**
- Lossless preservation
- Maximum FLAC compression
- Keeps both WAV and FLAC for redundancy
- Can delete WAV later after verifying FLAC integrity

### For Low-Storage/High-Volume

```python
ENABLE_COMPRESSION = True
COMPRESSION_FORMAT = 'opus'
OPUS_BITRATE = 32
COMPRESSION_DELAY = 10
DELETE_ORIGINAL_WAV = True
```

**Why:**
- 99% storage savings
- Acceptable quality for voice notes
- Extremely efficient for continuous 24/7 recording

## Advanced Configuration

### Customize Compression Delay

```python
COMPRESSION_DELAY = 5   # Faster (risky if file not fully written)
COMPRESSION_DELAY = 10  # Default (safe)
COMPRESSION_DELAY = 30  # Very conservative (for slow disks/NFS)
```

### Opus Application Modes

```python
# In compress_audio() function, modify Opus command:

# For speech (default):
'-application', 'voip'

# For music/general audio:
'-application', 'audio'

# For lowest latency:
'-application', 'lowdelay'
```

### FLAC Compression Levels

```python
FLAC_COMPRESSION_LEVEL = 0  # Fastest (~1s), larger files (~55% original)
FLAC_COMPRESSION_LEVEL = 5  # Default (~3s), balanced (~50% original)
FLAC_COMPRESSION_LEVEL = 8  # Maximum (~8s), smallest (~48% original)
```

### Environment Variables

Override configuration via environment variables:

```bash
# In systemd service file or shell
export ENABLE_COMPRESSION=True
export COMPRESSION_FORMAT=opus
export OPUS_BITRATE=96
export DELETE_ORIGINAL_WAV=False

python3 receiver.py
```

## Migration Guide

### Enabling Compression on Existing System

1. **Install ffmpeg:**
   ```bash
   sudo apt install ffmpeg
   ```

2. **Update receiver.py configuration:**
   ```python
   ENABLE_COMPRESSION = True
   COMPRESSION_FORMAT = 'flac'
   DELETE_ORIGINAL_WAV = True
   ```

3. **Restart receiver:**
   ```bash
   sudo systemctl restart audio-receiver
   ```

4. **Verify in logs:**
   ```bash
   journalctl -u audio-receiver -f
   # Should show: "Compression: ENABLED (FLAC)"
   ```

5. **Monitor first compression:**
   ```bash
   tail -f /var/log/audio-receiver.log | grep -i compress
   ```

### Compressing Existing WAV Files

**Batch compress all existing files:**

```bash
#!/bin/bash
# compress_existing.sh

DATA_DIR="/data/audio"

# FLAC compression
find "$DATA_DIR" -name "*.wav" -type f | while read wav_file; do
    flac_file="${wav_file%.wav}.flac"

    echo "Compressing: $wav_file"
    ffmpeg -i "$wav_file" -y -compression_level 5 -loglevel error "$flac_file"

    if [ $? -eq 0 ] && [ -f "$flac_file" ]; then
        original_size=$(stat -f%z "$wav_file" 2>/dev/null || stat -c%s "$wav_file")
        compressed_size=$(stat -f%z "$flac_file" 2>/dev/null || stat -c%s "$flac_file")
        reduction=$((100 - (compressed_size * 100 / original_size)))

        echo "  Original: $(($original_size / 1024 / 1024)) MB"
        echo "  Compressed: $(($compressed_size / 1024 / 1024)) MB"
        echo "  Reduction: $reduction%"

        rm "$wav_file"
        echo "  Deleted original WAV"
    else
        echo "  ERROR: Compression failed!"
    fi
done
```

**Run compression:**
```bash
chmod +x compress_existing.sh
./compress_existing.sh
```

## Monitoring

### Check Compression Status

```bash
# Real-time compression monitoring
tail -f /var/log/audio-receiver.log | grep -E "Compression|compress"

# Count compressed files
find /data/audio -name "*.flac" | wc -l
find /data/audio -name "*.opus" | wc -l

# Storage usage breakdown
du -sh /data/audio/*.wav  # Uncompressed
du -sh /data/audio/*.flac # FLAC
du -sh /data/audio/*.opus # Opus
```

### Compression Statistics

```bash
# Total storage used
du -sh /data/audio

# Average compression ratio
find /data/audio -name "*.flac" -type f -exec stat -f "%z %N" {} \; | awk '{sum+=$1; count++} END {print "Average FLAC size:", sum/count/1024/1024, "MB"}'

# Oldest uncompressed file
find /data/audio -name "*.wav" -type f -printf '%T+ %p\n' | sort | head -1
```

## Version History

**v2.1** (Current)
- Added automatic FLAC/Opus compression
- Background threading for non-blocking compression
- Configurable compression formats and settings
- Web UI support for compressed formats
- Startup ffmpeg availability check
- Comprehensive logging of compression statistics

**v2.0**
- Server-side alignment with ESP32 firmware
- 16kHz/16-bit mono audio support
- Basic WAV segment recording

## License

MIT License - See LICENSE file for details
