"""
Video capture and processing pipeline for real-time instance segmentation
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
            inference_engine: HailoInference instance for instance segmentation
        """
        self.inference_engine = inference_engine
        self.camera = None
        
        # Get config values
        self.resolution = config.get('camera.resolution')  # [H, W]
        self.framerate = config.get('camera.framerate')
        self.target_fps = config.get('processing.target_fps')
        self.show_confidence = config.get('display.show_confidence', True)
        self.show_class_names = config.get('display.show_class_names', True)
        
        # Performance tracking
        self.frame_count = 0
        self.total_inference_time = 0
        self.start_time = None
        
        # COCO class names (first 80 classes)
        self.class_names = [
            'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
            'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat',
            'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack',
            'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
            'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
            'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
            'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair',
            'couch', 'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse',
            'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator',
            'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
        ]
    
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
            dict: Processing results with 'frame', 'results', 'inference_time', etc.
        """
        if frame is None or self.inference_engine is None:
            return None
        
        # Run inference
        inference_start = time.time()
        results = self.inference_engine.predict(frame)
        inference_time = time.time() - inference_start
        
        # Update performance tracking
        self.frame_count += 1
        self.total_inference_time += inference_time
        
        return {
            'frame': frame,
            'results': results,
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
        
        if result['results'] is not None:
            num_instances = len(result['results']['classes'])
            print(f"    Instances detected: {num_instances}")
    
    def _create_segmentation_overlay(self, frame, results):
        """Create visualization overlay with instance segmentation results"""
        display_frame = frame.copy()
        
        if results is None:
            cv2.putText(display_frame, "No detection results", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            return display_frame
        
        # Get results
        boxes = results['boxes']
        scores = results['scores']
        classes = results['classes']
        masks = results['masks']
        
        print(f"\nDebug - Processing {len(classes)} instances:")
        print(f"Boxes shape: {boxes.shape}")
        print(f"Scores shape: {scores.shape}")
        print(f"Classes shape: {classes.shape}")
        print(f"Masks shape: {masks.shape}")
        
        # Generate random colors for each instance
        num_instances = len(classes)
        colors = np.random.randint(0, 255, (num_instances, 3), dtype=np.uint8)
        
        # Create overlay for masks
        overlay = np.zeros_like(display_frame)
        
        # Draw each instance
        for i in range(num_instances):
            # Get instance info
            box = boxes[i]
            score = scores[i]
            class_id = int(classes[i])
            mask = masks[i]
            color = colors[i]
            
            print(f"Instance {i}:")
            print(f"  Box: {box}")
            print(f"  Score: {score:.2f}")
            print(f"  Class: {class_id} ({self.class_names[class_id] if class_id < len(self.class_names) else 'unknown'})")
            print(f"  Mask sum: {np.sum(mask)}")
            
            # Draw mask with higher opacity
            mask_overlay = np.zeros_like(overlay)
            mask_overlay[mask > 0] = color
            cv2.addWeighted(overlay, 1, mask_overlay, 0.7, 0, overlay)
            
            # Draw bounding box
            y1, x1, y2, x2 = box
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), color.tolist(), 2)
            
            # Prepare label
            label = []
            if self.show_class_names and class_id < len(self.class_names):
                label.append(self.class_names[class_id])
            if self.show_confidence:
                label.append(f"{score:.2f}")
            label = " ".join(label)
            
            # Draw label background
            (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(display_frame, (x1, y1-label_h-4), (x1+label_w, y1), color.tolist(), -1)
            
            # Draw label text
            cv2.putText(display_frame, label, (x1, y1-4),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Blend overlay with original frame with higher mask visibility
        alpha = 0.4  # Increased from 0.6 to make masks more visible
        cv2.addWeighted(display_frame, 1-alpha, overlay, alpha, 0, display_frame)
        
        # Add frame info
        info_text = f"Instances: {num_instances}"
        cv2.putText(display_frame, info_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return display_frame
    
    def run_realtime_test(self):
        """Run real-time instance segmentation test with display visualization"""
        print("\n=== Real-Time Instance Segmentation Test ===")
        
        if not CAMERA_AVAILABLE:
            print("❌ Camera not available")
            return False
        
        try:
            # Set up display for Pi screen (even when SSH'd)
            os.environ['DISPLAY'] = ':0'
            
            # Initialize camera and inference
            picam2 = Picamera2()
            camera_config = picam2.create_video_configuration(
                main={"size": (self.resolution[1], self.resolution[0]), "format": "RGB888"},
                buffer_count=4  # Reduce buffer count for lower latency
            )
            picam2.configure(camera_config)
            
            print("🎥 Initializing Pi camera...")
            picam2.start()
            print(f"📹 Camera ready at {self.resolution[1]}x{self.resolution[0]}")
            
            # Create display window
            window_name = config.get('display.window_name', 'Instance Segmentation')
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, 640, 480)  # Smaller window for better performance
            
            print("🔄 Starting real-time processing...")
            print("Press 'q' to quit or Ctrl+C to stop")
            
            start_time = time.time()
            frame_count = 0
            inference_times = []
            skip_frames = config.get('processing.skip_frames', 1)
            frame_idx = 0
            
            while True:
                loop_start = time.time()
                
                # Capture frame
                frame = picam2.capture_array()
                if frame is None:
                    continue
                
                # Skip frames for better performance
                frame_idx += 1
                if frame_idx % (skip_frames + 1) != 0:
                    continue
                
                # Run inference
                inference_start = time.time()
                results = None
                if self.inference_engine:
                    results = self.inference_engine.predict(frame)
                inference_time = (time.time() - inference_start) * 1000
                inference_times.append(inference_time)
                
                # Create visualization
                display_frame = self._create_segmentation_overlay(frame, results)
                
                # Display on Pi screen
                cv2.imshow(window_name, display_frame)
                
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
                    
                    if results is not None:
                        num_instances = len(results['classes'])
                        print(f"📊 Frame {frame_count:4d} | FPS: {avg_fps:5.1f} | Inference: {avg_inference:6.1f}ms | Avg: {np.mean(inference_times):6.1f}ms")
                        print(f"    Instances detected: {num_instances}")
                    else:
                        print(f"📊 Frame {frame_count:4d} | FPS: {avg_fps:5.1f} | No inference")
            
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
    
    def cleanup(self):
        """Clean up camera resources"""
        if self.camera:
            self.camera.stop()
            print("�� Camera stopped") 