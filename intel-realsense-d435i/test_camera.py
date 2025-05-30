#!/usr/bin/env python3

import pyrealsense2 as rs
import numpy as np
import cv2
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def main():
    try:
        # Create a context object
        logger.info("Creating RealSense context...")
        ctx = rs.context()
        
        # Get device count
        device_count = ctx.query_devices().size()
        logger.info(f"Found {device_count} RealSense device(s)")
        
        if device_count == 0:
            logger.error("No RealSense devices found!")
            return
            
        # Initialize pipeline
        logger.info("\nInitializing pipeline...")
        pipeline = rs.pipeline()
        
        # Create a config object
        config = rs.config()
        
        # Configure streams - using low resolution and framerate for USB 2.0
        logger.info("Configuring streams...")
        config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 6)
        
        # Start streaming
        logger.info("Starting pipeline...")
        profile = pipeline.start(config)
        
        # Getting the depth sensor's depth scale
        depth_sensor = profile.get_device().first_depth_sensor()
        depth_scale = depth_sensor.get_depth_scale()
        logger.info(f"Depth Scale is: {depth_scale}")
        
        # Create colorizer for visualization
        colorizer = rs.colorizer()
        
        try:
            while True:
                # Wait for a coherent pair of frames
                frames = pipeline.wait_for_frames(timeout_ms=5000)
                depth_frame = frames.get_depth_frame()
                if not depth_frame:
                    continue

                # Convert depth frame to numpy array
                depth_image = np.asanyarray(depth_frame.get_data())
                
                # Colorize depth frame for visualization
                colorized_depth = np.asanyarray(colorizer.colorize(depth_frame).get_data())
                
                # Get depth statistics
                valid_depth = depth_image[depth_image != 0]  # Remove 0s (invalid depth)
                if len(valid_depth) > 0:
                    min_depth = valid_depth.min() * depth_scale
                    max_depth = valid_depth.max() * depth_scale
                    avg_depth = valid_depth.mean() * depth_scale
                    
                    # Add text to image
                    stats_text = f"Min: {min_depth:.2f}m, Max: {max_depth:.2f}m, Avg: {avg_depth:.2f}m"
                    cv2.putText(colorized_depth, stats_text, (10, 30), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                # Show depth frame
                cv2.namedWindow('RealSense Depth', cv2.WINDOW_AUTOSIZE)
                cv2.imshow('RealSense Depth', colorized_depth)
                
                # Break loop with 'q'
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
        finally:
            logger.info("\nStopping pipeline...")
            pipeline.stop()
            cv2.destroyAllWindows()
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 