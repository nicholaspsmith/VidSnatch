#!/usr/bin/env python3
"""
Save active downloads as failed downloads before server shutdown.
This preserves download URLs so they can be retried after reinstall.
"""
import json
import os
import sys

def save_active_as_failed():
    """Convert active downloads to failed downloads to preserve URLs."""
    active_file = os.path.expanduser("~/Applications/VidSnatch/.logs/active_downloads.json")
    failed_file = os.path.expanduser("~/Applications/VidSnatch/.logs/failed_downloads.json")
    
    # Check if active downloads file exists
    if not os.path.exists(active_file):
        print(" [+] No active downloads file found")
        return True
    
    try:
        # Load active downloads
        with open(active_file, 'r') as f:
            active_downloads = json.load(f)
        
        if not active_downloads:
            print(" [+] No active downloads to save")
            return True
        
        # Load existing failed downloads
        failed_downloads = {}
        if os.path.exists(failed_file):
            try:
                with open(failed_file, 'r') as f:
                    failed_downloads = json.load(f)
            except:
                failed_downloads = {}
        
        # Convert each active download to failed
        saved_count = 0
        for download_id, download_data in active_downloads.items():
            # Only save if it has a URL and isn't already complete
            if download_data.get('url') and download_data.get('status') not in ['completed', 'complete']:
                failed_downloads[download_id] = {
                    'url': download_data['url'],
                    'title': download_data.get('title', 'Unknown'),
                    'error': 'Server shutdown during download',
                    'retry_count': download_data.get('retry_count', 0),
                    'open_folder': download_data.get('open_folder', True),
                    'partial_files': []  # Will be detected on retry
                }
                saved_count += 1
                print(f" [+] Saved download: {download_data.get('title', 'Unknown')}")
        
        # Save failed downloads
        if saved_count > 0:
            os.makedirs(os.path.dirname(failed_file), exist_ok=True)
            with open(failed_file, 'w') as f:
                json.dump(failed_downloads, f, indent=2)
            print(f" [+] Saved {saved_count} active downloads as failed for retry")
        
        return True
        
    except Exception as e:
        print(f" [!] Error saving active downloads: {e}")
        return False

if __name__ == "__main__":
    success = save_active_as_failed()
    sys.exit(0 if success else 1)