"""
Hailo NPU inference wrapper for YOLOSeg instance segmentation model
"""

import numpy as np
import cv2
from pathlib import Path
from config import config

try:
    # Try to import HailoRT - might not be installed yet
    import hailo_platform
    from hailo_platform import HEF, ConfigureParams, InferVStreams, InputVStreamParams, OutputVStreamParams, HailoStreamInterface, Device, VDevice
    HAILO_AVAILABLE = True
except ImportError:
    print("⚠️  HailoRT not available - using mock inference for testing")
    HAILO_AVAILABLE = False

class HailoInference:
    """Hailo NPU inference wrapper for YOLOSeg instance segmentation"""
    
    def __init__(self, model_path=None):
        """Initialize Hailo inference
        
        Args:
            model_path: Path to .hef model file
        """
        self.model_path = model_path or config.get('model.path')
        self.input_size = config.get('model.input_size')  # [H, W, C]
        self.target_size = config.get('model.target_size')  # [H, W]
        self.confidence_threshold = config.get('model.confidence_threshold', 0.5)
        self.iou_threshold = config.get('model.iou_threshold', 0.45)
        self.num_classes = config.get('model.num_classes', 80)
        
        # Model resources
        self.hef = None
        self.vdevice = None
        self.network_group = None
        self.infer_vstreams = None
        self.infer_vstreams_ctx = None
        self.activation_ctx_manager = None
        self.activated_network = None
        
        # Input/output info
        self.input_vstream_info = None
        self.output_vstream_info = None
        
        self._load_model()
    
    def _load_model(self):
        """Load the Hailo model and prepare for inference."""
        model_file = Path(self.model_path)
        
        if not model_file.exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        
        print(f"Loading Hailo model: {self.model_path}")
        
        if not HAILO_AVAILABLE:
            print("📝 Mock mode: HailoRT not available")
            return
        
        try:
            # 1. Create HEF object from the file
            self.hef = HEF(str(model_file))
            
            # 2. Get the target VDevice
            self.vdevice = VDevice()
            
            # 3. Configure the VDevice with the HEF
            configured_network_groups = self.vdevice.configure(self.hef)
            if not configured_network_groups:
                raise RuntimeError("Failed to configure network groups from HEF.")
            self.network_group = configured_network_groups[0]
            
            # Store input/output info
            self.input_vstream_info = self.network_group.get_input_vstream_infos()[0]
            self.output_vstream_info = self.network_group.get_output_vstream_infos()
            
            # 4. Activate the network group
            print("💡 Activating network group...")
            self.activation_ctx_manager = self.network_group.activate()
            self.activated_network = self.activation_ctx_manager.__enter__()
            print("✅ Network group activated.")
            
            # 5. Create the InferVStreams pipeline
            self.infer_vstreams = InferVStreams(
                self.network_group,
                InputVStreamParams.make(self.network_group),
                OutputVStreamParams.make(self.network_group)
            )
            
            # 6. Enter the InferVStreams context
            self.infer_vstreams_ctx = self.infer_vstreams.__enter__()
            
            print(f"✅ Model loaded and ready for inference!")
            print(f"Input shape: {self.input_vstream_info.shape}")
            print(f"Output layers: {[info.name for info in self.output_vstream_info]}")
            
        except Exception as e:
            print(f"❌ Failed to load model: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def preprocess_frame(self, frame):
        """Preprocess input frame for inference
        
        Args:
            frame: Input image as numpy array (H, W, C)
            
        Returns:
            Preprocessed frame ready for inference
        """
        if frame is None:
            raise ValueError("Input frame is None")
        
        # Resize to model input size
        h, w = self.input_size[0], self.input_size[1]
        resized = cv2.resize(frame, (w, h))
        
        # Convert BGR to RGB
        if len(resized.shape) == 3 and resized.shape[2] == 3:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # Normalize to [0, 1]
        preprocessed = resized.astype(np.float32) / 255.0
        
        # Add batch dimension
        if len(preprocessed.shape) == 3:
            preprocessed = np.expand_dims(preprocessed, axis=0)
        
        return preprocessed
    
    def run_inference(self, preprocessed_frame):
        """Run inference using the InferVStreams context."""
        if not HAILO_AVAILABLE:
            return self._mock_inference(preprocessed_frame)
        
        if not self.infer_vstreams_ctx:
            print("❌ InferVStreams context not initialized. Cannot run inference.")
            return None
        
        try:
            # Get input name from model info
            input_name = self.input_vstream_info.name
            
            # Run inference
            results_dict = self.infer_vstreams_ctx.infer({input_name: preprocessed_frame})
            
            return results_dict
                
        except Exception as e:
            print(f"❌ Inference failed: {e}")
            return None
    
    def _mock_inference(self, preprocessed_frame):
        """Mock inference output for testing without Hailo"""
        h, w = self.input_size[0], self.input_size[1]
        
        # Create mock instance segmentation output
        mock_output = {
            "detection_boxes": np.array([[0.1, 0.1, 0.3, 0.3], [0.5, 0.5, 0.7, 0.7]]),  # [y1, x1, y2, x2]
            "detection_scores": np.array([0.9, 0.8]),
            "detection_classes": np.array([1, 2]),
            "detection_masks": np.random.randint(0, 2, (2, h, w), dtype=np.uint8)
        }
        
        return mock_output
    
    def postprocess_output(self, raw_output, original_shape):
        """Postprocess inference output for instance segmentation
        
        Args:
            raw_output: Raw inference output dictionary from infer()
            original_shape: Shape of original input frame (H, W, C)
            
        Returns:
            dict: Processed results with boxes, scores, classes, and masks
        """
        if raw_output is None:
            return None
        
        if not HAILO_AVAILABLE:
            return raw_output
        
        try:
            # Extract outputs based on YOLOSeg model structure
            # Note: Actual output names may need to be adjusted based on your model
            boxes = raw_output["detection_boxes"]
            scores = raw_output["detection_scores"]
            classes = raw_output["detection_classes"]
            masks = raw_output["detection_masks"]
            
            # Filter by confidence threshold
            keep_indices = scores > self.confidence_threshold
            boxes = boxes[keep_indices]
            scores = scores[keep_indices]
            classes = classes[keep_indices]
            masks = masks[keep_indices]
            
            # Resize masks to original frame size
            h, w = original_shape[:2]
            resized_masks = []
            for mask in masks:
                resized_mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
                resized_masks.append(resized_mask)
            
            # Convert boxes to pixel coordinates
            boxes_pixels = []
            for box in boxes:
                y1, x1, y2, x2 = box
                y1 = int(y1 * h)
                x1 = int(x1 * w)
                y2 = int(y2 * h)
                x2 = int(x2 * w)
                boxes_pixels.append([y1, x1, y2, x2])
            
            return {
                "boxes": np.array(boxes_pixels),
                "scores": scores,
                "classes": classes,
                "masks": np.array(resized_masks)
            }
            
        except Exception as e:
            print(f"❌ Postprocessing failed: {e}")
            return None
    
    def predict(self, frame):
        """Complete inference pipeline: preprocess -> infer -> postprocess
        
        Args:
            frame: Input image as numpy array
            
        Returns:
            dict: Processed results with boxes, scores, classes, and masks
        """
        if frame is None:
            return None
        
        try:
            # Preprocess
            preprocessed = self.preprocess_frame(frame)
            
            # Inference
            raw_output = self.run_inference(preprocessed)
            
            # Postprocess
            results = self.postprocess_output(raw_output, frame.shape)
            
            return results
            
        except Exception as e:
            print(f"❌ Prediction failed: {e}")
            return None
    
    def __del__(self):
        """Cleanup resources by exiting the context managers in the correct order."""
        # Exit the inference streams context first
        if hasattr(self, 'infer_vstreams') and hasattr(self, 'infer_vstreams_ctx') and self.infer_vstreams_ctx:
            try:
                self.infer_vstreams.__exit__(None, None, None)
                print("✅ Inference streams released.")
            except Exception as e:
                print(f"⚠️  Error releasing inference streams: {e}")
        
        # Then, exit the activation context
        if hasattr(self, 'activation_ctx_manager') and self.activation_ctx_manager:
            try:
                self.activation_ctx_manager.__exit__(None, None, None)
                print("✅ Network group deactivated.")
            except Exception as e:
                print(f"⚠️  Error deactivating network group: {e}") 