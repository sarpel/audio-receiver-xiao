#!/bin/bash
# Cleanup script for old audio files
# Add to cron: 0 2 * * * /opt/scripts/cleanup-old-files.sh

set -e

DATA_DIR="/data/audio"
RETENTION_DAYS=14  # Keep files for 14 days
LOG_FILE="/var/log/audio-cleanup.log"

echo "$(date): Starting cleanup of files older than ${RETENTION_DAYS} days" >> "$LOG_FILE"

# Find and delete old directories
find "$DATA_DIR" -maxdepth 1 -type d -name "20*" -mtime +${RETENTION_DAYS} | while read -r dir; do
    echo "$(date): Deleting old directory: $dir" >> "$LOG_FILE"
    rm -rf "$dir"
done

# Log disk usage
df -h "$DATA_DIR" >> "$LOG_FILE"

echo "$(date): Cleanup complete" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
