# Welding Video Segmentation

Real-time video segmentation for welding workpieces using Raspberry Pi + Hailo AI HAT+.

## Development Workflow

### 1. Laptop Setup (Development)
```bash
# Clone and setup
git clone <your-repo-url>
cd rpicam
./scripts/setup_env.sh
source venv/bin/activate
```

### 2. Sync to Raspberry Pi
```bash
# Make sync script executable
chmod +x scripts/sync_to_pi.sh

# Sync code to Pi (adjust IP/username as needed)
./scripts/sync_to_pi.sh pi@raspberrypi.local
```

### 3. Pi Setup (First Time)
```bash
# SSH into Pi
ssh pi@raspberrypi.local

# Setup environment on Pi
cd rpicam
./scripts/setup_env.sh
source venv/bin/activate

# Download model
cd scripts && ./download_model.sh

# Install Hailo runtime (follow official guide)
# This step varies depending on your Hailo installation
```

### 4. Development Cycle
1. **Develop on laptop** - Edit code in `rpicam/` directory
2. **Commit changes** - `git add . && git commit -m "description"`
3. **Sync to Pi** - `./scripts/sync_to_pi.sh pi@raspberrypi.local`
4. **Test on Pi** - SSH in and run: `cd rpicam && source venv/bin/activate && python src/main.py`
5. **Push to GitHub** - `git push origin main`

## Project Structure

## Current Status
- [x] Basic project structure
- [x] Development workflow setup
- [x] Virtual environment management
- [ ] Hailo inference wrapper
- [ ] Video capture pipeline
- [ ] Boundary extraction
- [ ] Real-time visualization 