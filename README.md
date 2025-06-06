# Intel RealSense D435i Test Project

This project contains test scripts for working with the Intel RealSense D435i depth camera on macOS.

## System Requirements

- macOS (tested on macOS Sequoia 15.4.1)
- Python 3.11 (required for RealSense SDK compatibility)
- Intel RealSense D435i camera
- USB 3.0 port (recommended)

## Setup Instructions

1. **Install pyenv for Python version management**:
   ```bash
   brew install pyenv
   ```

2. **Configure pyenv in your shell** (add to ~/.zshrc):
   ```bash
   export PYENV_ROOT="$HOME/.pyenv"
   command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
   eval "$(pyenv init -)"
   ```

3. **Install Python 3.11**:
   ```bash
   pyenv install 3.11
   ```

4. **Set up the project**:
   ```bash
   # Clone the repository
   git clone [repository-url]
   cd intel-realsense-d435i

   # Set local Python version
   pyenv local 3.11

   # Create and activate virtual environment
   python -m venv venv
   source venv/bin/activate

   # Install dependencies
   pip install pyrealsense2-macosx
   pip install numpy opencv-python
   ```

## Important Notes

1. **Permission Requirements**: 
   - The RealSense SDK on macOS may require sudo privileges to access the camera
   - This is a known issue since version 2.50.0 of the SDK

2. **Python Version Compatibility**:
   - The official `pyrealsense2` package doesn't support Python 3.12+
   - We use `pyrealsense2-macosx` which provides better macOS compatibility

3. **USB Connection**:
   - The camera is detected as "Intel RealSense USB2"
   - For best performance, use a USB 3.0 port if available

## Project Structure

- `test_camera.py`: Basic script to test camera connection and streaming
- `requirements.txt`: Python package dependencies
- `.gitignore`: Git ignore rules
- `.python-version`: pyenv local version configuration

## Running the Tests

Basic camera test:
```bash
# May require sudo on macOS
sudo python test_camera.py
```

## Troubleshooting

1. **"Failed to set power state" error**:
   - This is a known issue on macOS
   - Try running the script with sudo privileges

2. **"No streams are selected" error**:
   - Make sure stream configuration matches your camera's capabilities
   - Default configuration: 640x480 @ 30fps for both color and depth

## References

- [pyrealsense2-macosx Repository](https://github.com/cansik/pyrealsense2-macosx)
- [Intel RealSense SDK Issues](https://github.com/IntelRealSense/librealsense/issues/12601)