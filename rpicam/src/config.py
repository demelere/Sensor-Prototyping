"""
Configuration management for the welding segmentation project
"""

import yaml
import os
from pathlib import Path

class Config:
    def __init__(self, config_path="config/config.yaml"):
        self.config_path = Path(config_path)
        self.data = self._load_config()
    
    def _load_config(self):
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"Config file {self.config_path} not found, using defaults")
            return self._default_config()
    
    def _default_config(self):
        """Default configuration values"""
        return {
            'model': {
                'path': 'models/stdc1.hef',
                'input_size': [1024, 1920, 3],
                'target_size': [720, 1280]
            },
            'camera': {
                'resolution': [720, 1280],
                'framerate': 30,
                'format': 'RGB888'
            },
            'processing': {
                'target_fps': 25,
                'enable_boundary_extraction': True,
                'visualization': True
            }
        }
    
    def get(self, key_path, default=None):
        """Get configuration value using dot notation (e.g., 'model.path')"""
        keys = key_path.split('.')
        value = self.data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

# Global config instance
config = Config() 