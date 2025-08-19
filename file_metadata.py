#!/usr/bin/env python3
"""
File metadata tracking system for VidSnatch.
Maps downloaded files to their source URLs and other metadata.
"""

import json
import os
import time
import threading
import hashlib

class FileMetadata:
    def __init__(self, storage_file='.logs/file_metadata.json'):
        self.storage_file = storage_file
        self.metadata = {}
        self.lock = threading.Lock()
        self.load()
    
    def load(self):
        """Load file metadata from persistent storage."""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    self.metadata = json.load(f)
                print(f" [+] Loaded metadata for {len(self.metadata)} files")
        except Exception as e:
            print(f" [!] Error loading file metadata: {e}")
            self.metadata = {}
    
    def save(self):
        """Save file metadata to persistent storage."""
        try:
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            with self.lock:
                with open(self.storage_file, 'w') as f:
                    json.dump(self.metadata, f, indent=2)
        except Exception as e:
            print(f" [!] Error saving file metadata: {e}")
    
    def add_file(self, filename, url, title=None, download_time=None):
        """Add file metadata."""
        file_key = self._get_file_key(filename)
        
        with self.lock:
            self.metadata[file_key] = {
                'filename': filename,
                'url': url,
                'title': title or 'Unknown',
                'download_time': download_time or time.time(),
                'added_time': time.time()
            }
        
        self.save()
        return file_key
    
    def get_file_metadata(self, filename):
        """Get metadata for a file."""
        file_key = self._get_file_key(filename)
        return self.metadata.get(file_key)
    
    def get_file_url(self, filename):
        """Get the source URL for a file."""
        metadata = self.get_file_metadata(filename)
        return metadata.get('url') if metadata else None
    
    def update_file(self, filename, **kwargs):
        """Update file metadata."""
        file_key = self._get_file_key(filename)
        
        if file_key in self.metadata:
            with self.lock:
                self.metadata[file_key].update(kwargs)
            self.save()
            return True
        return False
    
    def remove_file(self, filename):
        """Remove file metadata."""
        file_key = self._get_file_key(filename)
        
        with self.lock:
            if file_key in self.metadata:
                del self.metadata[file_key]
                self.save()
                return True
        return False
    
    def get_all_metadata(self):
        """Get all file metadata."""
        return dict(self.metadata)
    
    def _get_file_key(self, filename):
        """Generate a consistent key for a filename."""
        # Use just the filename without path for the key
        base_filename = os.path.basename(filename)
        return base_filename.lower()

# Global instance
_file_metadata = None

def get_file_metadata():
    """Get the global file metadata instance."""
    global _file_metadata
    if _file_metadata is None:
        _file_metadata = FileMetadata()
    return _file_metadata