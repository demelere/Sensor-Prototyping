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
        resized = cv2.resize(frame, (w, h), interpolation=cv2.INTER_NEAREST)  # Use nearest neighbor for speed
        
        # Convert BGR to RGB
        if len(resized.shape) == 3 and resized.shape[2] == 3:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # Keep as uint8 for model input
        preprocessed = resized.astype(np.uint8)
        
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
            # Get raw outputs
            boxes = np.array(raw_output['yolov8n_seg/conv73'])  # [1, 20, 20, 64]
            scores = np.array(raw_output['yolov8n_seg/conv74'])  # [1, 20, 20, 80]
            classes = np.array(raw_output['yolov8n_seg/conv75'])  # [1, 20, 20, 32]
            masks = np.array(raw_output['yolov8n_seg/conv60'])   # [1, 40, 40, 64]
            
            # Remove batch dimension
            boxes = boxes[0]    # [20, 20, 64]
            scores = scores[0]  # [20, 20, 80]
            classes = classes[0]  # [20, 20, 32]
            masks = masks[0]    # [40, 40, 64]
            
            # Get max scores and class IDs for each grid cell
            max_scores = np.max(scores, axis=2)  # [20, 20]
            class_ids = np.argmax(scores, axis=2)  # [20, 20]
            
            # Find cells with scores above threshold
            valid_cells = max_scores > self.confidence_threshold
            if not np.any(valid_cells):
                return None
            
            # Get coordinates of valid cells
            valid_y, valid_x = np.where(valid_cells)
            
            # Sort by score to keep only top detections
            cell_scores = max_scores[valid_y, valid_x]
            sort_idx = np.argsort(-cell_scores)  # Sort in descending order
            valid_y = valid_y[sort_idx]
            valid_x = valid_x[sort_idx]
            
            # Keep only top 20 detections
            max_detections = 20
            valid_y = valid_y[:max_detections]
            valid_x = valid_x[:max_detections]
            
            # Pre-allocate arrays for better performance
            valid_boxes = []
            valid_scores = []
            valid_classes = []
            valid_masks = []
            
            # Process each valid detection
            for y, x in zip(valid_y, valid_x):
                # Get box coordinates
                box = boxes[y, x].reshape(-1, 4)[0]
                
                # Get score and class
                score = max_scores[y, x]
                class_id = class_ids[y, x]
                
                # Skip if class_id is out of bounds for masks
                if class_id >= masks.shape[2]:
                    continue
                
                # Get mask for this class
                mask = masks[:, :, class_id]  # [40, 40]
                
                # Only keep if mask has significant positive values
                if np.mean(mask > 0.5) > 0.01:  # At least 1% of mask should be positive
                    valid_boxes.append(box)
                    valid_scores.append(score)
                    valid_classes.append(class_id)
                    valid_masks.append(mask)
            
            if not valid_boxes:
                return None
            
            # Convert to numpy arrays
            valid_boxes = np.array(valid_boxes)
            valid_scores = np.array(valid_scores)
            valid_classes = np.array(valid_classes)
            
            # Resize masks to original frame size
            h, w = original_shape[:2]
            resized_masks = []
            for mask in valid_masks:
                resized_mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
                # Threshold the mask to make it binary
                resized_mask = (resized_mask > 0.5).astype(np.uint8)
                resized_masks.append(resized_mask)
            
            # Convert boxes to pixel coordinates
            boxes_pixels = np.zeros_like(valid_boxes)
            boxes_pixels[:, 0] = valid_boxes[:, 1] * h  # y1
            boxes_pixels[:, 1] = valid_boxes[:, 0] * w  # x1
            boxes_pixels[:, 2] = valid_boxes[:, 3] * h  # y2
            boxes_pixels[:, 3] = valid_boxes[:, 2] * w  # x2
            boxes_pixels = boxes_pixels.astype(np.int32)
            
            return {
                "boxes": boxes_pixels,
                "scores": valid_scores,
                "classes": valid_classes,
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