"""
Main entry point for the welding segmentation application
"""

from config import config
from hailo_inference import HailoInference
from video_processor import VideoProcessor

def main():
    """Main application entry point"""
    print("=== Welding Video Segmentation ===")
    print(f"Model path: {config.get('model.path')}")
    print(f"Camera resolution: {config.get('camera.resolution')}")
    print(f"Target FPS: {config.get('processing.target_fps')}")
    
    print("\nConfiguration loaded successfully!")
    
    # Initialize inference engine
    print("🧠 Initializing inference engine...")
    inference = HailoInference()
    
    # Initialize video processor
    video_processor = VideoProcessor(inference_engine=inference)
    
    # Run real-time test
    video_processor.run_realtime_test()
    
    print("\n🎉 Real-time video segmentation test complete!")

if __name__ == "__main__":
    main() 