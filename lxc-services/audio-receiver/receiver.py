#!/usr/bin/env python3
"""
Audio Stream Receiver
Receives raw PCM audio from ESP32-S3 via TCP and saves as WAV segments.
Supports automatic compression to FLAC or Opus formats for storage efficiency.
"""

import socket
import struct
import time
import os
import sys
import subprocess
import threading
from datetime import datetime
from pathlib import Path
import logging

# Configuration - MUST match ESP32 firmware settings
# Aligned with audio-streamer-xiao firmware v2.0:
# - Sample rate: 16 kHz (reduced from 48 kHz for WiFi streaming)
# - Bits per sample: 16-bit (reduced from 24-bit)
# - TCP chunk size: 9600 samples × 2 bytes = 19200 bytes (200ms chunks)
SAMPLE_RATE = 16000      # 16 kHz (matches firmware config.h)
CHANNELS = 1             # Mono
BITS_PER_SAMPLE = 16     # 16-bit (matches firmware)
BYTES_PER_SAMPLE = 2     # 2 bytes per sample (16-bit)
SEGMENT_DURATION = 600   # 10 minutes per WAV file
SEGMENT_SIZE = SAMPLE_RATE * CHANNELS * BYTES_PER_SAMPLE * SEGMENT_DURATION
DATA_DIR = '/data/audio'
TCP_PORT = 9000
TCP_HOST = '0.0.0.0'

# TCP buffer size aligned with firmware (200ms chunks from ESP32)
TCP_CHUNK_SIZE = 19200   # 9600 samples × 2 bytes = 19200 bytes

# Compression Configuration
# Automatically compress WAV files after segment completion to save storage space
ENABLE_COMPRESSION = True           # Set to False to disable compression
COMPRESSION_FORMAT = 'flac'         # Options: 'flac' (lossless ~50% reduction) or 'opus' (lossy ~98% reduction)
COMPRESSION_DELAY = 10              # Wait 10 seconds after segment completion before compressing
DELETE_ORIGINAL_WAV = True          # Delete uncompressed WAV after successful compression

# Format-specific settings
# FLAC: Lossless compression, ~50% size reduction (19.2 MB → ~9.6 MB)
# - Best for: Archival, highest quality, moderate space savings
# - Quality: Perfect (lossless)
FLAC_COMPRESSION_LEVEL = 5          # 0-8, higher = better compression but slower (5 = default)

# Opus: Lossy compression, ~98% size reduction (19.2 MB → ~0.5 MB at 64kbps)
# - Best for: Speech, maximum space savings, near-transparent quality
# - Quality: Excellent for speech at 64kbps, transparent at 96kbps
OPUS_BITRATE = 64                   # kbps, recommended: 64 for speech, 96 for music, 128 for high quality

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/audio-receiver.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('AudioReceiver')


def write_wav_header(f, data_size):
    """Write WAV file header for PCM mono audio (16-bit or 24-bit)"""
    # RIFF header
    f.write(b'RIFF')
    f.write(struct.pack('<I', 36 + data_size))  # File size - 8
    f.write(b'WAVE')

    # fmt chunk
    f.write(b'fmt ')
    f.write(struct.pack('<I', 16))  # fmt chunk size
    f.write(struct.pack('<H', 1))   # PCM format
    f.write(struct.pack('<H', CHANNELS))  # Channels (mono = 1)
    f.write(struct.pack('<I', SAMPLE_RATE))  # Sample rate
    f.write(struct.pack('<I', SAMPLE_RATE * CHANNELS * BYTES_PER_SAMPLE))  # Byte rate
    f.write(struct.pack('<H', CHANNELS * BYTES_PER_SAMPLE))  # Block align
    f.write(struct.pack('<H', BITS_PER_SAMPLE))  # Bits per sample (16 or 24)

    # data chunk
    f.write(b'data')
    f.write(struct.pack('<I', data_size))


def start_new_segment():
    """Create new WAV file for next segment"""
    now = datetime.now()
    date_dir = now.strftime('%Y-%m-%d')
    date_path = Path(DATA_DIR) / date_dir

    # Create date directory if it doesn't exist
    date_path.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp
    filename = now.strftime('%Y-%m-%d_%H%M') + '.wav'
    filepath = date_path / filename

    logger.info(f"Starting new segment: {filepath}")

    # Open file and write WAV header
    f = open(filepath, 'wb')
    write_wav_header(f, SEGMENT_SIZE)

    return f, SEGMENT_SIZE, filepath


def compress_audio(wav_filepath):
    """
    Compress WAV file to FLAC or Opus format using ffmpeg.
    Runs in background thread after COMPRESSION_DELAY seconds.
    Deletes original WAV file after successful compression if DELETE_ORIGINAL_WAV is True.

    Args:
        wav_filepath: Path to the WAV file to compress
    """
    try:
        # Wait before compression to ensure file is fully written and closed
        logger.info(f"Compression scheduled for {wav_filepath} in {COMPRESSION_DELAY} seconds")
        time.sleep(COMPRESSION_DELAY)

        wav_path = Path(wav_filepath)

        # Check if WAV file still exists
        if not wav_path.exists():
            logger.warning(f"WAV file no longer exists: {wav_filepath}")
            return

        # Only compress complete segments (at least 5 minutes of audio)
        # 16000 Hz × 2 bytes × 300 sec = 9.6 MB minimum
        min_file_size = 9600000  # 9.6 MB
        actual_size = wav_path.stat().st_size
        if actual_size < min_file_size:
            logger.info(f"Skipping compression of partial segment: {wav_path.name} ({actual_size / 1024 / 1024:.2f} MB)")
            return

        # Determine output format and build ffmpeg command
        if COMPRESSION_FORMAT.lower() == 'flac':
            # FLAC: Lossless compression
            output_path = wav_path.with_suffix('.flac')
            cmd = [
                'ffmpeg',
                '-i', str(wav_path),
                '-y',  # Overwrite output file if exists
                '-compression_level', str(FLAC_COMPRESSION_LEVEL),
                '-loglevel', 'error',  # Only show errors
                str(output_path)
            ]
            format_name = 'FLAC'

        elif COMPRESSION_FORMAT.lower() == 'opus':
            # Opus: Lossy compression optimized for speech
            output_path = wav_path.with_suffix('.opus')
            cmd = [
                'ffmpeg',
                '-i', str(wav_path),
                '-y',
                '-c:a', 'libopus',
                '-b:a', f'{OPUS_BITRATE}k',
                '-vbr', 'on',  # Variable bitrate for better quality
                '-compression_level', '10',  # Maximum compression efficiency
                '-application', 'voip',  # Optimized for speech (alternatives: audio, lowdelay)
                '-loglevel', 'error',
                str(output_path)
            ]
            format_name = 'Opus'

        else:
            logger.error(f"Unknown compression format: {COMPRESSION_FORMAT}")
            return

        # Get original file size
        original_size = wav_path.stat().st_size

        logger.info(f"Compressing {wav_path.name} to {format_name}...")

        # Run ffmpeg compression
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        compression_time = time.time() - start_time

        if result.returncode != 0:
            logger.error(f"Compression failed: {result.stderr}")
            return

        # Check if output file was created successfully
        if not output_path.exists():
            logger.error(f"Compression output file not created: {output_path}")
            return

        # Get compressed file size
        compressed_size = output_path.stat().st_size
        reduction_percent = ((original_size - compressed_size) / original_size) * 100

        logger.info(f"Compression complete: {output_path.name}")
        logger.info(f"  Original: {original_size / 1024 / 1024:.2f} MB")
        logger.info(f"  Compressed: {compressed_size / 1024 / 1024:.2f} MB")
        logger.info(f"  Reduction: {reduction_percent:.1f}% ({compression_time:.1f}s)")

        # Delete original WAV file if configured
        if DELETE_ORIGINAL_WAV:
            try:
                wav_path.unlink()
                logger.info(f"Deleted original WAV: {wav_path.name}")
            except Exception as e:
                logger.error(f"Failed to delete original WAV: {e}")

    except subprocess.TimeoutExpired:
        logger.error(f"Compression timeout (>300s) for {wav_filepath}")
    except Exception as e:
        logger.error(f"Compression error for {wav_filepath}: {e}")


def tcp_server():
    """Main TCP server loop"""
    # Create socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Bind and listen
    sock.bind((TCP_HOST, TCP_PORT))
    sock.listen(1)

    logger.info(f"Audio receiver listening on {TCP_HOST}:{TCP_PORT}")
    logger.info(f"Saving segments to: {DATA_DIR}")
    logger.info(f"Segment duration: {SEGMENT_DURATION} seconds ({SEGMENT_DURATION // 60} minutes)")

    while True:
        try:
            # Wait for connection
            logger.info("Waiting for ESP32 connection...")
            conn, addr = sock.accept()
            logger.info(f"Connected: {addr}")

            # Set socket options for optimal streaming
            # TCP_NODELAY: Disable Nagle's algorithm for lower latency (matches ESP32 firmware)
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

            # Increase receive buffer to handle 200ms chunks efficiently
            # ESP32 sends 19200 bytes every 200ms = ~96KB/sec
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)

            conn.settimeout(30)  # 30 second timeout (matches firmware watchdog window)

            # Start first segment
            current_file, bytes_left, current_path = start_new_segment()
            segment_start_time = time.time()
            total_bytes_received = 0

            while True:
                try:
                    # Receive data (aligned with firmware 200ms chunks: 9600 samples × 2 bytes = 19200 bytes)
                    # Using TCP_CHUNK_SIZE constant for clarity and maintainability
                    data = conn.recv(TCP_CHUNK_SIZE)

                    if not data:
                        logger.warning("Connection closed by client")
                        break

                    # Write to current segment
                    current_file.write(data)
                    bytes_left -= len(data)
                    total_bytes_received += len(data)

                    # Check if segment is complete
                    if bytes_left <= 0:
                        segment_duration = time.time() - segment_start_time
                        logger.info(f"Segment complete: {current_path}")
                        logger.info(f"  Duration: {segment_duration:.1f}s, Size: {total_bytes_received / 1024 / 1024:.2f} MB")

                        current_file.close()

                        # Trigger compression in background thread if enabled
                        if ENABLE_COMPRESSION:
                            compression_thread = threading.Thread(
                                target=compress_audio,
                                args=(str(current_path),),
                                daemon=True,
                                name=f"Compress-{current_path.name}"
                            )
                            compression_thread.start()

                        # Start new segment
                        current_file, bytes_left, current_path = start_new_segment()
                        segment_start_time = time.time()
                        total_bytes_received = 0

                except socket.timeout:
                    logger.warning("Socket timeout - no data received for 30 seconds")
                    break
                except Exception as e:
                    logger.error(f"Error receiving data: {e}")
                    break

            # Clean up connection
            current_file.close()
            conn.close()
            logger.info("Connection closed")

        except KeyboardInterrupt:
            logger.info("Shutting down...")
            break
        except Exception as e:
            logger.error(f"Server error: {e}")
            time.sleep(5)  # Wait before retrying

    sock.close()


def main():
    """Main entry point"""
    logger.info("=== Audio Stream Receiver Starting ===")
    logger.info(f"Configuration: {SAMPLE_RATE} Hz, {BITS_PER_SAMPLE}-bit, {CHANNELS} channel(s)")
    logger.info(f"Segment size: {SEGMENT_SIZE / 1024 / 1024:.2f} MB ({SEGMENT_DURATION} seconds)")
    logger.info(f"Listening on: {TCP_HOST}:{TCP_PORT}")

    # Compression configuration
    if ENABLE_COMPRESSION:
        logger.info(f"Compression: ENABLED ({COMPRESSION_FORMAT.upper()})")
        if COMPRESSION_FORMAT.lower() == 'flac':
            logger.info(f"  Format: FLAC (lossless, ~50% reduction, level {FLAC_COMPRESSION_LEVEL})")
        elif COMPRESSION_FORMAT.lower() == 'opus':
            logger.info(f"  Format: Opus ({OPUS_BITRATE} kbps, ~98% reduction, VoIP optimized)")
        logger.info(f"  Delay: {COMPRESSION_DELAY}s after segment completion")
        logger.info(f"  Delete original: {'YES' if DELETE_ORIGINAL_WAV else 'NO'}")

        # Check if ffmpeg is available
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
            if result.returncode == 0:
                logger.info("  ffmpeg: Available")
            else:
                logger.error("  ffmpeg: Not working properly")
                logger.warning("  Compression will be disabled!")
        except FileNotFoundError:
            logger.error("  ffmpeg: NOT FOUND")
            logger.error("  Install ffmpeg: apt install ffmpeg")
            logger.warning("  Compression will fail without ffmpeg!")
        except Exception as e:
            logger.warning(f"  ffmpeg check failed: {e}")
    else:
        logger.info("Compression: DISABLED")

    # Check if data directory exists
    if not os.path.exists(DATA_DIR):
        logger.warning(f"Data directory {DATA_DIR} does not exist, creating...")
        os.makedirs(DATA_DIR, exist_ok=True)

    # Start TCP server
    tcp_server()


if __name__ == '__main__':
    main()
