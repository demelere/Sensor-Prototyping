#!/bin/bash

# Download YOLOv8n-seg model from Hailo Model Zoo
# This script should be run on the Raspberry Pi

MODEL_DIR="../models"
MODEL_NAME="yolov8n_seg.hef"
MODEL_URL="https://hailo-model-zoo.s3.eu-west-2.amazonaws.com/ModelZoo/Compiled/v2.15.0/hailo8/yolov8n_seg.hef"

echo "=== Downloading Hailo YOLOv8n-seg model ==="

# Create models directory if it doesn't exist
mkdir -p "$MODEL_DIR"

# Download the model
echo "Downloading $MODEL_NAME..."
wget -O "$MODEL_DIR/$MODEL_NAME" "$MODEL_URL"

if [ $? -eq 0 ]; then
    echo "✅ Model downloaded successfully to $MODEL_DIR/$MODEL_NAME"
    ls -lh "$MODEL_DIR/$MODEL_NAME"
else
    echo "❌ Failed to download model"
    exit 1
fi

echo "🎉 Setup complete! Model ready for inference." 