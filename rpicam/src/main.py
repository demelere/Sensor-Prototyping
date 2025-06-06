"""
Main entry point for the welding segmentation application
"""

import sys
import time
from config import config

def main():
    """Main application entry point"""
    print("=== Welding Video Segmentation ===")
    print(f"Model path: {config.get('model.path')}")
    print(f"Camera resolution: {config.get('camera.resolution')}")
    print(f"Target FPS: {config.get('processing.target_fps')}")
    
    print("\nConfiguration loaded successfully!")
    print("Ready for segmentation pipeline implementation...")

if __name__ == "__main__":
    main() 