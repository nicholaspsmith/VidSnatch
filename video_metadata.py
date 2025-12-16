#!/usr/bin/env python3
"""
Video metadata storage for names and tags.
Stores person names and tags for video files.
"""

import json
import os
import threading

class VideoMetadata:
    def __init__(self, storage_file):
        self.storage_file = storage_file
        self.data = {
            'person_names': {},  # filename -> person name
            'file_tags': {},     # filename -> list of tags
            'ratings': {}        # filename -> rating (1-5)
        }
        self.lock = threading.Lock()
        self.load()

    def load(self):
        """Load metadata from persistent storage."""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    self.data = json.load(f)
                # Ensure all keys exist for backwards compatibility
                if 'ratings' not in self.data:
                    self.data['ratings'] = {}
                print(f" [+] Loaded video metadata for {len(self.data.get('person_names', {}))} files")
        except Exception as e:
            print(f" [!] Error loading video metadata: {e}")
            self.data = {'person_names': {}, 'file_tags': {}, 'ratings': {}}

    def save(self):
        """Save metadata to persistent storage."""
        try:
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            with self.lock:
                with open(self.storage_file, 'w') as f:
                    json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f" [!] Error saving video metadata: {e}")

    def set_person_name(self, filename, name):
        """Set person name for a file."""
        with self.lock:
            if name and name.strip():
                self.data['person_names'][filename] = name.strip()
            else:
                # Remove if empty
                self.data['person_names'].pop(filename, None)
        self.save()

    def get_person_name(self, filename):
        """Get person name for a file."""
        return self.data['person_names'].get(filename, '')

    def set_tags(self, filename, tags):
        """Set tags for a file."""
        with self.lock:
            if tags:
                self.data['file_tags'][filename] = tags
            else:
                # Remove if empty
                self.data['file_tags'].pop(filename, None)
        self.save()

    def get_tags(self, filename):
        """Get tags for a file."""
        return self.data['file_tags'].get(filename, [])

    def set_rating(self, filename, rating):
        """Set rating for a file (1-5 stars)."""
        with self.lock:
            if rating is not None and 1 <= rating <= 5:
                self.data['ratings'][filename] = rating
            else:
                # Remove if invalid or None
                self.data['ratings'].pop(filename, None)
        self.save()

    def get_rating(self, filename):
        """Get rating for a file."""
        return self.data['ratings'].get(filename, 0)

    def add_tag(self, filename, tag):
        """Add a single tag to a file."""
        with self.lock:
            if filename not in self.data['file_tags']:
                self.data['file_tags'][filename] = []
            if tag not in self.data['file_tags'][filename]:
                self.data['file_tags'][filename].append(tag)
        self.save()

    def remove_tag(self, filename, tag):
        """Remove a single tag from a file."""
        with self.lock:
            if filename in self.data['file_tags']:
                if tag in self.data['file_tags'][filename]:
                    self.data['file_tags'][filename].remove(tag)
                if not self.data['file_tags'][filename]:
                    del self.data['file_tags'][filename]
        self.save()

    def get_all_data(self):
        """Get all metadata."""
        return dict(self.data)

    def bulk_import(self, person_names_dict, file_tags_dict):
        """Bulk import data (for migration from localStorage)."""
        with self.lock:
            if person_names_dict:
                self.data['person_names'].update(person_names_dict)
            if file_tags_dict:
                self.data['file_tags'].update(file_tags_dict)
        self.save()
        print(f" [+] Imported metadata for {len(person_names_dict)} names and {len(file_tags_dict)} tag sets")

# Global instance
_video_metadata = None

def get_video_metadata():
    """Get the global video metadata instance."""
    global _video_metadata
    if _video_metadata is None:
        storage_path = os.path.expanduser('~/Applications/VidSnatch/.logs/video_metadata.json')
        _video_metadata = VideoMetadata(storage_path)
    return _video_metadata
