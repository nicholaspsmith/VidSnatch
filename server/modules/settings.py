"""Settings management for Quikvid-DL."""

import json
import os
from pathlib import Path

class Settings:
    """Manages user settings and preferences."""
    
    def __init__(self):
        """Initialize settings manager."""
        self.settings_dir = Path.home() / ".quikvid-dl"
        self.settings_file = self.settings_dir / "settings.json"
        self.settings = self._load_settings()
    
    def _load_settings(self):
        """Load settings from file or create default settings."""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return self._get_default_settings()
        else:
            return self._get_default_settings()
    
    def _get_default_settings(self):
        """Get default settings."""
        return {
            "download_path": None,
            "first_run": True
        }
    
    def save_settings(self):
        """Save current settings to file."""
        try:
            self.settings_dir.mkdir(exist_ok=True)
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2)
        except IOError as e:
            print(f" [!] Warning: Could not save settings - {e}")
    
    def get_download_path(self):
        """Get the user's preferred download path."""
        return self.settings.get("download_path")
    
    def set_download_path(self, path):
        """Set the user's preferred download path."""
        self.settings["download_path"] = str(path)
        self.settings["first_run"] = False
        self.save_settings()
    
    def is_first_run(self):
        """Check if this is the first time running the application."""
        return self.settings.get("first_run", True)

# Global settings instance
_settings = Settings()

def get_download_path():
    """Get the user's preferred download path."""
    return _settings.get_download_path()

def set_download_path(path):
    """Set the user's preferred download path."""
    _settings.set_download_path(path)

def is_first_run():
    """Check if this is the first time running the application."""
    return _settings.is_first_run()