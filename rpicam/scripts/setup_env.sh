#!/bin/bash

# Setup virtual environment and install dependencies
# Run this on both laptop and Raspberry Pi

echo "=== Setting up Python virtual environment ==="

# Check if we're on Raspberry Pi
if [ -f /proc/device-tree/model ] && grep -q "Raspberry Pi" /proc/device-tree/model; then
    echo "🍓 Detected Raspberry Pi"
    IS_PI=true
else
    echo "💻 Detected laptop/desktop"
    IS_PI=false
fi

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install common dependencies
echo "Installing common dependencies..."
pip install -r requirements.txt

# Pi-specific installations
if [ "$IS_PI" = true ]; then
    echo "Installing Raspberry Pi specific packages..."
    
    # Install Hailo runtime (this might need to be done manually)
    echo "⚠️  You may need to install Hailo runtime manually:"
    echo "   Follow Hailo AI HAT+ installation guide"
    
    # Install picamera2 if not already installed
    pip install picamera2
    
    # Install additional Pi-specific packages
    pip install RPi.GPIO gpiozero
fi

echo "✅ Environment setup complete!"
echo "🔧 To activate: source venv/bin/activate"

if [ "$IS_PI" = true ]; then
    echo "🎯 Next steps on Pi:"
    echo "   1. Install Hailo runtime (if not done)"
    echo "   2. Run: cd scripts && ./download_model.sh"
    echo "   3. Test: cd src && python main.py"
fi 