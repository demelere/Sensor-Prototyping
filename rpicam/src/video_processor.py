"""
Video capture and processing pipeline for real-time segmentation
"""

import time
import numpy as np
import cv2
from config import config
import os

try:
    from picamera2 import Picamera2
    CAMERA_AVAILABLE = True
except ImportError:
    print("⚠️  picamera2 not available")
    CAMERA_AVAILABLE = False

class VideoProcessor:
    """Handles video capture and real-time processing pipeline"""
    
    def __init__(self, inference_engine=None):
        """Initialize video processor
        
        Args:
            inference_engine: HailoInference instance for segmentation
        """
        self.inference_engine = inference_engine
        self.camera = None
        
        # Get config values
        self.resolution = config.get('camera.resolution')  # [H, W]
        self.framerate = config.get('camera.framerate')
        self.target_fps = config.get('processing.target_fps')
        
        # Performance tracking
        self.frame_count = 0
        self.total_inference_time = 0
        self.start_time = None
        
    def initialize_camera(self):
        """Initialize and configure Pi camera"""
        if not CAMERA_AVAILABLE:
            raise RuntimeError("picamera2 not available - install with: pip install picamera2")
        
        print("🎥 Initializing Pi camera...")
        self.camera = Picamera2()
        
        # Configure for video capture
        height, width = self.resolution
        camera_config = self.camera.create_video_configuration(
            main={"size": (width, height), "format": "RGB888"}
        )
        self.camera.configure(camera_config)
        
        # Start camera
        self.camera.start()
        time.sleep(2)  # Camera warm-up
        
        print(f"📹 Camera ready at {width}x{height}")
    
    def capture_frame(self):
        """Capture a single frame from camera
        
        Returns:
            numpy array: Captured frame or None if failed
        """
        if not self.camera:
            return None
        
        try:
            return self.camera.capture_array()
        except Exception as e:
            print(f"❌ Frame capture failed: {e}")
            return None
    
    def process_frame(self, frame):
        """Process a frame through the inference pipeline
        
        Args:
            frame: Input frame
            
        Returns:
            dict: Processing results with 'mask', 'inference_time', etc.
        """
        if frame is None or self.inference_engine is None:
            return None
        
        # Run inference
        inference_start = time.time()
        mask = self.inference_engine.predict(frame)
        inference_time = time.time() - inference_start
        
        # Update performance tracking
        self.frame_count += 1
        self.total_inference_time += inference_time
        
        return {
            'frame': frame,
            'mask': mask,
            'inference_time': inference_time,
            'frame_number': self.frame_count
        }
    
    def print_performance_stats(self, result):
        """Print performance statistics every 30 frames"""
        if result is None or self.frame_count % 30 != 0:
            return
        
        elapsed = time.time() - self.start_time
        overall_fps = self.frame_count / elapsed
        avg_inference_time = self.total_inference_time / self.frame_count
        
        print(f"📊 Frame {self.frame_count:4d} | "
              f"FPS: {overall_fps:5.1f} | "
              f"Inference: {result['inference_time']*1000:5.1f}ms | "
              f"Avg: {avg_inference_time*1000:5.1f}ms")
        
        if result['mask'] is not None:
            unique_vals = np.unique(result['mask'])
            print(f"    Mask classes: {len(unique_vals)} | Values: {unique_vals}")
    
    def run_realtime_test(self, duration_seconds=10, min_frames=60):
        """Run real-time segmentation test with display visualization"""
        print("\n=== Real-Time Video Segmentation Test ===")
        
        if not CAMERA_AVAILABLE:
            print("❌ Camera not available")
            return False
        
        try:
            # Set up display for Pi screen (even when SSH'd)
            os.environ['DISPLAY'] = ':0'
            
            # Initialize camera and inference
            picam2 = Picamera2()
            camera_config = picam2.create_video_configuration(
                main={"size": (self.resolution[1], self.resolution[0]), "format": "RGB888"}
            )
            picam2.configure(camera_config)
            
            print("🎥 Initializing Pi camera...")
            picam2.start()
            print(f"📹 Camera ready at {self.resolution[1]}x{self.resolution[0]}")
            
            # Create display window
            cv2.namedWindow('Real-Time Segmentation', cv2.WINDOW_NORMAL)
            cv2.resizeWindow('Real-Time Segmentation', 1280, 720)
            
            print("🔄 Starting real-time processing...")
            print("Press 'q' to quit or Ctrl+C to stop")
            
            start_time = time.time()
            frame_count = 0
            inference_times = []
            
            while True:
                loop_start = time.time()
                
                # Capture frame
                frame = picam2.capture_array()
                if frame is None:
                    continue
                
                # Run inference
                inference_start = time.time()
                mask = None
                if self.inference_engine:
                    mask = self.inference_engine.predict(frame)
                inference_time = (time.time() - inference_start) * 1000
                inference_times.append(inference_time)
                
                # Create visualization
                display_frame = self._create_segmentation_overlay(frame, mask)
                
                # Display on Pi screen
                cv2.imshow('Real-Time Segmentation', display_frame)
                
                # Handle window events
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("🛑 Stopped by user (pressed 'q')")
                    break
                
                frame_count += 1
                elapsed_time = time.time() - start_time
                
                # Print statistics every 30 frames
                if frame_count % 30 == 0:
                    avg_fps = frame_count / elapsed_time
                    avg_inference = np.mean(inference_times[-30:])
                    
                    if mask is not None:
                        unique_values = np.unique(mask)
                        print(f"📊 Frame {frame_count:4d} | FPS: {avg_fps:5.1f} | Inference: {avg_inference:6.1f}ms | Avg: {np.mean(inference_times):6.1f}ms")
                        print(f"    Mask classes: {len(unique_values)} | Values: {unique_values}")
                    else:
                        print(f"📊 Frame {frame_count:4d} | FPS: {avg_fps:5.1f} | No inference")
                
                # Stop after duration OR minimum frames reached
                if elapsed_time >= duration_seconds and frame_count >= min_frames:
                    print(f"🛑 Stopped after {duration_seconds} seconds and {frame_count} frames")
                    break
            
            # Cleanup
            cv2.destroyAllWindows()
            picam2.stop()
            print("📺 Display closed")
            print("📷 Camera stopped")
            
            # Final statistics
            total_time = time.time() - start_time
            avg_fps = frame_count / total_time
            avg_inference = np.mean(inference_times) if inference_times else 0
            
            print(f"\n📈 Final Statistics:")
            print(f"   Total frames: {frame_count}")
            print(f"   Total time: {total_time:.1f}s") 
            print(f"   Average FPS: {avg_fps:.1f}")
            print(f"   Average inference time: {avg_inference:.1f}ms")
            
            return True
            
        except KeyboardInterrupt:
            elapsed_time = time.time() - start_time if 'start_time' in locals() else 0
            print(f"\n🛑 Stopped by user after {elapsed_time:.1f} seconds")
            return True
        except Exception as e:
            print(f"❌ Error in video test: {e}")
            return False
        finally:
            # Ensure cleanup
            if 'picam2' in locals():
                picam2.stop()
            cv2.destroyAllWindows()
    
    def _create_segmentation_overlay(self, frame, mask):
        """Create visualization overlay with segmentation mask"""
        display_frame = frame.copy()
        
        if mask is not None:
            # Create colored overlay for segmentation
            height, width = mask.shape[:2]
            colored_mask = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Assign different colors to different classes
            unique_classes = np.unique(mask)
            colors = [
                (0, 0, 0),      # Black for background (class 0)
                (255, 0, 0),    # Red
                (0, 255, 0),    # Green  
                (0, 0, 255),    # Blue
                (255, 255, 0),  # Yellow
                (255, 0, 255),  # Magenta
                (0, 255, 255),  # Cyan
                (128, 128, 128), # Gray
                (255, 165, 0),  # Orange
                (128, 0, 128),  # Purple
            ]
            
            for i, class_id in enumerate(unique_classes):
                if class_id == 0:  # Skip background
                    continue
                color = colors[min(i, len(colors)-1)]
                colored_mask[mask == class_id] = color
            
            # Blend with original frame (30% overlay)
            alpha = 0.3
            display_frame = cv2.addWeighted(display_frame, 1-alpha, colored_mask, alpha, 0)
            
            # Add text overlay with class information
            text = f"Classes: {len(unique_classes)} | Values: {unique_classes}"
            cv2.putText(display_frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        else:
            # No mask - just show original frame with text
            cv2.putText(display_frame, "No segmentation mask", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        return display_frame
    
    def cleanup(self):
        """Clean up camera resources"""
        if self.camera:
            self.camera.stop()
            print("�� Camera stopped") 