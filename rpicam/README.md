# Welding Video Segmentation

Real-time video segmentation for welding workpieces using Raspberry Pi + Hailo AI HAT+.

## Setup

### On Raspberry Pi:
1. Install dependencies: `pip install -r requirements.txt`
2. Download model: `cd scripts && ./download_model.sh`
3. Run: `cd src && python main.py`

### Development Workflow:
1. Develop on laptop in `rpicam/` directory
2. Sync code to Pi using rsync
3. Test and run on Pi via SSH

## Project Structure 

## Current Status
- [x] Basic project structure
- [ ] Hailo inference wrapper
- [ ] Video capture pipeline
- [ ] Boundary extraction
- [ ] Real-time visualization 