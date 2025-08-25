#!/usr/bin/env python3
"""
Simple URL tracking system for VidSnatch.
Tracks all download URLs and their completion status.
"""

import json
import os
import time
from datetime import datetime
import threading
from modules.config import URL_TRACKER_FILE

class URLTracker:
    def __init__(self, storage_file=URL_TRACKER_FILE):
        self.storage_file = storage_file
        self.urls = {}
        self.lock = threading.Lock()
        self.load()
    
    def load(self):
        """Load URLs from persistent storage."""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    self.urls = json.load(f)
                print(f" [+] Loaded {len(self.urls)} tracked URLs")
        except Exception as e:
            print(f" [!] Error loading URL tracker: {e}")
            self.urls = {}
    
    def save(self):
        """Save URLs to persistent storage."""
        try:
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            with self.lock:
                with open(self.storage_file, 'w') as f:
                    json.dump(self.urls, f, indent=2)
        except Exception as e:
            print(f" [!] Error saving URL tracker: {e}")
    
    def add_url(self, url, title=None):
        """Add a URL to track. Returns the tracking ID."""
        # Use URL as the key for simplicity
        url_id = str(hash(url + str(time.time())))
        
        with self.lock:
            self.urls[url_id] = {
                'url': url,
                'title': title or 'Unknown',
                'status': 'pending',
                'added': datetime.now().isoformat(),
                'completed': None,
                'attempts': 0
            }
        
        self.save()
        print(f" [+] Tracking URL: {url[:50]}...")
        return url_id
    
    def mark_attempting(self, url_id):
        """Mark a URL as being attempted."""
        with self.lock:
            if url_id in self.urls:
                self.urls[url_id]['status'] = 'downloading'
                self.urls[url_id]['attempts'] += 1
                self.urls[url_id]['last_attempt'] = datetime.now().isoformat()
        self.save()
    
    def mark_completed(self, url_id):
        """Mark a URL as successfully downloaded."""
        with self.lock:
            if url_id in self.urls:
                self.urls[url_id]['status'] = 'completed'
                self.urls[url_id]['completed'] = datetime.now().isoformat()
                print(f" [+] Marked as completed: {self.urls[url_id]['title']}")
        self.save()
    
    def mark_failed(self, url_id, error=None):
        """Mark a URL as failed (but will retry on restart)."""
        with self.lock:
            if url_id in self.urls:
                self.urls[url_id]['status'] = 'failed'
                self.urls[url_id]['last_error'] = error or 'Unknown error'
                print(f" [!] Marked as failed: {self.urls[url_id]['title']}")
        self.save()
    
    def get_incomplete_urls(self):
        """Get all URLs that haven't been successfully downloaded."""
        incomplete = []
        with self.lock:
            for url_id, data in self.urls.items():
                if data['status'] != 'completed':
                    incomplete.append((url_id, data))
        return incomplete
    
    def find_by_url(self, url):
        """Find a tracking entry by URL."""
        with self.lock:
            for url_id, data in self.urls.items():
                if data['url'] == url:
                    return url_id, data
        return None, None
    
    def find_by_partial_filename(self, filename):
        """Find a URL that might match a partial filename."""
        # Clean filename for comparison
        clean_filename = filename.replace('.part', '').replace('.ytdl', '').replace('.temp', '').lower()
        clean_filename = ''.join(c for c in clean_filename if c.isalnum() or c.isspace())
        
        best_match = None
        with self.lock:
            for url_id, data in self.urls.items():
                if data['status'] == 'completed':
                    continue
                    
                # Clean title for comparison
                clean_title = data['title'].lower()
                clean_title = ''.join(c for c in clean_title if c.isalnum() or c.isspace())
                
                # Simple substring match
                if clean_title in clean_filename or clean_filename in clean_title:
                    best_match = (url_id, data)
                    break
                
                # Word overlap check
                filename_words = set(clean_filename.split())
                title_words = set(clean_title.split())
                if filename_words and title_words:
                    overlap = len(filename_words.intersection(title_words))
                    if overlap >= min(3, len(filename_words) * 0.5):
                        best_match = (url_id, data)
                        break
        
        return best_match
    
    def cleanup_old_completed(self, days=7):
        """Remove completed URLs older than specified days."""
        cutoff = datetime.now().timestamp() - (days * 86400)
        removed = 0
        
        with self.lock:
            to_remove = []
            for url_id, data in self.urls.items():
                if data['status'] == 'completed' and data.get('completed'):
                    completed_time = datetime.fromisoformat(data['completed']).timestamp()
                    if completed_time < cutoff:
                        to_remove.append(url_id)
            
            for url_id in to_remove:
                del self.urls[url_id]
                removed += 1
        
        if removed > 0:
            self.save()
            print(f" [+] Cleaned up {removed} old completed URLs")
        
        return removed

# Global tracker instance
url_tracker = None

def init_tracker(storage_file='.logs/url_tracker.json'):
    """Initialize the global URL tracker."""
    global url_tracker
    url_tracker = URLTracker(storage_file)
    return url_tracker

def get_tracker():
    """Get the global URL tracker instance."""
    global url_tracker
    if url_tracker is None:
        url_tracker = URLTracker()
    return url_tracker