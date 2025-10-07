#!/usr/bin/env python3
"""
Audio Archive Web UI
Simple web interface for browsing and playing archived audio segments.

Aligned with ESP32-S3 audio-streamer-xiao firmware v2.0:
- 16 kHz sample rate, 16-bit mono audio
- 10-minute WAV segments (approximately 19.2 MB per file)
- HTTP Basic Authentication for secure access
"""

from flask import Flask, render_template, send_file, abort, jsonify, request
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import check_password_hash, generate_password_hash
from pathlib import Path
from datetime import datetime, timedelta
import os
import logging

app = Flask(__name__)
auth = HTTPBasicAuth()

# Configuration aligned with firmware settings
DATA_DIR = Path('/data/audio')
PORT = 8080
HOST = '0.0.0.0'

# Audio configuration (matches ESP32 firmware)
SAMPLE_RATE = 16000      # 16 kHz
BITS_PER_SAMPLE = 16     # 16-bit
CHANNELS = 1             # Mono
SEGMENT_DURATION = 600   # 10 minutes per file

# Authentication credentials from environment variables
WEB_UI_USERNAME = os.getenv('WEB_UI_USERNAME', 'admin')
WEB_UI_PASSWORD_HASH = generate_password_hash(os.getenv('WEB_UI_PASSWORD', 'changeme'))

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('AudioWebUI')


def get_date_folders():
    """Get list of date folders sorted in descending order"""
    if not DATA_DIR.exists():
        return []

    folders = []
    for item in DATA_DIR.iterdir():
        if item.is_dir() and len(item.name) == 10:  # YYYY-MM-DD format
            try:
                datetime.strptime(item.name, '%Y-%m-%d')
                folders.append(item.name)
            except ValueError:
                continue

    return sorted(folders, reverse=True)


def get_audio_files(date_folder):
    """Get list of audio files for a specific date"""
    folder_path = DATA_DIR / date_folder
    if not folder_path.exists():
        return []

    files = []
    for item in folder_path.iterdir():
        if item.is_file() and item.suffix.lower() in ['.wav', '.flac', '.opus']:
            files.append({
                'name': item.name,
                'size': item.stat().st_size,
                'modified': datetime.fromtimestamp(item.stat().st_mtime)
            })

    return sorted(files, key=lambda x: x['name'])


def format_size(size_bytes):
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def format_duration(filename):
    """Extract and format duration from filename"""
    # All segments are 10 minutes (600 seconds) based on firmware config
    # Duration = SEGMENT_DURATION from receiver.py (16000 Hz × 2 bytes × 600s = 19.2 MB)
    minutes = SEGMENT_DURATION // 60
    return f"{minutes}:00"


@auth.verify_password
def verify_password(username, password):
    """Verify HTTP Basic Auth credentials"""
    if username == WEB_UI_USERNAME and check_password_hash(WEB_UI_PASSWORD_HASH, password):
        return username
    return None


@app.route('/')
@auth.login_required
def index():
    """Main page showing date folders"""
    folders = get_date_folders()
    return render_template('index.html', folders=folders)


@app.route('/date/<date_folder>')
@auth.login_required
def date_view(date_folder):
    """View audio files for a specific date"""
    # Validate date format
    try:
        datetime.strptime(date_folder, '%Y-%m-%d')
    except ValueError:
        abort(404)

    files = get_audio_files(date_folder)
    if not files:
        abort(404)

    # Add formatted size and duration
    for file in files:
        file['size_formatted'] = format_size(file['size'])
        file['duration'] = format_duration(file['name'])

    return render_template('date.html', date=date_folder, files=files)


@app.route('/download/<date_folder>/<filename>')
@auth.login_required
def download(date_folder, filename):
    """Download audio file"""
    file_path = DATA_DIR / date_folder / filename

    if not file_path.exists() or not file_path.is_file():
        abort(404)

    # Security check - ensure file is within DATA_DIR
    try:
        file_path.resolve().relative_to(DATA_DIR.resolve())
    except ValueError:
        abort(403)

    return send_file(file_path, as_attachment=True)


@app.route('/stream/<date_folder>/<filename>')
@auth.login_required
def stream(date_folder, filename):
    """Stream audio file for in-browser playback"""
    file_path = DATA_DIR / date_folder / filename

    if not file_path.exists() or not file_path.is_file():
        abort(404)

    # Security check
    try:
        file_path.resolve().relative_to(DATA_DIR.resolve())
    except ValueError:
        abort(403)

    # Determine MIME type based on file extension
    mime_types = {
        '.wav': 'audio/wav',
        '.flac': 'audio/flac',
        '.opus': 'audio/opus'
    }
    mimetype = mime_types.get(file_path.suffix.lower(), 'audio/wav')

    return send_file(file_path, mimetype=mimetype)


@app.route('/api/stats')
@auth.login_required
def stats():
    """API endpoint for statistics"""
    folders = get_date_folders()
    total_files = 0
    total_size = 0

    for folder in folders:
        files = get_audio_files(folder)
        total_files += len(files)
        total_size += sum(f['size'] for f in files)

    return jsonify({
        'total_dates': len(folders),
        'total_files': total_files,
        'total_size': total_size,
        'total_size_formatted': format_size(total_size)
    })


@app.route('/api/latest')
@auth.login_required
def latest():
    """API endpoint for latest recordings"""
    folders = get_date_folders()
    if not folders:
        return jsonify([])

    latest_date = folders[0]
    files = get_audio_files(latest_date)

    return jsonify({
        'date': latest_date,
        'files': [{'name': f['name'], 'size': f['size']} for f in files[-5:]]
    })


@app.template_filter('datetime')
def format_datetime(value):
    """Format datetime for templates"""
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    return value


if __name__ == '__main__':
    logger.info("=== Audio Archive Web UI Starting ===")
    logger.info(f"Data directory: {DATA_DIR}")
    logger.info(f"Listening on http://{HOST}:{PORT}")
    logger.info(f"Audio format: {SAMPLE_RATE} Hz, {BITS_PER_SAMPLE}-bit, {CHANNELS} channel (mono)")
    logger.info(f"Segment duration: {SEGMENT_DURATION // 60} minutes per file")
    logger.info(f"Authentication: enabled (user: {WEB_UI_USERNAME})")
    logger.info("Set WEB_UI_USERNAME and WEB_UI_PASSWORD environment variables to configure credentials")

    # Ensure data directory exists
    if not DATA_DIR.exists():
        logger.warning(f"Data directory {DATA_DIR} does not exist!")

    # Security warning if using default credentials
    if os.getenv('WEB_UI_PASSWORD') is None:
        logger.warning("WARNING: Using default password 'changeme' - set WEB_UI_PASSWORD environment variable!")

    app.run(host=HOST, port=PORT, debug=False, threaded=True)
