"""
Basic Hailo NPU inference wrapper for stdc1 segmentation model
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
    """Basic Hailo NPU inference wrapper for segmentation"""
    
    def __init__(self, model_path=None):
        """Initialize Hailo inference
        
        Args:
            model_path: Path to .hef model file
        """
        self.model_path = model_path or config.get('model.path')
        self.input_size = config.get('model.input_size')  # [H, W, C]
        self.target_size = config.get('model.target_size')  # [H, W]
        
        self.hef = None
        self.vdevice = None
        self.network_group = None
        self.infer_vstreams = None
        self.infer_vstreams_ctx = None
        
        self.activation_ctx_manager = None
        self.activated_network = None
        
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
            from hailo_platform import VDevice, HEF, InferVStreams, InputVStreamParams, OutputVStreamParams
            self.hef = HEF(str(model_file))

            # 2. Get the target VDevice
            self.vdevice = VDevice()

            # 3. Configure the VDevice with the HEF - returns a list of ConfiguredNetwork objects
            configured_network_groups = self.vdevice.configure(self.hef)
            if not configured_network_groups:
                 raise RuntimeError("Failed to configure network groups from HEF.")
            self.network_group = configured_network_groups[0]
            
            # 4. Activate the network group. This returns a context manager.
            print("💡 Activating network group...")
            self.activation_ctx_manager = self.network_group.activate()
            self.activated_network = self.activation_ctx_manager.__enter__()
            print("✅ Network group activated.")
            
            # 5. Create the InferVStreams pipeline (was step 4)
            self.infer_vstreams = InferVStreams(self.network_group,
                                                InputVStreamParams.make(self.network_group),
                                                OutputVStreamParams.make(self.network_group))
            
            # 6. Enter the InferVStreams context (was step 5)
            self.infer_vstreams_ctx = self.infer_vstreams.__enter__()

            print(f"✅ Model loaded and ready for inference!")
            
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
        
        # Convert BGR to RGB if needed
        if len(resized.shape) == 3 and resized.shape[2] == 3:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # Normalize to [0, 1] or [-1, 1] depending on model requirements
        # For now, assume [0, 255] uint8 input
        preprocessed = resized.astype(np.uint8)
        
        # Add batch dimension if needed
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
            # The infer() method takes a dictionary of {input_name: numpy_array}
            # and returns a dictionary of {output_name: numpy_array}.
            
            # Get the name of the single input to use as the dictionary key.
            input_name = self.network_group.get_input_vstream_infos()[0].name

            # The infer() call is blocking and handles the write/read cycle.
            results_dict = self.infer_vstreams_ctx.infer({input_name: preprocessed_frame})
            
            # Return the entire dictionary of results
            return results_dict
                
        except Exception as e:
            print(f"❌ Inference failed: {e}")
            return None
    
    def _mock_inference(self, preprocessed_frame):
        """Mock inference output for testing without Hailo"""
        # Create a fake segmentation mask
        h, w = self.input_size[0], self.input_size[1]
        
        # Create simple mock segmentation (different regions)
        mock_output = np.zeros((h, w), dtype=np.uint8)
        
        # Add some fake segmented regions
        mock_output[h//4:3*h//4, w//4:3*w//4] = 1  # Center region
        mock_output[0:h//3, 0:w//3] = 2  # Top-left corner
        mock_output[2*h//3:h, 2*w//3:w] = 3  # Bottom-right corner
        
        return {"segmentation_mask": mock_output}
    
    def postprocess_output(self, raw_output, original_shape):
        """Postprocess inference output
        
        Args:
            raw_output: Raw inference output dictionary from infer()
            original_shape: Shape of original input frame (H, W, C)
            
        Returns:
            Processed segmentation mask
        """
        if raw_output is None:
            return None
        
        if not HAILO_AVAILABLE:
            # Handle mock output
            return raw_output["segmentation_mask"]
        
        # Get the name of the first output layer from the model info
        output_name = self.network_group.get_output_vstream_infos()[0].name
        
        # Extract the segmentation mask from the results dictionary
        mask = raw_output[output_name]
        
        # The output from InferVStreams often has a batch dimension, even if it's 1.
        # We remove it to get the single image mask.
        if mask.shape[0] == 1:
            mask = np.squeeze(mask, axis=0)

        # Resize back to original frame size
        if mask.shape[0] != original_shape[0] or mask.shape[1] != original_shape[1]:
            mask = cv2.resize(mask, (original_shape[1], original_shape[0]), interpolation=cv2.INTER_NEAREST)
        
        return mask
    
    def predict(self, frame):
        """Complete inference pipeline: preprocess -> infer -> postprocess
        
        Args:
            frame: Input image as numpy array
            
        Returns:
            Segmentation mask
        """
        if frame is None:
            return None
        
        try:
            # Preprocess
            preprocessed = self.preprocess_frame(frame)
            
            # Inference
            raw_output = self.run_inference(preprocessed)
            
            # Postprocess
            mask = self.postprocess_output(raw_output, frame.shape)
            
            return mask
            
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