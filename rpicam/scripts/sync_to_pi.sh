#!/bin/bash

# Sync code from laptop to Raspberry Pi
# Usage: ./sync_to_pi.sh [pi_username@pi_ip] [destination_path]

PI_USER_HOST=${1:-pi@raspberrypi.local}
PI_PROJECT_PATH=${2:-/home/pi/rpicam}  # Default or custom path
LOCAL_PROJECT_PATH="$(dirname "$(dirname "$(realpath "$0")")")"

echo "=== Syncing code to Raspberry Pi ==="
echo "From: $LOCAL_PROJECT_PATH"
echo "To: $PI_USER_HOST:$PI_PROJECT_PATH"

# Create destination directory if it doesn't exist
ssh "$PI_USER_HOST" "mkdir -p $PI_PROJECT_PATH"

# Sync files
rsync -avz --progress \
  --exclude='.git/' \
  --exclude='venv/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='models/*.hef' \
  --exclude='output/' \
  "$LOCAL_PROJECT_PATH/" "$PI_USER_HOST:$PI_PROJECT_PATH/"

if [ $? -eq 0 ]; then
    echo "✅ Sync completed successfully!"
    echo "🚀 Ready to run on Pi: ssh $PI_USER_HOST 'cd $(basename $PI_PROJECT_PATH) && source venv/bin/activate && python src/main.py'"
else
    echo "❌ Sync failed"
    exit 1
fi 