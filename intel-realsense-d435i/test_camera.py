#!/usr/bin/env python3

import pyrealsense2 as rs

def main():
    try:
        # Create a context object. This object owns the handles to all connected realsense devices
        print("Creating RealSense context...")
        ctx = rs.context()

        print("Available devices:")
        for d in ctx.devices:
            print(f"- {d.get_info(rs.camera_info.name)} (S/N: {d.get_info(rs.camera_info.serial_number)})")

        if not ctx.devices:
            print("No RealSense devices found!")
            return

        # Initialize the pipeline
        print("\nInitializing pipeline...")
        pipeline = rs.pipeline()
        config = rs.config()
        
        # Enable depth and color streams
        print("Configuring streams...")
        config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        
        # Start streaming with configured settings
        print("Starting pipeline...")
        pipeline_profile = pipeline.start(config)
        
        try:
            # Wait for a coherent pair of frames
            print("Waiting for frames...")
            frames = pipeline.wait_for_frames(timeout_ms=5000)  # 5 second timeout
            depth_frame = frames.get_depth_frame()
            color_frame = frames.get_color_frame()
            
            if not depth_frame or not color_frame:
                print("Error: Could not get frames!")
                return
                
            print("\nCamera is working! Stream information:")
            print(f"Depth frame width: {depth_frame.get_width()}")
            print(f"Depth frame height: {depth_frame.get_height()}")
            print(f"Color frame width: {color_frame.get_width()}")
            print(f"Color frame height: {color_frame.get_height()}")
            
        finally:
            print("\nStopping pipeline...")
            pipeline.stop()
            
    except Exception as e:
        print(f"\nError occurred: {str(e)}")

if __name__ == "__main__":
    main() 