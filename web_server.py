"""Enhanced web server for Chrome extension integration with Quikvid-DL."""

import json
import os
import re
import sys
import threading
import time
import uuid
import signal
import subprocess
import logging
import logging.handlers
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Import with dependency check like main.py
import modules.config as config
import modules.utilities as utilities
from url_tracker import init_tracker, get_tracker
from file_metadata import get_file_metadata

# Check for yt-dlp dependency
while True:
    try:
        import yt_dlp  # noqa: F401
        break
    except ImportError as e:
        package_name = str(e).split("'")[1] if "'" in str(e) else str(e)[17:-1]
        print(f" [!] Installing missing package: {package_name}")
        pip_package = config.REQUIRED_PACKAGES.get(package_name, package_name)
        utilities.install(pip_package)

# Now safe to import videoDownloader
import modules.videoDownloader as videoDownloader

# Global dictionary to track downloads
active_downloads = {}
download_lock = threading.Lock()

# Failed downloads persistence
failed_downloads = {}
failed_downloads_file = '.logs/failed_downloads.json'

# Active downloads persistence
active_downloads_file = '.logs/active_downloads.json'

def save_active_downloads():
    """Save active downloads to persistent storage (only metadata, not the actual download state)."""
    try:
        os.makedirs(os.path.dirname(active_downloads_file), exist_ok=True)
        # Only save basic info that can be used to detect orphaned downloads
        active_data = {}
        for download_id, progress in active_downloads.items():
            # Only save downloads that are actually in progress
            if progress.status in ['preparing', 'downloading', 'processing']:
                active_data[download_id] = {
                    'title': progress.title,
                    'url': progress.url,
                    'status': progress.status,
                    'percent': progress.percent,
                    'start_time': progress.start_time
                }
        with open(active_downloads_file, 'w') as f:
            json.dump(active_data, f, indent=2)
    except Exception as e:
        print(f" [!] Error saving active downloads: {e}")

def load_active_downloads():
    """Load active downloads from persistent storage and mark as interrupted."""
    global active_downloads
    try:
        if os.path.exists(active_downloads_file):
            with open(active_downloads_file, 'r') as f:
                saved_downloads = json.load(f)
                
                if saved_downloads:
                    print(f" [!] Found {len(saved_downloads)} interrupted downloads from previous session")
                    
                    # Convert saved downloads to failed downloads since they were interrupted
                    for download_id, download_info in saved_downloads.items():
                        # Add to failed downloads so they can be retried
                        failed_downloads[download_id] = {
                            'title': download_info['title'],
                            'url': download_info['url'],
                            'error': 'Download interrupted by server restart',
                            'retry_count': 0,
                            'open_folder': True
                        }
                    
                    # Save the failed downloads
                    save_failed_downloads()
                    print(f" [+] Moved {len(saved_downloads)} interrupted downloads to failed list for retry")
                    
                    # Clear the active downloads file
                    with open(active_downloads_file, 'w') as f:
                        json.dump({}, f)
    except Exception as e:
        print(f" [!] Error loading active downloads: {e}")

def load_failed_downloads():
    """Load failed downloads from persistent storage."""
    global failed_downloads
    try:
        if os.path.exists(failed_downloads_file):
            with open(failed_downloads_file, 'r') as f:
                failed_downloads = json.load(f)
                print(f" [+] Loaded {len(failed_downloads)} failed downloads from storage")
    except Exception as e:
        print(f" [!] Error loading failed downloads: {e}")
        failed_downloads = {}

def save_failed_downloads():
    """Save failed downloads to persistent storage."""
    try:
        os.makedirs(os.path.dirname(failed_downloads_file), exist_ok=True)
        with open(failed_downloads_file, 'w') as f:
            json.dump(failed_downloads, f, indent=2)
    except Exception as e:
        print(f" [!] Error saving failed downloads: {e}")

def add_failed_download(download_id, download_data):
    """Add a failed download to the persistent store with enhanced logging."""
    global failed_downloads
    
    # Extract URL components for debugging
    url = download_data.get('url', '')
    try:
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        path = parsed_url.path
    except Exception:
        domain = 'unknown'
        path = 'unknown'
    
    # Create enhanced failed download entry
    failed_downloads[download_id] = {
        'id': download_id,
        'url': url,
        'domain': domain,
        'path': path,
        'title': download_data.get('title'),
        'error': download_data.get('error'),
        'failed_at': time.time(),
        'failed_at_human': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
        'retry_count': download_data.get('retry_count', 0),
        'open_folder': download_data.get('open_folder', True),
        'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'python_version': sys.version,
        'yt_dlp_version': getattr(yt_dlp, 'version', {}).get('version', 'unknown') if 'yt_dlp' in globals() else 'unknown'
    }
    
    # Enhanced logging for developers
    try:
        os.makedirs('.logs', exist_ok=True)
        developer_log_file = '.logs/failed_downloads_detailed.json'
        
        # Load existing detailed logs
        detailed_logs = []
        if os.path.exists(developer_log_file):
            try:
                with open(developer_log_file, 'r') as f:
                    detailed_logs = json.load(f)
            except Exception:
                detailed_logs = []
        
        # Add detailed entry for developers
        detailed_entry = {
            'download_id': download_id,
            'timestamp': time.time(),
            'timestamp_human': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
            'url': url,
            'domain': domain,
            'title': download_data.get('title'),
            'error_message': download_data.get('error'),
            'retry_count': download_data.get('retry_count', 0),
            'system_info': {
                'python_version': sys.version,
                'platform': sys.platform,
                'yt_dlp_version': getattr(yt_dlp, 'version', {}).get('version', 'unknown') if 'yt_dlp' in globals() else 'unknown'
            },
            'debugging_info': {
                'url_path': path,
                'url_scheme': parsed_url.scheme if 'parsed_url' in locals() else 'unknown',
                'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
            }
        }
        
        detailed_logs.append(detailed_entry)
        
        # Keep only the last 50 detailed logs to prevent file from growing too large
        if len(detailed_logs) > 50:
            detailed_logs = detailed_logs[-50:]
        
        # Save detailed logs
        with open(developer_log_file, 'w') as f:
            json.dump(detailed_logs, f, indent=2)
        
        # Also log to server log with enhanced details
        server_logger.error(f"DOWNLOAD FAILED: {download_data.get('title')} | "
                           f"Domain: {domain} | "
                           f"Error: {download_data.get('error')} | "
                           f"Retry #{download_data.get('retry_count', 0)} | "
                           f"URL: {url}")
        
        print(f" [!] ENHANCED LOGGING: Failed download details saved for developers")
        
    except Exception as e:
        print(f" [!] Error in enhanced logging: {e}")
        server_logger.error(f"Error in enhanced logging: {e}")
    
    save_failed_downloads()

def remove_failed_download(download_id):
    """Remove a failed download from the persistent store."""
    global failed_downloads
    if download_id in failed_downloads:
        del failed_downloads[download_id]
        save_failed_downloads()
        return True
    return False

def find_existing_failed_download(url):
    """Check if a URL already exists in failed downloads."""
    global failed_downloads
    for download_id, failed_download in failed_downloads.items():
        if failed_download.get('url') == url:
            return download_id, failed_download
    return None, None

def log_duplicate_attempt(url, title, existing_download_id, existing_download):
    """Log a duplicate download attempt for developer analysis."""
    try:
        os.makedirs('.logs', exist_ok=True)
        duplicate_log_file = '.logs/duplicate_attempts.json'
        
        # Load existing duplicate attempts
        duplicate_attempts = []
        if os.path.exists(duplicate_log_file):
            try:
                with open(duplicate_log_file, 'r') as f:
                    duplicate_attempts = json.load(f)
            except Exception:
                duplicate_attempts = []
        
        # Add new duplicate attempt
        duplicate_entry = {
            'timestamp': time.time(),
            'timestamp_human': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
            'attempted_url': url,
            'attempted_title': title,
            'existing_download_id': existing_download_id,
            'existing_title': existing_download.get('title'),
            'existing_error': existing_download.get('error'),
            'existing_failed_at': existing_download.get('failed_at'),
            'existing_retry_count': existing_download.get('retry_count', 0)
        }
        
        duplicate_attempts.append(duplicate_entry)
        
        # Keep only the last 100 attempts to prevent file from growing too large
        if len(duplicate_attempts) > 100:
            duplicate_attempts = duplicate_attempts[-100:]
        
        # Save duplicate attempts log
        with open(duplicate_log_file, 'w') as f:
            json.dump(duplicate_attempts, f, indent=2)
        
        # Also log to server log
        server_logger.warning(f"DUPLICATE ATTEMPT: URL {url} already failed previously. "
                             f"Original error: {existing_download.get('error')} "
                             f"Retry count: {existing_download.get('retry_count', 0)}")
        
        print(f" [!] DUPLICATE: URL already in failed downloads list")
        print(f" [!] Original title: {existing_download.get('title')}")
        print(f" [!] Original error: {existing_download.get('error')}")
        print(f" [!] Failed {existing_download.get('retry_count', 0)} times")
        
    except Exception as e:
        print(f" [!] Error logging duplicate attempt: {e}")
        server_logger.error(f"Error logging duplicate attempt: {e}")

def get_partial_files(download_id, title):
    """Get partial files (.part, .ytdl) for a download."""
    try:
        download_path = config.get_video_download_path()
        partial_files = []
        
        # Look for files with the download_id or title in name
        for file_name in os.listdir(download_path):
            if (download_id in file_name or 
                (title and any(word in file_name.lower() for word in title.lower().split() if len(word) > 3)) and
                (file_name.endswith('.part') or file_name.endswith('.ytdl') or file_name.endswith('.temp'))):
                partial_files.append(os.path.join(download_path, file_name))
        
        return partial_files
    except Exception as e:
        print(f" [!] Error finding partial files: {e}")
        return []

def cleanup_partial_files(download_id, title):
    """Remove partial files for a download."""
    try:
        partial_files = get_partial_files(download_id, title)
        removed_files = []
        
        for file_path in partial_files:
            try:
                os.remove(file_path)
                removed_files.append(os.path.basename(file_path))
                print(f" [+] Removed partial file: {os.path.basename(file_path)}")
            except Exception as e:
                print(f" [!] Error removing {file_path}: {e}")
        
        return removed_files
    except Exception as e:
        print(f" [!] Error cleaning up partial files: {e}")
        return []

def find_matching_failed_download(filename):
    """Find a failed download that matches a partial file using multiple matching strategies."""
    global failed_downloads
    
    # Clean filename for comparison (remove extensions and special chars)
    clean_filename = filename.replace('.part', '').replace('.ytdl', '').replace('.temp', '').lower()
    clean_filename = re.sub(r'[^\w\s-]', '', clean_filename).strip()
    
    best_match = None
    best_similarity = 0
    
    print(f" [+] Searching for match to: '{clean_filename}'")
    
    for download_id, failed_download in failed_downloads.items():
        # Clean the failed download title for comparison
        clean_title = failed_download['title'].lower()
        clean_title = re.sub(r'[^\w\s-]', '', clean_title).strip()
        
        print(f" [+] Comparing with: '{clean_title}'")
        
        # Strategy 1: Exact match (after cleaning)
        if clean_filename == clean_title:
            print(f" [+] Exact match found!")
            return (download_id, failed_download)
        
        # Strategy 2: Substring containment (bidirectional)
        if clean_title in clean_filename or clean_filename in clean_title:
            similarity = 0.99
            print(f" [+] Substring match found (similarity: {similarity})")
        else:
            # Strategy 3: Word-based similarity
            filename_words = set(clean_filename.split())
            title_words = set(clean_title.split())
            
            if not filename_words or not title_words:
                continue
                
            # Calculate Jaccard similarity (intersection over union)
            intersection = len(filename_words.intersection(title_words))
            union = len(filename_words.union(title_words))
            similarity = intersection / union if union > 0 else 0
            
            print(f" [+] Word similarity: {similarity:.2f}")
        
        # Strategy 4: Check if most words from filename are in title (lowered threshold)
        if similarity == 0:  # Only if no other similarity found
            filename_words = set(clean_filename.split())
            title_words = set(clean_title.split())
            
            if filename_words and title_words:
                # Check what percentage of filename words are in title
                words_in_title = len(filename_words.intersection(title_words))
                filename_coverage = words_in_title / len(filename_words) if filename_words else 0
                
                # If 80%+ of filename words are in title, consider it a match
                if filename_coverage >= 0.8:
                    similarity = 0.85
                    print(f" [+] High filename coverage match: {filename_coverage:.2f}")
        
        # Update best match if this is better (lowered threshold to 80%)
        if similarity > best_similarity and similarity >= 0.80:
            best_similarity = similarity
            best_match = (download_id, failed_download)
            print(f" [+] New best match: {similarity:.2f}")
    
    if best_match:
        print(f" [+] Final match selected with similarity: {best_similarity:.2f}")
    else:
        print(f" [-] No match found (threshold: 0.80)")
        
    return best_match

def find_matching_active_download(filename):
    """Find an active download that matches a partial file using multiple matching strategies."""
    global active_downloads
    
    # Clean filename for comparison (remove extensions and special chars)
    clean_filename = filename.replace('.part', '').replace('.ytdl', '').replace('.temp', '').lower()
    clean_filename = re.sub(r'[^\w\s-]', '', clean_filename).strip()
    
    best_match = None
    best_similarity = 0
    
    print(f" [+] Searching active downloads for match to: '{clean_filename}'")
    
    # Load active downloads if they exist
    try:
        if os.path.exists(active_downloads_file):
            with open(active_downloads_file, 'r') as f:
                active_downloads_data = json.load(f)
        else:
            active_downloads_data = {}
    except Exception as e:
        print(f"Warning: Could not load active downloads data: {e}")
        active_downloads_data = {}
    
    # Also check currently active downloads in memory
    all_active = {}
    all_active.update(active_downloads_data)
    with download_lock:
        for did, progress in active_downloads.items():
            all_active[did] = {
                'url': progress.url,
                'title': progress.title,
                'retry_count': progress.retry_count,
                'open_folder': progress.open_folder
            }
    
    for download_id, active_download in all_active.items():
        if not active_download.get('url'):
            continue
            
        # Clean the active download title for comparison
        clean_title = active_download.get('title', '').lower()
        clean_title = re.sub(r'[^\w\s-]', '', clean_title).strip()
        
        print(f" [+] Comparing with active: '{clean_title}'")
        
        # Strategy 1: Exact match (after cleaning)
        if clean_filename == clean_title:
            print(f" [+] Exact match found in active downloads!")
            return (download_id, active_download)
        
        # Strategy 2: Substring containment (bidirectional)
        if clean_title in clean_filename or clean_filename in clean_title:
            similarity = 0.99
            print(f" [+] Substring match found in active (similarity: {similarity})")
        else:
            # Strategy 3: Word-based similarity
            filename_words = set(clean_filename.split())
            title_words = set(clean_title.split())
            
            if not filename_words or not title_words:
                continue
                
            # Calculate Jaccard similarity (intersection over union)
            intersection = len(filename_words.intersection(title_words))
            union = len(filename_words.union(title_words))
            similarity = intersection / union if union > 0 else 0
            
            print(f" [+] Word similarity: {similarity:.2f}")
        
        # Strategy 4: Check if most words from filename are in title
        if similarity == 0:  # Only if no other similarity found
            filename_words = set(clean_filename.split())
            title_words = set(clean_title.split())
            
            if filename_words and title_words:
                matching_words = len(filename_words.intersection(title_words))
                if matching_words >= len(filename_words) * 0.5:  # At least 50% of words match
                    similarity = 0.85
                    print(f" [+] Partial word match: {matching_words}/{len(filename_words)} words")
        
        # Use same lowered threshold as failed downloads (0.80)
        if similarity >= 0.80 and similarity > best_similarity:
            best_similarity = similarity
            best_match = (download_id, active_download)
            print(f" [+] New best active match: {similarity:.2f}")
    
    if best_match:
        print(f" [+] Final active match selected with similarity: {best_similarity:.2f}")
    else:
        print(f" [-] No active match found (threshold: 0.80)")
        
    return best_match

def get_video_duration(file_path):
    """Get video duration in seconds using ffprobe or fallback methods."""
    try:
        # Try using ffprobe first (most accurate)
        import subprocess
        result = subprocess.run([
            'ffprobe', '-v', 'quiet', '-show_entries', 
            'format=duration', '-of', 'csv=p=0', file_path
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout.strip():
            duration = float(result.stdout.strip())
            return round(duration)
    except (subprocess.SubprocessError, subprocess.TimeoutExpired, ValueError, FileNotFoundError) as e:
        pass
    
    try:
        # Fallback: try mediainfo if available
        result = subprocess.run([
            'mediainfo', '--Inform=General;%Duration%', file_path
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout.strip():
            duration_ms = float(result.stdout.strip())
            return round(duration_ms / 1000)  # Convert ms to seconds
    except (subprocess.SubprocessError, subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass
    
    try:
        # Another fallback: try using file size estimation (very rough)
        # Most videos are roughly 1MB per minute for standard quality
        file_size = os.path.getsize(file_path)
        if file_size > 10 * 1024 * 1024:  # Only for files > 10MB
            estimated_minutes = file_size / (1024 * 1024)  # Rough estimate
            if estimated_minutes < 300:  # Cap at 5 hours to avoid crazy estimates
                return round(estimated_minutes * 60)
    except Exception as e:
        # Silently fail for duration parsing as it's non-critical
        pass
    
    return None

def auto_cleanup_matching_partial_files(completed_title):
    """Automatically clean up partial files that match a completed download."""
    try:
        download_path = config.get_video_download_path()
        if not os.path.exists(download_path):
            return []
            
        removed_files = []
        clean_completed_title = completed_title.lower()
        clean_completed_title = re.sub(r'[^\w\s-]', '', clean_completed_title).strip()
        
        for filename in os.listdir(download_path):
            if filename.endswith('.part') or filename.endswith('.ytdl') or filename.endswith('.temp'):
                # Check if this partial file matches the completed download
                clean_filename = filename.replace('.part', '').replace('.ytdl', '').replace('.temp', '').lower()
                clean_filename = re.sub(r'[^\w\s-]', '', clean_filename).strip()
                
                # Calculate similarity
                filename_words = set(clean_filename.split())
                title_words = set(clean_completed_title.split())
                
                if not filename_words or not title_words:
                    continue
                    
                intersection = len(filename_words.intersection(title_words))
                union = len(filename_words.union(title_words))
                similarity = intersection / union if union > 0 else 0
                
                # Also check if the title is contained in filename or vice versa
                if clean_completed_title in clean_filename or clean_filename in clean_completed_title:
                    similarity = max(similarity, 0.98)
                
                if similarity >= 0.98:  # 98% match threshold
                    try:
                        file_path = os.path.join(download_path, filename)
                        os.remove(file_path)
                        removed_files.append(filename)
                        print(f" [+] Auto-cleaned matching partial file: {filename} (similarity: {similarity:.2%})")
                    except Exception as e:
                        print(f" [!] Error auto-cleaning partial file {filename}: {e}")
        
        return removed_files
    except Exception as e:
        print(f" [!] Error in auto_cleanup_matching_partial_files: {e}")
        return []

def setup_logging():
    """Set up circular buffer logging for the web server."""
    os.makedirs('.logs', exist_ok=True)
    
    # Create logger
    logger = logging.getLogger('quikvid_server')
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create rotating file handler (circular buffer)
    # 5MB max file size, keep 3 files (15MB total)
    file_handler = logging.handlers.RotatingFileHandler(
        '.logs/server.log',
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(logging.Formatter('%(message)s'))  # Simple console format
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Set up logging
server_logger = setup_logging()

class DownloadProgress:
    """Track download progress and status."""
    def __init__(self, download_id, url, title, retry_count=0):
        self.download_id = download_id
        self.url = url
        self.title = title
        self.status = 'preparing'  # preparing, downloading, processing, completed, error, cancelled, failed
        self.percent = 0.0
        self.speed = ''
        self.eta = ''
        self.error = None
        self.cancelled = False
        self.process = None
        self.download_thread = None
        self.start_time = time.time()
        self.retry_count = retry_count
        self.open_folder = True
        self.partial_files = []

class QuikvidHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Quikvid-DL API."""
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/status':
            self.send_json_response({'status': 'running', 'message': 'Quikvid-DL server is active'})
        elif parsed_path.path.startswith('/progress/'):
            download_id = parsed_path.path.split('/')[-1]
            self.handle_progress_request(download_id)
        elif parsed_path.path == '/current-folder':
            self.handle_current_folder_request()
        elif parsed_path.path == '/debug':
            self.handle_debug_request()
        elif parsed_path.path == '/uninstall':
            self.handle_uninstall_request()
        elif parsed_path.path == '/browse-downloads':
            self.handle_browse_downloads_request()
        elif parsed_path.path.startswith('/open-file/'):
            self.handle_open_file_request()
        elif parsed_path.path.startswith('/stream-video/'):
            self.handle_stream_video_request()
        elif parsed_path.path.startswith('/find-failed-download-for-file/'):
            filename = parsed_path.path.split('/')[-1]
            self.handle_find_failed_download_request(filename)
        elif parsed_path.path == '/favicon.ico':
            # Serve the new favicon.ico
            try:
                favicon_path = os.path.join(os.getcwd(), "static", "favicons", "favicon.ico")
                if os.path.exists(favicon_path):
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/x-icon')
                    self.send_header('Cache-Control', 'public, max-age=3600')
                    self.end_headers()
                    
                    with open(favicon_path, 'rb') as f:
                        self.wfile.write(f.read())
                else:
                    self.send_error(404, 'Favicon not found')
            except Exception as e:
                print(f"Error serving favicon: {e}")
                self.send_error(500, 'Internal server error')
        elif parsed_path.path.startswith('/static/'):
            # Serve static files (favicons, etc.)
            self.serve_static_file(parsed_path.path)
        elif parsed_path.path == '/':
            self.send_html_response(self.get_web_interface())
        else:
            self.send_error(404, 'Not Found')
    
    def do_POST(self):
        """Handle POST requests."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/download':
            self.handle_download_request()
        elif parsed_path.path.startswith('/cancel/'):
            download_id = parsed_path.path.split('/')[-1]
            self.handle_cancel_request(download_id)
        elif parsed_path.path.startswith('/retry/'):
            download_id = parsed_path.path.split('/')[-1]
            self.handle_retry_request(download_id)
        elif parsed_path.path.startswith('/delete/'):
            download_id = parsed_path.path.split('/')[-1]
            self.handle_delete_request(download_id)
        elif parsed_path.path.startswith('/clear/'):
            download_id = parsed_path.path.split('/')[-1]
            self.handle_clear_request(download_id)
        elif parsed_path.path.startswith('/delete-partial-file/'):
            filename = parsed_path.path.split('/')[-1]
            self.handle_delete_partial_file_request(filename)
        elif parsed_path.path.startswith('/find-failed-download-for-file/'):
            filename = parsed_path.path.split('/')[-1]
            self.handle_find_failed_download_request(filename)
        elif parsed_path.path == '/select-folder':
            self.handle_folder_selection_request()
        elif parsed_path.path == '/open-folder':
            self.handle_open_folder_request()
        elif parsed_path.path == '/stop-server':
            self.handle_stop_server_request()
        else:
            self.send_error(404, 'Not Found')
    
    def handle_progress_request(self, download_id):
        """Handle progress check requests."""
        with download_lock:
            if download_id not in active_downloads:
                self.send_json_response({'error': 'Download not found'}, status=404)
                return
            
            progress = active_downloads[download_id]
            self.send_json_response({
                'downloadId': download_id,
                'status': progress.status,
                'percent': progress.percent,
                'speed': progress.speed,
                'eta': progress.eta,
                'error': progress.error,
                'title': progress.title
            })
    
    def handle_retry_request(self, download_id):
        """Handle download retry requests."""
        try:
            # Check if it's a failed download
            if download_id in failed_downloads:
                failed_download = failed_downloads[download_id]
                print(f" [+] Retrying failed download: {failed_download['title']}")
                
                # Create new progress tracker with incremented retry count
                progress = DownloadProgress(
                    download_id, 
                    failed_download['url'], 
                    failed_download['title'], 
                    retry_count=failed_download['retry_count'] + 1
                )
                progress.open_folder = failed_download.get('open_folder', True)
                
                with download_lock:
                    active_downloads[download_id] = progress
                    save_active_downloads()
                
                # Remove from failed downloads (it will be re-added if it fails again)
                remove_failed_download(download_id)
                
                # Start download in background thread
                download_thread = threading.Thread(
                    target=self.download_video_with_progress,
                    args=(progress, progress.open_folder)
                )
                download_thread.daemon = True
                download_thread.start()
                
                self.send_json_response({
                    'success': True,
                    'message': 'Download retry started',
                    'downloadId': download_id,
                    'retry_count': progress.retry_count
                })
                
            elif download_id in active_downloads:
                # It's an active failed download
                progress = active_downloads[download_id]
                if progress.status == 'error':
                    print(f" [+] Retrying active failed download: {progress.title}")
                    
                    # Reset progress for retry
                    progress.status = 'preparing'
                    progress.percent = 0.0
                    progress.error = None
                    progress.retry_count += 1
                    
                    # Start download in background thread
                    download_thread = threading.Thread(
                        target=self.download_video_with_progress,
                        args=(progress, progress.open_folder)
                    )
                    download_thread.daemon = True
                    download_thread.start()
                    
                    self.send_json_response({
                        'success': True,
                        'message': 'Download retry started',
                        'downloadId': download_id,
                        'retry_count': progress.retry_count
                    })
                else:
                    self.send_json_response({
                        'success': False,
                        'error': 'Download is not in a failed state'
                    }, status=400)
            else:
                self.send_json_response({
                    'success': False,
                    'error': 'Download not found'
                }, status=404)
                
        except Exception as e:
            print(f" [!] Error retrying download: {e}")
            self.send_json_response({'success': False, 'error': str(e)}, status=500)

    def handle_delete_request(self, download_id):
        """Handle download deletion requests with partial file cleanup."""
        try:
            removed_files = []
            download_title = "Unknown"
            
            # Check active downloads first
            if download_id in active_downloads:
                progress = active_downloads[download_id]
                download_title = progress.title
                
                # Cancel if running
                if progress.status in ['preparing', 'downloading', 'processing']:
                    progress.cancelled = True
                    progress.status = 'cancelled'
                
                # Clean up partial files
                removed_files = cleanup_partial_files(download_id, progress.title)
                
                with download_lock:
                    del active_downloads[download_id]
                    save_active_downloads()
                    
            # Check failed downloads
            elif download_id in failed_downloads:
                failed_download = failed_downloads[download_id]
                download_title = failed_download['title']
                
                # Clean up partial files
                removed_files = cleanup_partial_files(download_id, failed_download['title'])
                
                # Remove from failed downloads store
                remove_failed_download(download_id)
            else:
                self.send_json_response({
                    'success': False,
                    'error': 'Download not found'
                }, status=404)
                return
            
            print(f" [+] Deleted download: {download_title}")
            if removed_files:
                print(f" [+] Cleaned up partial files: {', '.join(removed_files)}")
                
            self.send_json_response({
                'success': True,
                'message': f'Download deleted: {download_title}',
                'downloadId': download_id,
                'removedFiles': removed_files
            })
            
        except Exception as e:
            print(f" [!] Error deleting download: {e}")
            self.send_json_response({'success': False, 'error': str(e)}, status=500)

    def handle_clear_request(self, download_id):
        """Handle clear request for completed downloads (removes from list without deleting files)."""
        try:
            download_title = "Unknown"
            
            # Check active downloads first
            if download_id in active_downloads:
                progress = active_downloads[download_id]
                download_title = progress.title
                
                # Only allow clearing completed downloads
                if progress.status != 'completed':
                    self.send_json_response({
                        'success': False,
                        'error': 'Can only clear completed downloads'
                    }, status=400)
                    return
                
                with download_lock:
                    del active_downloads[download_id]
                    save_active_downloads()
                    
            # Check failed downloads  
            elif download_id in failed_downloads:
                failed_download = failed_downloads[download_id]
                download_title = failed_download['title']
                
                # Remove from failed downloads store
                remove_failed_download(download_id)
            else:
                self.send_json_response({
                    'success': False,
                    'error': 'Download not found'
                }, status=404)
                return
            
            print(f" [+] Cleared download from list: {download_title}")
                
            self.send_json_response({
                'success': True,
                'message': f'Download cleared: {download_title}',
                'downloadId': download_id
            })
            
        except Exception as e:
            print(f" [!] Error clearing download: {e}")
            self.send_json_response({'success': False, 'error': str(e)}, status=500)

    def handle_delete_partial_file_request(self, filename):
        """Handle deletion of individual partial files."""
        try:
            # Decode URL-encoded filename
            import urllib.parse
            filename = urllib.parse.unquote(filename)
            
            # Construct full file path
            downloads_path = config.get_video_download_path()
            file_path = os.path.join(downloads_path, filename)
            
            # Security check - ensure the file is in the downloads directory
            if not file_path.startswith(downloads_path):
                self.send_json_response({
                    'success': False,
                    'message': 'Invalid file path'
                }, status=400)
                return
            
            # Check if file exists
            if not os.path.exists(file_path):
                self.send_json_response({
                    'success': False,
                    'message': 'File not found'
                }, status=404)
                return
            
            # Verify it's actually a partial file
            if not filename.endswith(('.part', '.ytdl', '.temp')):
                self.send_json_response({
                    'success': False,
                    'message': 'Can only delete partial download files (.part, .ytdl, .temp)'
                }, status=400)
                return
            
            # Delete the file
            os.remove(file_path)
            
            print(f" [+] Deleted partial file: {filename}")
            
            self.send_json_response({
                'success': True,
                'message': f'Successfully deleted {filename}',
                'filename': filename
            })
            
        except Exception as e:
            print(f" [!] Error deleting partial file: {e}")
            self.send_json_response({
                'success': False,
                'message': f'Failed to delete file: {str(e)}'
            }, status=500)

    def handle_find_failed_download_request(self, filename):
        """Handle finding a failed download that matches a partial file."""
        try:
            # Decode URL-encoded filename
            import urllib.parse
            filename = urllib.parse.unquote(filename)
            
            print(f" [+] Looking for download matching: {filename}")
            
            # First check URL tracker for incomplete downloads
            tracker = get_tracker()
            url_match = tracker.find_by_partial_filename(filename)
            
            if url_match:
                url_track_id, url_data = url_match
                print(f" [+] Found matching URL in tracker: {url_data['title']}")
                
                # Convert to failed download format
                failed_download = {
                    'url': url_data['url'],
                    'title': url_data['title'],
                    'error': url_data.get('last_error', 'Download incomplete'),
                    'retry_count': url_data.get('attempts', 0),
                    'open_folder': True
                }
                
                self.send_json_response({
                    'success': True,
                    'failed_download': failed_download,
                    'download_id': url_track_id,
                    'filename': filename
                })
                return
            
            # Fallback to old system for compatibility
            match_result = find_matching_failed_download(filename)
            
            if match_result:
                download_id, failed_download = match_result
                print(f" [+] Found matching failed download: {failed_download['title']} (ID: {download_id})")
                
                self.send_json_response({
                    'success': True,
                    'failed_download': failed_download,
                    'download_id': download_id,
                    'filename': filename
                })
            else:
                # Also check active downloads (in case of recent crash/restart)
                print(f" [+] Checking active downloads for: {filename}")
                match_result = find_matching_active_download(filename)
                
                if match_result:
                    download_id, active_download = match_result
                    print(f" [+] Found matching active download: {active_download['title']} (ID: {download_id})")
                    
                    # Convert to failed download format
                    failed_download = {
                        'url': active_download['url'],
                        'title': active_download.get('title', 'Unknown'),
                        'error': 'Download interrupted',
                        'retry_count': active_download.get('retry_count', 0),
                        'open_folder': active_download.get('open_folder', True)
                    }
                    
                    self.send_json_response({
                        'success': True,
                        'failed_download': failed_download,
                        'download_id': download_id,
                        'filename': filename
                    })
                else:
                    print(f" [-] No matching download found for: {filename}")
                    self.send_json_response({
                        'success': False,
                        'message': 'No matching download found',
                        'filename': filename
                    })
                
        except Exception as e:
            print(f" [!] Error finding failed download: {e}")
            self.send_json_response({
                'success': False,
                'message': f'Error finding failed download: {str(e)}'
            }, status=500)

    def handle_cancel_request(self, download_id):
        """Handle download cancellation requests."""
        with download_lock:
            if download_id not in active_downloads:
                self.send_json_response({'error': 'Download not found'}, status=404)
                return
            
            progress = active_downloads[download_id]
            progress.cancelled = True
            progress.status = 'cancelled'
            
            print(f" [!] Cancelling download: {progress.title}")
            
            # Try to interrupt the download thread
            if hasattr(progress, 'download_thread') and progress.download_thread:
                try:
                    # The yt-dlp process will check progress.cancelled in the progress hook
                    print(f" [!] Marking download as cancelled, thread will stop on next progress check")
                except Exception as e:
                    print(f" [!] Error interrupting thread: {e}")
            
            # Try to terminate the process if it exists
            if hasattr(progress, 'process') and progress.process:
                try:
                    progress.process.terminate()
                    # Give it a moment to terminate gracefully
                    time.sleep(1)
                    if progress.process.poll() is None:
                        progress.process.kill()
                        print(f" [!] Killed stubborn process for: {progress.title}")
                except Exception as e:
                    print(f" [!] Error terminating process: {e}")
            
            print(f" [!] Download cancellation initiated: {progress.title}")
            self.send_json_response({'success': True, 'message': 'Download cancellation initiated'})
            
            # Clean up any partial files
            self.cleanup_partial_files(progress)
    
    def handle_debug_request(self):
        """Handle debug requests to show all active downloads and failed downloads."""
        with download_lock:
            # Count only truly active downloads (preparing, downloading, processing)
            actual_active_count = sum(1 for progress in active_downloads.values() 
                                    if progress.status in ['preparing', 'downloading', 'processing'])
            
            debug_info = {
                'active_downloads_count': actual_active_count,
                'failed_downloads_count': len(failed_downloads),
                'downloads': []
            }
            
            # Track seen titles/URLs to prevent duplicates
            seen_items = set()
            
            # Add active downloads
            for download_id, progress in active_downloads.items():
                # Create unique key based on title and URL
                item_key = (progress.title, progress.url)
                if item_key in seen_items:
                    continue
                seen_items.add(item_key)
                
                download_info = {
                    'downloadId': download_id,
                    'title': progress.title,
                    'url': progress.url,
                    'status': progress.status,
                    'percent': progress.percent,
                    'speed': progress.speed,
                    'eta': progress.eta,
                    'error': progress.error,
                    'cancelled': progress.cancelled,
                    'has_thread': hasattr(progress, 'download_thread') and progress.download_thread is not None,
                    'thread_alive': hasattr(progress, 'download_thread') and progress.download_thread and progress.download_thread.is_alive(),
                    'start_time': progress.start_time,
                    'runtime_seconds': time.time() - progress.start_time,
                    'retry_count': getattr(progress, 'retry_count', 0),
                    'is_failed': False
                }
                debug_info['downloads'].append(download_info)
            
            # Add failed downloads that aren't currently active and not duplicates
            for download_id, failed_download in failed_downloads.items():
                if download_id not in active_downloads:
                    # Create unique key based on title and URL
                    item_key = (failed_download['title'], failed_download['url'])
                    if item_key in seen_items:
                        continue
                    seen_items.add(item_key)
                    download_info = {
                        'downloadId': download_id,
                        'title': failed_download['title'],
                        'url': failed_download['url'],
                        'status': 'failed',
                        'percent': 0.0,
                        'speed': '',
                        'eta': '',
                        'error': failed_download['error'],
                        'cancelled': False,
                        'has_thread': False,
                        'thread_alive': False,
                        'start_time': failed_download.get('failed_at', time.time()),
                        'runtime_seconds': 0,
                        'retry_count': failed_download.get('retry_count', 0),
                        'is_failed': True
                    }
                    debug_info['downloads'].append(download_info)
            
            self.send_json_response(debug_info)
    
    def handle_uninstall_request(self):
        """Handle uninstall requests - opens Finder to uninstall script location."""
        import subprocess
        import os
        
        try:
            # Try multiple possible locations for the uninstall script
            possible_paths = [
                # First try the macos-installer directory (from VidSnatch-Installer.zip)
                os.path.abspath(os.path.join(os.path.dirname(__file__), 'macos-installer', 'uninstall.sh')),
                # Try the command file in macos-installer
                os.path.abspath(os.path.join(os.path.dirname(__file__), 'macos-installer', '🗑️ Uninstall VidSnatch.command')),
                # Fallback to the source directory
                os.path.abspath(os.path.join(os.path.dirname(__file__), 'uninstall-vidsnatch.sh'))
            ]
            
            script_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    script_path = path
                    break
            
            if script_path:
                # Open Finder to the directory containing the uninstall script
                subprocess.run(['open', '-R', script_path], check=True)
                self.send_json_response({
                    'status': 'success', 
                    'message': 'Finder opened to uninstall script location',
                    'script_path': script_path
                })
            else:
                self.send_json_response({
                    'status': 'error', 
                    'message': f'Uninstall script not found. Checked paths: {", ".join(possible_paths)}',
                    'checked_paths': possible_paths
                })
        except Exception as e:
            self.send_json_response({
                'status': 'error', 
                'message': f'Failed to open uninstall location: {str(e)}'
            })
    
    def handle_browse_downloads_request(self):
        """Handle requests to browse downloads folder."""
        try:
            # Get current download folder
            folder_path = config.get_video_download_path()
            
            if not os.path.exists(folder_path):
                self.send_json_response({
                    'status': 'error',
                    'message': 'Downloads folder not found',
                    'path': folder_path
                })
                return
            
            files = []
            file_metadata = get_file_metadata()
            
            # Get list of files currently being downloaded to exclude them
            actively_downloading_files = set()
            with download_lock:
                for progress in active_downloads.values():
                    if progress.status in ['preparing', 'downloading', 'processing']:
                        # Try to extract filename from the progress object or URL
                        if hasattr(progress, 'filename') and progress.filename:
                            actively_downloading_files.add(progress.filename)
                        elif hasattr(progress, 'title') and progress.title:
                            # Create potential filename from title (common video extensions)
                            for ext in ['.mp4', '.mkv', '.webm', '.avi', '.mov', '.m4v']:
                                potential_filename = f"{progress.title}{ext}"
                                actively_downloading_files.add(potential_filename)
            
            try:
                for item in sorted(os.listdir(folder_path)):
                    # Skip hidden files and system files
                    if item.startswith('.') or item.startswith('~'):
                        continue
                    
                    # Skip files that are currently being downloaded
                    if item in actively_downloading_files:
                        continue
                    
                    # Skip partial download files (common partial extensions)
                    if item.endswith(('.part', '.ytdl', '.temp', '.download', '.crdownload')):
                        continue
                        
                    item_path = os.path.join(folder_path, item)
                    if os.path.isfile(item_path):
                        # Get file info
                        stat = os.stat(item_path)
                        size = stat.st_size
                        modified = stat.st_mtime
                        
                        # Format size
                        if size < 1024:
                            size_str = f"{size} B"
                        elif size < 1024*1024:
                            size_str = f"{size/1024:.1f} KB"
                        elif size < 1024*1024*1024:
                            size_str = f"{size/(1024*1024):.1f} MB"
                        else:
                            size_str = f"{size/(1024*1024*1024):.1f} GB"
                        
                        # Get video duration if it's a video file
                        duration = None
                        if item.lower().endswith(('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v')):
                            duration = get_video_duration(item_path)
                        
                        # Get file metadata (URL and title)
                        metadata = file_metadata.get_file_metadata(item)
                        source_url = metadata.get('url', '') if metadata else ''
                        
                        files.append({
                            'name': item,
                            'size': size_str,
                            'modified': modified,
                            'path': item_path,
                            'duration': duration,
                            'url': source_url
                        })
            except PermissionError:
                pass
            
            self.send_json_response({
                'status': 'success',
                'folder': folder_path,
                'files': files
            })
            
        except Exception as e:
            self.send_json_response({
                'status': 'error',
                'message': f'Failed to browse downloads: {str(e)}'
            })
    
    def serve_static_file(self, path):
        """Serve static files (favicons, etc.)."""
        try:
            # Security: prevent directory traversal
            if '..' in path or path.startswith('//'):
                self.send_error(403, 'Access denied')
                return
            
            # Map URL path to file path - use current working directory for static files
            static_root = os.path.join(os.getcwd(), 'static')
            file_path = os.path.join(static_root, path.lstrip('/static/'))
            
            # Ensure the file is within the static directory
            if not os.path.abspath(file_path).startswith(os.path.abspath(static_root)):
                self.send_error(403, 'Access denied')
                return
            
            if not os.path.exists(file_path):
                self.send_error(404, 'File not found')
                return
            
            # Determine content type
            content_type = 'application/octet-stream'
            if file_path.endswith('.png'):
                content_type = 'image/png'
            elif file_path.endswith('.ico'):
                content_type = 'image/x-icon'
            elif file_path.endswith('.webmanifest'):
                content_type = 'application/manifest+json'
            elif file_path.endswith('.svg'):
                content_type = 'image/svg+xml'
            
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()
            
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
                
        except Exception as e:
            print(f"Error serving static file {path}: {e}")
            self.send_error(500, 'Internal server error')
    
    def handle_open_file_request(self):
        """Handle requests to open a specific file."""
        try:
            # Extract filename from URL and properly decode it
            import urllib.parse
            encoded_filename = self.path.replace('/open-file/', '')
            filename = urllib.parse.unquote(encoded_filename)
            
            # Join with download path (don't use basename as it strips slashes in filenames)
            download_path = config.get_video_download_path()
            file_path = os.path.join(download_path, filename)
            
            # Security check - ensure the resolved path is within the download directory
            file_path = os.path.abspath(file_path)
            download_path = os.path.abspath(download_path)
            if not file_path.startswith(download_path):
                self.send_json_response({
                    'status': 'error',
                    'message': 'Access denied'
                })
                return
            
            if os.path.exists(file_path):
                # Open file with default application
                subprocess.run(['open', file_path], check=True)
                self.send_json_response({
                    'status': 'success',
                    'message': f'Opened {os.path.basename(file_path)}'
                })
            else:
                self.send_json_response({
                    'status': 'error',
                    'message': 'File not found'
                })
                
        except Exception as e:
            self.send_json_response({
                'status': 'error',
                'message': f'Failed to open file: {str(e)}'
            })
    
    def handle_stream_video_request(self):
        """Handle video streaming requests with range support for video players."""
        try:
            # Extract filename from URL and properly decode it
            import urllib.parse
            encoded_filename = self.path.replace('/stream-video/', '')
            filename = urllib.parse.unquote(encoded_filename)
            
            # Don't use basename as it strips content before slashes in the filename
            # Just join with the download path directly
            download_path = config.get_video_download_path()
            file_path = os.path.join(download_path, filename)
            
            # Security check - ensure the resolved path is within the download directory
            # This prevents directory traversal attacks
            file_path = os.path.abspath(file_path)
            download_path = os.path.abspath(download_path)
            if not file_path.startswith(download_path):
                self.send_error(403, 'Access denied')
                return
            
            if not os.path.exists(file_path):
                self.send_error(404, 'Video file not found')
                return
            
            # Get file info
            file_size = os.path.getsize(file_path)
            
            # Check if client requested a range (for video seeking)
            range_header = self.headers.get('Range')
            
            if range_header:
                # Parse range header (e.g., "bytes=0-1023")
                try:
                    range_match = range_header.replace('bytes=', '').split('-')
                    start = int(range_match[0]) if range_match[0] else 0
                    end = int(range_match[1]) if range_match[1] else file_size - 1
                    
                    # Ensure valid range
                    start = max(0, start)
                    end = min(file_size - 1, end)
                    content_length = end - start + 1
                    
                    # Send partial content response
                    self.send_response(206)  # Partial Content
                    self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                    self.send_header('Accept-Ranges', 'bytes')
                    self.send_header('Content-Length', str(content_length))
                    
                except (ValueError, IndexError):
                    # Invalid range, send full file
                    start = 0
                    end = file_size - 1
                    content_length = file_size
                    self.send_response(200)
                    self.send_header('Content-Length', str(content_length))
            else:
                # No range requested, send full file
                start = 0
                end = file_size - 1
                content_length = file_size
                self.send_response(200)
                self.send_header('Content-Length', str(content_length))
            
            # Set appropriate headers for video streaming
            if filename.lower().endswith('.mp4'):
                self.send_header('Content-Type', 'video/mp4')
            elif filename.lower().endswith('.webm'):
                self.send_header('Content-Type', 'video/webm')
            elif filename.lower().endswith('.avi'):
                self.send_header('Content-Type', 'video/avi')
            elif filename.lower().endswith('.mkv'):
                self.send_header('Content-Type', 'video/x-matroska')
            elif filename.lower().endswith('.mov'):
                self.send_header('Content-Type', 'video/quicktime')
            else:
                self.send_header('Content-Type', 'video/mp4')  # Default
            
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Stream the file content
            with open(file_path, 'rb') as f:
                f.seek(start)
                remaining = content_length
                chunk_size = 8192
                
                while remaining > 0:
                    chunk = f.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    
                    try:
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                    except (ConnectionResetError, BrokenPipeError):
                        # Client disconnected
                        break
                        
        except Exception as e:
            print(f" [!] Error streaming video: {e}")
            try:
                self.send_error(500, f'Error streaming video: {str(e)}')
            except Exception as send_error:
                print(f"Warning: Could not send error response (connection likely closed): {send_error}")
    
    def handle_stop_server_request(self):
        """Handle server stop requests."""
        try:
            print(" [!] Shutdown request received from extension")
            self.send_json_response({
                'success': True,
                'message': 'Server shutdown initiated'
            })
            
            # Schedule server shutdown after sending response
            def shutdown_server():
                time.sleep(1)  # Give time for response to be sent
                print(" [+] Shutting down server...")
                
                # Cancel all active downloads
                with download_lock:
                    for download_id, progress in list(active_downloads.items()):
                        if progress.status in ['preparing', 'downloading', 'processing']:
                            progress.cancelled = True
                            progress.status = 'cancelled'
                    save_active_downloads()
                
                # Terminate all child processes
                import signal
                import os
                import sys
                
                # Send termination signal to entire process group
                try:
                    os.killpg(os.getpgid(os.getpid()), signal.SIGTERM)
                except Exception as e:
                    print(f"Warning: Could not kill process group during shutdown: {e}")
                
                # Exit the process
                sys.exit(0)
            
            shutdown_thread = threading.Thread(target=shutdown_server)
            shutdown_thread.daemon = True
            shutdown_thread.start()
            
        except Exception as e:
            print(f" [!] Error in stop server request: {e}")
            self.send_json_response({'error': str(e)}, status=500)
    
    def cleanup_partial_files(self, progress):
        """Clean up partial download files."""
        try:
            download_path = config.get_video_download_path()
            # Look for files that might be from this download
            for filename in os.listdir(download_path):
                if filename.endswith('.part') or filename.endswith('.tmp'):
                    file_path = os.path.join(download_path, filename)
                    # Check if file was created recently (within last few minutes)
                    if time.time() - os.path.getctime(file_path) < 300:  # 5 minutes
                        try:
                            os.remove(file_path)
                            print(f" [+] Cleaned up partial file: {filename}")
                        except Exception as e:
                            print(f"Warning: Could not remove partial file {filename}: {e}")
        except Exception as e:
            print(f" [!] Error cleaning up files: {e}")
    
    def handle_current_folder_request(self):
        """Handle request for current download folder."""
        try:
            current_path = config.get_video_download_path()
            self.send_json_response({
                'status': 'success',
                'folder': current_path,
                'path': current_path  # Keep both for backward compatibility
            })
        except Exception as e:
            print(f" [!] Error getting current folder: {e}")
            self.send_json_response({'status': 'error', 'error': str(e)}, status=500)
    
    def handle_folder_selection_request(self):
        """Handle folder selection request."""
        try:
            import modules.folderSelector as folderSelector
            import modules.settings as settings
            
            print(" [+] Opening folder selection dialog...")
            selected_folder = folderSelector.select_download_folder()
            
            if selected_folder:
                settings.set_download_path(selected_folder)
                print(f" [+] Download folder changed to: {selected_folder}")
                self.send_json_response({
                    'success': True,
                    'path': selected_folder
                })
            else:
                print(" [!] Folder selection cancelled")
                self.send_json_response({
                    'success': False,
                    'cancelled': True
                })
                
        except Exception as e:
            print(f" [!] Error in folder selection: {e}")
            self.send_json_response({'error': str(e)}, status=500)
    
    def handle_open_folder_request(self):
        """Handle request to open the download folder."""
        try:
            download_path = config.get_video_download_path()
            
            print(f" [+] Opening download folder: {download_path}")
            
            # Open folder using system-specific command
            if sys.platform == 'darwin':  # macOS
                subprocess.run(['open', download_path], check=True)
            elif sys.platform == 'win32':  # Windows
                subprocess.run(['explorer', download_path], check=True)
            else:  # Linux and other Unix-like systems
                subprocess.run(['xdg-open', download_path], check=True)
            
            self.send_json_response({
                'success': True,
                'message': 'Folder opened successfully'
            })
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to open folder: {e}"
            print(f" [!] {error_msg}")
            self.send_json_response({'error': error_msg}, status=500)
        except Exception as e:
            error_msg = f"Error opening folder: {e}"
            print(f" [!] {error_msg}")
            self.send_json_response({'error': error_msg}, status=500)
    
    def handle_download_request(self):
        """Handle download requests from Chrome extension."""
        try:
            # Get request body
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            # Parse JSON data
            data = json.loads(post_data.decode('utf-8'))
            url = data.get('url')
            raw_title = data.get('title', 'Unknown')
            # Clean the title to remove "NA - " and other unwanted prefixes
            import modules.utilities as utilities
            title = utilities.clean_video_title(raw_title)
            open_folder = data.get('openFolder', True)
            
            if not url:
                self.send_json_response({'error': 'No URL provided'}, status=400)
                return
            
            # Check for duplicate URL in failed downloads
            existing_download_id, existing_download = find_existing_failed_download(url)
            if existing_download_id:
                # Log the duplicate attempt for developer analysis
                log_duplicate_attempt(url, title, existing_download_id, existing_download)
                
                # Instead of creating a new download, increment retry count and update the existing one
                existing_download['retry_count'] = existing_download.get('retry_count', 0) + 1
                existing_download['last_retry_attempt'] = time.time()
                existing_download['last_retry_title'] = title  # Update title in case it changed
                save_failed_downloads()
                
                # Return a response indicating this is a retry of an existing failed download
                self.send_json_response({
                    'success': False,
                    'is_duplicate': True,
                    'message': f'This URL already failed {existing_download["retry_count"]} time(s). Original error: {existing_download.get("error", "Unknown error")}',
                    'existing_download_id': existing_download_id,
                    'original_error': existing_download.get('error'),
                    'retry_count': existing_download['retry_count'],
                    'url': url,
                    'title': title
                })
                return
            
            # Generate unique download ID
            download_id = str(uuid.uuid4())
            
            # Track this URL in the URL tracker
            tracker = get_tracker()
            url_track_id = tracker.add_url(url, title)
            
            # Create progress tracker
            progress = DownloadProgress(download_id, url, title)
            progress.url_track_id = url_track_id
            
            with download_lock:
                active_downloads[download_id] = progress
                save_active_downloads()
            
            server_logger.info(f"Chrome Extension Request: {title}")
            server_logger.info(f"URL: {url}")
            server_logger.info(f"Download ID: {download_id}")
            print(f" [+] Chrome Extension Request: {title}")
            print(f" [+] URL: {url}")
            print(f" [+] Download ID: {download_id}")
            
            # Start download in background thread
            download_thread = threading.Thread(
                target=self.download_video_with_progress,
                args=(progress, open_folder)
            )
            download_thread.daemon = True
            download_thread.start()
            
            # Return immediate response with download ID
            self.send_json_response({
                'success': True,
                'message': 'Download started',
                'downloadId': download_id,
                'url': url,
                'title': title
            })
            
        except json.JSONDecodeError:
            self.send_json_response({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            print(f" [!] Error handling download request: {e}")
            self.send_json_response({'error': str(e)}, status=500)
    
    def download_video_with_progress(self, progress, open_folder):
        """Download video with progress tracking."""
        try:
            download_path = config.get_video_download_path()
            
            # Ensure download directory exists
            os.makedirs(download_path, exist_ok=True)
            
            progress.status = 'preparing'
            progress.percent = 5.0
            print(f" [+] Starting download: {progress.title}")
            print(f" [+] URL: {progress.url}")
            
            # Store the current thread so we can interrupt it
            progress.download_thread = threading.current_thread()
            
            try:
                print(f" [+] Creating yt-dlp instance...")
                progress.percent = 10.0
                
                # Create yt-dlp options with progress hook and anti-detection settings
                ydl_opts = {
                    'outtmpl': os.path.join(download_path, config.DEFAULT_OUTPUT_TEMPLATE),
                    'progress_hooks': [lambda d: self.progress_hook(d, progress)],
                    'socket_timeout': 180,  # 3 minutes socket timeout for slow CDNs
                    'retries': 5,  # Retry 5 times on failure
                    'fragment_retries': 5,  # Retry fragments 5 times
                    'file_access_retries': 3,  # Retry file access
                    'verbose': True,  # Add verbose logging
                    'no_warnings': False,  # Show warnings
                    
                    # Anti-detection measures
                    'sleep_interval_requests': 2,  # Sleep 2 seconds between requests
                    'sleep_interval_subtitles': 1,  # Sleep 1 second between subtitle requests
                    'sleep_interval': 1,  # General sleep interval
                    
                    # Realistic browser headers to avoid detection
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                        'Sec-Fetch-User': '?1',
                        'Cache-Control': 'max-age=0',
                        'Referer': progress.url,  # Set referer to the video page
                    },
                    
                    # Cookie handling for session management
                    'cookiefile': None,  # Don't save cookies to file
                    'cookiesfrombrowser': None,  # Don't use browser cookies
                    
                    # Additional anti-detection
                    'no_check_certificate': False,  # Verify SSL certificates
                    'prefer_insecure': False,  # Prefer HTTPS
                    'geo_bypass': True,  # Try to bypass geo-restrictions
                    'geo_bypass_country': 'US',  # Pretend to be in US
                    
                    # CDN-specific optimizations
                    'external_downloader_args': {
                        'default': ['--retry-connrefused', '--retry', '5', '--timeout', '300', '--limit-rate', '1M']
                    }
                }
                
                # Apply site-specific settings for better compatibility
                if 'youtube.com' in progress.url or 'youtu.be' in progress.url:
                    server_logger.info(f"Detected YouTube URL, applying specific configuration")
                    print(f" [+] Detected YouTube URL, applying YouTube-specific configuration...")
                    ydl_opts['extractor_args'] = {
                        'youtube': {
                            'player_client': ['android'],  # Use Android client for better compatibility
                        }
                    }
                elif 'pornhub.com' in progress.url:
                    server_logger.info(f"Detected Pornhub URL, applying specific configuration")
                    print(f" [+] Detected Pornhub URL, applying Pornhub-specific configuration...")
                    # Add more aggressive extraction options for Pornhub
                    ydl_opts.update({
                        'extractor_args': {
                            'pornhub': {
                                'cookiesfrombrowser': None,
                            }
                        },
                        # More aggressive retry settings for problematic sites
                        'retries': 10,
                        'fragment_retries': 10,
                        # Try to bypass potential blocks
                        'sleep_interval_requests': 3,
                        # Use different user agent
                        'http_headers': {
                            **ydl_opts['http_headers'],
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                            'Accept': '*/*',
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Referer': 'https://www.pornhub.com/',
                        }
                    })
                elif 'xhamster.com' in progress.url:
                    server_logger.info(f"Detected XHamster URL, applying specific configuration")
                    print(f" [+] Detected XHamster URL, applying XHamster-specific configuration...")
                    # Add XHamster-specific configuration to handle title extraction issues
                    ydl_opts.update({
                        'retries': 15,
                        'fragment_retries': 15,
                        'sleep_interval_requests': 2,
                        'socket_timeout': 300,
                        'http_headers': {
                            **ydl_opts['http_headers'],
                            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                            'Accept-Language': 'en-us,en;q=0.5',
                            'Accept-Encoding': 'gzip,deflate',
                            'Connection': 'keep-alive',
                            'Upgrade-Insecure-Requests': '1',
                            'Referer': 'https://xhamster.com/',
                        },
                        # Disable SSL verification if needed and use alternate extraction
                        'nocheckcertificate': True,
                        'ignoreerrors': False,
                        'no_warnings': False,
                    })
                elif 'eporner.com' in progress.url:
                    server_logger.info(f"Detected Eporner URL, applying specific configuration")
                    print(f" [+] Detected Eporner URL, applying Eporner-specific configuration...")
                    # Add Eporner-specific configuration to handle hash extraction issues
                    ydl_opts.update({
                        'retries': 20,
                        'fragment_retries': 20,
                        'sleep_interval_requests': 3,
                        'socket_timeout': 300,
                        'http_headers': {
                            **ydl_opts['http_headers'],
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Accept-Encoding': 'gzip, deflate, br',
                            'Connection': 'keep-alive',
                            'Upgrade-Insecure-Requests': '1',
                            'Sec-Fetch-Dest': 'document',
                            'Sec-Fetch-Mode': 'navigate',
                            'Sec-Fetch-Site': 'none',
                            'Sec-Fetch-User': '?1',
                            'Cache-Control': 'max-age=0',
                            'Referer': 'https://www.eporner.com/',
                        },
                        'nocheckcertificate': False,
                        'ignoreerrors': True,  # Try to continue on errors
                        'no_warnings': False,
                        'writesubtitles': False,
                        'writeautomaticsub': False,
                    })
                
                print(f" [+] yt-dlp options configured")
                progress.percent = 15.0
                
                print(f" [+] Initializing YoutubeDL instance...")
                
                # Download with yt-dlp
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    if progress.cancelled:
                        print(f" [!] Download cancelled before start: {progress.title}")
                        return
                    
                    print(f" [+] YoutubeDL instance created successfully")
                    progress.status = 'downloading'
                    progress.percent = 20.0
                    
                    print(f" [+] Starting extract_info for URL: {progress.url}")
                    
                    # This is where it might hang - let's add a timeout mechanism
                    info = ydl.extract_info(progress.url, download=False)  # First just get info
                    # Clean the extracted title
                    import modules.utilities as utilities
                    raw_extracted_title = info.get('title', 'Unknown')
                    cleaned_title = utilities.clean_video_title(raw_extracted_title)
                    print(f" [+] Successfully extracted video info: {cleaned_title}")
                    # Update progress title with cleaned version
                    progress.title = cleaned_title
                    progress.percent = 50.0
                    
                    if progress.cancelled:
                        print(f" [!] Download cancelled after info extraction: {progress.title}")
                        return
                    
                    print(f" [+] Beginning actual download...")
                    ydl.extract_info(progress.url, download=True)  # Now actually download
                    print(f" [+] Download completed successfully: {progress.title}")
                    
            except yt_dlp.utils.ExtractorError as e:
                print(f" [!] Extractor error: {e}")
                # Try fallback approach for XHamster
                if 'xhamster.com' in progress.url and ('unable to download video data' in str(e).lower() or 'unable to extract title' in str(e).lower()):
                    print(f" [+] Attempting manual XHamster extraction...")
                    try:
                        import requests
                        import re
                        
                        # Get page content
                        response = requests.get(progress.url, 
                            headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                                'Accept-Language': 'en-US,en;q=0.9',
                            },
                            timeout=30)
                        
                        # Extract M3U8 video URL patterns from XHamster
                        m3u8_patterns = [
                            r'video-cf\.xhcdn\.com[^"\']*\.m3u8[^"\']*',
                            r'preload[^>]*href=["\']([^"\']*\.m3u8[^"\']*)["\']',
                            r'"file"\s*:\s*"([^"]+\.m3u8[^"]*)"',
                        ]
                        
                        video_url = None
                        for pattern in m3u8_patterns:
                            matches = re.findall(pattern, response.text, re.IGNORECASE)
                            if matches:
                                video_url = matches[0] if isinstance(matches[0], str) else matches[0]
                                # Ensure URL is properly formatted
                                if not video_url.startswith('http'):
                                    video_url = 'https://' + video_url
                                break
                        
                        # Extract title from page
                        title_match = re.search(r'<title[^>]*>([^<]+)</title>', response.text, re.IGNORECASE)
                        video_title = "XHamster_Video"
                        if title_match:
                            title = title_match.group(1)
                            # Clean title for filename
                            video_title = utilities.clean_video_title(title.split(' - ')[0])
                            progress.title = video_title  # Update progress title
                        
                        if video_url:
                            print(f" [+] Found direct M3U8 URL, downloading...")
                            
                            # Create options for M3U8 download
                            direct_opts = {
                                'outtmpl': os.path.join(config.get_video_download_path(), f'{video_title}.%(ext)s'),
                                'progress_hooks': [lambda d: self.progress_hook(d, progress)],
                                'http_headers': {
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                                    'Referer': 'https://xhamster.com/',
                                }
                            }
                            
                            with yt_dlp.YoutubeDL(direct_opts) as direct_ydl:
                                direct_ydl.extract_info(video_url, download=True)
                            
                            print(f" [+] Manual XHamster extraction successful!")
                            return  # Success, exit the function
                        else:
                            print(f" [!] Could not find M3U8 URL in page content")
                            
                    except Exception as manual_e:
                        print(f" [!] Manual XHamster extraction failed: {manual_e}")
                        # Continue to try other fallbacks
                
                # Try fallback approach for Pornhub
                elif 'pornhub.com' in progress.url and 'Unable to extract title' in str(e):
                    print(f" [+] Attempting Pornhub fallback extraction...")
                    try:
                        fallback_opts = {
                            **ydl_opts,
                            'format': 'best',
                            'ignoreerrors': False,
                            'http_headers': {
                                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                                'Accept-Language': 'en-us,en;q=0.5',
                                'Accept-Encoding': 'gzip,deflate',
                                'Connection': 'keep-alive',
                                'Upgrade-Insecure-Requests': '1',
                            }
                        }
                        with yt_dlp.YoutubeDL(fallback_opts) as fallback_ydl:
                            info = fallback_ydl.extract_info(progress.url, download=False)
                            print(f" [+] Fallback extraction successful: {info.get('title', 'Unknown')}")
                            fallback_ydl.extract_info(progress.url, download=True)
                            print(f" [+] Fallback download completed successfully")
                            return  # Success, exit the function
                    except Exception as fallback_e:
                        print(f" [!] Fallback also failed: {fallback_e}")
                        raise e  # Raise original error
                else:
                    raise
            except yt_dlp.utils.DownloadError as e:
                print(f" [!] Download error: {e}")
                # Try manual extraction for XHamster on download errors (like HTTP 404)
                if 'xhamster.com' in progress.url and ('unable to download video data' in str(e).lower() or 'http error 404' in str(e).lower()):
                    print(f" [+] Attempting manual XHamster extraction for download error...")
                    try:
                        import requests
                        import re
                        
                        # Get page content
                        response = requests.get(progress.url, 
                            headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                                'Accept-Language': 'en-US,en;q=0.9',
                            },
                            timeout=30)
                        
                        # Extract M3U8 video URL patterns from XHamster
                        m3u8_patterns = [
                            r'video-cf\.xhcdn\.com[^"\']*\.m3u8[^"\']*',
                            r'preload[^>]*href=["\']([^"\']*\.m3u8[^"\']*)["\']',
                            r'"file"\s*:\s*"([^"]+\.m3u8[^"]*)"',
                        ]
                        
                        video_url = None
                        for pattern in m3u8_patterns:
                            matches = re.findall(pattern, response.text, re.IGNORECASE)
                            if matches:
                                video_url = matches[0] if isinstance(matches[0], str) else matches[0]
                                # Ensure URL is properly formatted
                                if not video_url.startswith('http'):
                                    video_url = 'https://' + video_url
                                break
                        
                        # Extract title from page
                        title_match = re.search(r'<title[^>]*>([^<]+)</title>', response.text, re.IGNORECASE)
                        video_title = "XHamster_Video"
                        if title_match:
                            title = title_match.group(1)
                            # Clean title for filename
                            video_title = utilities.clean_video_title(title.split(' - ')[0])
                            progress.title = video_title  # Update progress title
                        
                        if video_url:
                            print(f" [+] Found direct M3U8 URL, downloading...")
                            
                            # Create options for M3U8 download
                            direct_opts = {
                                'outtmpl': os.path.join(config.get_video_download_path(), f'{video_title}.%(ext)s'),
                                'progress_hooks': [lambda d: self.progress_hook(d, progress)],
                                'http_headers': {
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                                    'Referer': 'https://xhamster.com/',
                                }
                            }
                            
                            with yt_dlp.YoutubeDL(direct_opts) as direct_ydl:
                                direct_ydl.extract_info(video_url, download=True)
                            
                            print(f" [+] Manual XHamster extraction successful!")
                            return  # Success, exit the function
                        else:
                            print(f" [!] Could not find M3U8 URL in page content")
                            
                    except Exception as manual_e:
                        print(f" [!] Manual XHamster extraction failed: {manual_e}")
                        raise e  # Raise original error
                else:
                    raise
            except Exception as e:
                print(f" [!] Unexpected error during download: {e}")
                print(f" [!] Error type: {type(e).__name__}")
                raise
            
            if not progress.cancelled:
                progress.status = 'completed'
                progress.percent = 100.0
                print(f" [+] Download completed: {progress.title}")
                
                # Store file metadata with source URL
                try:
                    file_metadata = get_file_metadata()
                    # Find the downloaded file(s) and store metadata
                    download_path = config.get_download_path()
                    for filename in os.listdir(download_path):
                        # Check if this file matches the download (basic matching)
                        if any(word.lower() in filename.lower() for word in progress.title.split() if len(word) > 3):
                            if not filename.endswith(('.part', '.ytdl', '.temp')):
                                file_metadata.add_file(filename, progress.url, progress.title)
                                print(f" [+] Stored metadata for file: {filename}")
                except Exception as e:
                    print(f" [!] Error storing file metadata: {e}")
                
                # Mark as completed in URL tracker
                if hasattr(progress, 'url_track_id'):
                    tracker = get_tracker()
                    tracker.mark_completed(progress.url_track_id)
                
                # Save the final state
                with download_lock:
                    save_active_downloads()
                
                # Auto-cleanup matching partial files
                try:
                    removed_files = auto_cleanup_matching_partial_files(progress.title)
                    if removed_files:
                        print(f" [+] Auto-cleaned {len(removed_files)} matching partial files: {', '.join(removed_files)}")
                except Exception as e:
                    print(f" [!] Error during auto-cleanup: {e}")
                
                # Open finder on macOS if requested - DISABLED
                # if open_folder and sys.platform == 'darwin':
                #     videoDownloader.open_finder(download_path)
            
        except (yt_dlp.DownloadError, AttributeError) as e:
            error_msg = str(e)
            server_logger.error(f"yt-dlp Download error for {progress.url}: {error_msg}")
            print(f" [!] yt-dlp Download error: {error_msg}")
            
            # Reset progress on error
            progress.percent = 0.0
            
            # Try fallback approach for Pornhub, XHamster, and Eporner
            if ('pornhub.com' in progress.url or 'xhamster.com' in progress.url or 'eporner.com' in progress.url) and ('Unable to extract title' in error_msg or 'Unable to extract hash' in error_msg or isinstance(e, AttributeError)):
                if 'eporner.com' in progress.url:
                    site_name = 'Eporner'
                elif 'xhamster.com' in progress.url:
                    site_name = 'XHamster'
                else:
                    site_name = 'Pornhub'
                print(f" [+] Attempting {site_name} fallback extraction...")
                progress.percent = 25.0  # Show some progress for fallback attempt
                try:
                    # Create site-specific fallback options
                    if 'eporner.com' in progress.url:
                        fallback_opts = {
                            'outtmpl': os.path.join(download_path, config.DEFAULT_OUTPUT_TEMPLATE),
                            'progress_hooks': [lambda d: self.progress_hook(d, progress)],
                            'format': 'best',
                            'quiet': False,
                            'no_warnings': False,
                            'retries': 25,
                            'fragment_retries': 25,
                            'socket_timeout': 600,
                            'http_headers': {
                                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                                'Accept': '*/*',
                                'Accept-Language': 'en-US,en;q=0.5',
                                'Accept-Encoding': 'gzip, deflate',
                                'Connection': 'keep-alive',
                                'Upgrade-Insecure-Requests': '1',
                                'Referer': 'https://www.eporner.com/',
                            },
                            'sleep_interval_requests': 5,
                            'ignoreerrors': True,
                            'extract_flat': False,
                            'writesubtitles': False,
                            'writeautomaticsub': False,
                        }
                    else:
                        # Original fallback for Pornhub/XHamster
                        fallback_opts = {
                            'outtmpl': os.path.join(download_path, config.DEFAULT_OUTPUT_TEMPLATE),
                            'progress_hooks': [lambda d: self.progress_hook(d, progress)],
                            'format': 'best',
                            'quiet': False,
                            'no_warnings': False,
                            'retries': 15,
                            'fragment_retries': 15,
                            'socket_timeout': 300,
                            'http_headers': {
                                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                                'Accept-Language': 'en-us,en;q=0.5',
                                'Accept-Encoding': 'gzip,deflate',
                                'Connection': 'keep-alive',
                                'Upgrade-Insecure-Requests': '1',
                                'Referer': 'https://www.pornhub.com/' if 'pornhub.com' in progress.url else 'https://xhamster.com/',
                            },
                            'sleep_interval_requests': 5,
                            'extractor_args': {
                                'generic': {
                                    'default_search': 'auto'
                                }
                            }
                        }
                    with yt_dlp.YoutubeDL(fallback_opts) as fallback_ydl:
                        print(f" [+] Trying fallback extraction...")
                        progress.percent = 40.0
                        info = fallback_ydl.extract_info(progress.url, download=False)
                        print(f" [+] Fallback extraction successful: {info.get('title', 'Unknown')}")
                        progress.percent = 60.0
                        fallback_ydl.extract_info(progress.url, download=True)
                        print(f" [+] Fallback download completed successfully")
                        progress.status = 'completed'
                        progress.percent = 100.0
                        
                        # Mark as completed in URL tracker
                        if hasattr(progress, 'url_track_id'):
                            tracker = get_tracker()
                            tracker.mark_completed(progress.url_track_id)
                        
                        # Auto-cleanup matching partial files
                        try:
                            removed_files = auto_cleanup_matching_partial_files(progress.title)
                            if removed_files:
                                print(f" [+] Auto-cleaned {len(removed_files)} matching partial files: {', '.join(removed_files)}")
                        except Exception as e:
                            print(f" [!] Error during auto-cleanup: {e}")
                        
                        return  # Success, exit the function
                except Exception as fallback_e:
                    print(f" [!] Fallback also failed: {fallback_e}")
                    
                    # Last resort for Eporner: manual video URL extraction
                    if 'eporner.com' in progress.url:
                        print(f" [+] Attempting manual Eporner video URL extraction...")
                        progress.percent = 50.0
                        try:
                            import requests
                            import re
                            
                            # Get page content
                            response = requests.get(progress.url, 
                                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'},
                                timeout=30)
                            
                            # Extract video URL patterns
                            video_patterns = [
                                r'\"(https?://[^\"]*gvideo\.eporner\.com[^\"]*\.mp4[^\"]*?)\"',
                                r'video_url[\"\']\s*:\s*[\"\'](.*?)[\"\']',
                                r'\"(https?://[^\"]*\.mp4[^\"]*?)\"',
                            ]
                            
                            video_url = None
                            for pattern in video_patterns:
                                matches = re.findall(pattern, response.text, re.IGNORECASE)
                                if matches:
                                    video_url = matches[0]
                                    break
                            
                            if video_url:
                                print(f" [+] Found direct video URL, attempting download...")
                                progress.percent = 75.0
                                
                                # Use yt-dlp to download the direct video URL
                                direct_opts = {
                                    'outtmpl': os.path.join(download_path, progress.title + '.%(ext)s'),
                                    'progress_hooks': [lambda d: self.progress_hook(d, progress)],
                                    'http_headers': {
                                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                                        'Referer': 'https://www.eporner.com/',
                                    }
                                }
                                
                                with yt_dlp.YoutubeDL(direct_opts) as direct_ydl:
                                    direct_ydl.download([video_url])
                                
                                progress.status = 'completed'
                                progress.percent = 100.0
                                print(f" [+] Manual Eporner extraction successful!")
                                
                                # Auto-cleanup matching partial files
                                try:
                                    removed_files = auto_cleanup_matching_partial_files(progress.title)
                                    if removed_files:
                                        print(f" [+] Auto-cleaned {len(removed_files)} matching partial files: {', '.join(removed_files)}")
                                except Exception as e:
                                    print(f" [!] Error during auto-cleanup: {e}")
                                
                                return  # Success!
                            else:
                                print(f" [!] Could not find video URL in page content")
                                
                        except Exception as manual_e:
                            print(f" [!] Manual extraction failed: {manual_e}")
                    
                    progress.percent = 0.0  # Reset on fallback failure
                    if not progress.cancelled:
                        progress.status = 'error'
                        progress.error = error_msg
            else:
                if not progress.cancelled:
                    progress.status = 'error'
                    progress.error = error_msg
        except Exception as e:
            error_msg = str(e)
            print(f" [!] General download error: {error_msg}")
            # Reset progress on error
            progress.percent = 0.0
            if not progress.cancelled:
                progress.status = 'error'
                progress.error = error_msg
        finally:
            print(f" [+] Download thread finished for: {progress.title}")
            
            # If download failed, add to persistent store
            if progress.status == 'error' and not progress.cancelled:
                print(f" [!] Adding failed download to persistent store: {progress.title}")
                progress.partial_files = get_partial_files(progress.download_id, progress.title)
                add_failed_download(progress.download_id, {
                    'url': progress.url,
                    'title': progress.title,
                    'error': progress.error,
                    'retry_count': progress.retry_count,
                    'open_folder': progress.open_folder
                })
                
                # Mark as failed in URL tracker
                if hasattr(progress, 'url_track_id'):
                    tracker = get_tracker()
                    tracker.mark_failed(progress.url_track_id, progress.error)
            
            # Clean up from active downloads after 5 minutes (unless it's a failed download to retry)
            def cleanup():
                time.sleep(300)  # 5 minutes
                with download_lock:
                    if progress.download_id in active_downloads:
                        # Only remove if it's not a failed download (failed downloads stay for retry)
                        if progress.status != 'error':
                            print(f" [+] Cleaning up download: {progress.download_id}")
                            del active_downloads[progress.download_id]
                            save_active_downloads()
            
            cleanup_thread = threading.Thread(target=cleanup)
            cleanup_thread.daemon = True
            cleanup_thread.start()
    
    def progress_hook(self, d, progress):
        """Progress hook for yt-dlp."""
        if progress.cancelled:
            raise yt_dlp.DownloadError("Download cancelled by user")
        
        if d['status'] == 'downloading':
            # Update progress information
            if 'total_bytes' in d and d['total_bytes']:
                progress.percent = (d.get('downloaded_bytes', 0) / d['total_bytes']) * 100
            elif 'total_bytes_estimate' in d and d['total_bytes_estimate']:
                progress.percent = (d.get('downloaded_bytes', 0) / d['total_bytes_estimate']) * 100
            
            # Format speed and ETA
            speed = d.get('_speed_str', '').strip()
            eta = d.get('_eta_str', '').strip()
            
            progress.speed = speed
            progress.eta = eta
            
            # Save active downloads periodically (every 10% progress)
            if int(progress.percent) % 10 == 0:
                with download_lock:
                    save_active_downloads()
            
        elif d['status'] == 'finished':
            progress.status = 'processing'
            progress.percent = 100.0
            with download_lock:
                save_active_downloads()
    
    def send_json_response(self, data, status=200):
        """Send JSON response with CORS headers."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        response_data = json.dumps(data, indent=2)
        self.wfile.write(response_data.encode('utf-8'))
    
    def send_html_response(self, html):
        """Send HTML response."""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def get_web_interface(self):
        """Get modern VidSnatch homepage interface."""
        # Count only truly active downloads (preparing, downloading, processing)
        active_count = sum(1 for progress in active_downloads.values() 
                          if progress.status in ['preparing', 'downloading', 'processing'])
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>VidSnatch Control Panel</title>
            <!-- Favicons -->
            <link rel="apple-touch-icon" sizes="180x180" href="/static/favicons/apple-touch-icon.png">
            <link rel="icon" type="image/png" sizes="32x32" href="/static/favicons/favicon-32x32.png">
            <link rel="icon" type="image/png" sizes="16x16" href="/static/favicons/favicon-16x16.png">
            <link rel="manifest" href="/static/favicons/site.webmanifest">
            <link rel="shortcut icon" href="/favicon.ico">
            <style>
                :root {{
                    /* Light mode colors */
                    --bg-gradient-start: #3d4db7;
                    --bg-gradient-end: #523a6f;
                    --text-color: #333;
                    --card-bg: rgba(255, 255, 255, 0.95);
                    --card-border: rgba(255, 255, 255, 0.2);
                    --table-header-bg: #f8f9fa;
                    --table-hover-bg: #f9f9f9;
                    --table-border: #f0f0f0;
                    --table-partial-bg: #fff9f0;
                    --table-playing-bg: #e8f4ff;
                    --modal-bg: rgba(0, 0, 0, 0.5);
                    --modal-content-bg: white;
                    --btn-bg: #007bff;
                    --btn-hover-bg: #0056b3;
                    --btn-danger-bg: #dc3545;
                    --btn-danger-hover-bg: #c82333;
                    --input-bg: white;
                    --input-border: #ddd;
                    --toggle-bg: #ccc;
                    --toggle-active-bg: #007bff;
                    --toggle-slider-bg: white;
                    --uninstall-text-color: #d32f2f;
                    --secondary-text-color: #666;
                }}
                
                [data-theme="dark"] {{
                    /* Dark mode colors */
                    --bg-gradient-start: #1a1a2e;
                    --bg-gradient-end: #16213e;
                    --text-color: #e0e0e0;
                    --card-bg: rgba(45, 45, 45, 0.95);
                    --card-border: rgba(255, 255, 255, 0.1);
                    --table-header-bg: #2c2c2c;
                    --table-hover-bg: #3a3a3a;
                    --table-border: #404040;
                    --table-partial-bg: #3d3520;
                    --table-playing-bg: #1e3a5f;
                    --modal-bg: rgba(0, 0, 0, 0.8);
                    --modal-content-bg: #2c2c2c;
                    --btn-bg: #0d6efd;
                    --btn-hover-bg: #0b5ed7;
                    --btn-danger-bg: #dc3545;
                    --btn-danger-hover-bg: #bb2d3b;
                    --input-bg: #3c3c3c;
                    --input-border: #555;
                    --toggle-bg: #555;
                    --toggle-active-bg: #0d6efd;
                    --toggle-slider-bg: #f0f0f0;
                    --uninstall-text-color: #ff6b6b;
                    --secondary-text-color: #bbb;
                }}
                
                /* Dark mode specific element styles */
                [data-theme="dark"] .download-item {{
                    background: #3c3c3c;
                    border: 1px solid #555;
                }}
                
                [data-theme="dark"] .download-title {{
                    color: #e0e0e0;
                }}
                
                [data-theme="dark"] .download-meta {{
                    color: #b0b0b0;
                }}
                
                [data-theme="dark"] .downloads-table {{
                    background: var(--card-bg);
                    color: var(--text-color);
                }}
                
                [data-theme="dark"] .downloads-table th {{
                    background: var(--table-header-bg);
                    color: var(--text-color);
                }}
                
                [data-theme="dark"] .downloads-table td {{
                    color: var(--text-color);
                    border-bottom: 1px solid var(--table-border);
                }}
                
                [data-theme="dark"] .video-controls {{
                    background: rgba(45, 45, 45, 0.95);
                    backdrop-filter: blur(10px);
                }}
                
                [data-theme="dark"] .downloads-list {{
                    background: #2c2c2c;
                    border: 1px solid #404040;
                }}
                
                [data-theme="dark"] .video-title {{
                    color: #e0e0e0;
                }}
                
                [data-theme="dark"] .video-meta {{
                    color: #bbb;
                }}
                
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    background: linear-gradient(135deg, var(--bg-gradient-start) 0%, var(--bg-gradient-end) 100%);
                    min-height: 100vh;
                    color: var(--text-color);
                    transition: all 0.25s ease-in-out;
                }}
                
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                
                .header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    height: 60px;
                    margin-bottom: 30px;
                    background: var(--card-bg);
                    backdrop-filter: blur(10px);
                    border-radius: 15px;
                    padding: 0 30px;
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
                    gap: 20px;
                }}
                
                .header-left {{
                    display: flex;
                    align-items: center;
                }}
                
                .theme-toggle {{
                    display: flex;
                    align-items: center;
                }}
                
                .toggle-switch {{
                    position: relative;
                    display: inline-block;
                    width: 60px;
                    height: 30px;
                    cursor: pointer;
                }}
                
                .toggle-switch input {{
                    opacity: 0;
                    width: 0;
                    height: 0;
                }}
                
                .toggle-slider {{
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background-color: var(--toggle-bg);
                    transition: 0.3s;
                    border-radius: 30px;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    padding: 3px 6px;
                }}
                
                .toggle-slider:before {{
                    position: absolute;
                    content: "";
                    height: 24px;
                    width: 24px;
                    left: 3px;
                    bottom: 3px;
                    background-color: var(--toggle-slider-bg);
                    transition: 0.3s;
                    border-radius: 50%;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                }}
                
                input:checked + .toggle-slider {{
                    background-color: var(--toggle-active-bg);
                }}
                
                input:checked + .toggle-slider:before {{
                    transform: translateX(30px);
                }}
                
                .toggle-icon {{
                    font-size: 12px;
                    z-index: 1;
                    pointer-events: none;
                }}
                
                .toggle-icon.light {{
                    margin-left: 2px;
                }}
                
                .toggle-icon.dark {{
                    margin-right: 2px;
                }}
                
                .logo {{
                    font-size: 2rem;
                    background: linear-gradient(135deg, #3d4db7, #523a6f);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                    font-weight: bold;
                }}
                
                
                .main-content {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 30px;
                    margin-bottom: 30px;
                }}
                
                .card {{
                    background: var(--card-bg);
                    backdrop-filter: blur(10px);
                    border-radius: 15px;
                    padding: 25px;
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
                }}
                
                .card h3 {{
                    margin-bottom: 20px;
                    color: var(--text-color);
                    font-size: 1.4rem;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}
                
                .status-indicator {{
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                    background: var(--btn-bg);
                    animation: pulse 2s infinite;
                }}
                
                @keyframes pulse {{
                    0% {{ opacity: 1; }}
                    50% {{ opacity: 0.5; }}
                    100% {{ opacity: 1; }}
                }}
                
                .server-toggle {{
                    display: flex;
                    align-items: center;
                    gap: 15px;
                    margin: 15px 0;
                }}
                
                .toggle-switch {{
                    position: relative;
                    width: 60px;
                    height: 30px;
                    background: var(--toggle-bg);
                    border-radius: 15px;
                    cursor: pointer;
                    transition: all 0.3s ease;
                }}
                
                .toggle-switch.active {{
                    background: var(--toggle-active-bg);
                }}
                
                .toggle-switch .slider {{
                    position: absolute;
                    top: 3px;
                    left: 3px;
                    width: 24px;
                    height: 24px;
                    background: var(--toggle-slider-bg);
                    border-radius: 50%;
                    transition: all 0.3s ease;
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
                }}
                
                .toggle-switch.active .slider {{
                    transform: translateX(30px);
                }}
                
                .folder-section {{
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    margin: 15px 0;
                    padding: 10px;
                    background: var(--input-bg);
                    border: 1px solid var(--input-border);
                    border-radius: 8px;
                }}
                
                .folder-path {{
                    flex: 1;
                    font-family: monospace;
                    font-size: 0.9rem;
                    color: var(--text-color);
                    opacity: 0.8;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }}
                
                .btn {{
                    background: linear-gradient(135deg, #3d4db7, #523a6f);
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 0.9rem;
                    transition: all 0.2s ease;
                }}
                
                .btn:hover {{
                    transform: translateY(-1px);
                    box-shadow: 0 4px 12px rgba(61, 77, 183, 0.4);
                }}
                
                .btn.danger {{
                    background: linear-gradient(135deg, #d63447, #c42f3a);
                }}
                
                .uninstall-link-btn {{
                    background: none;
                    border: none;
                    color: var(--uninstall-text-color);
                    cursor: pointer;
                    font-size: 0.9rem;
                    text-decoration: none;
                    padding: 8px 0;
                    transition: all 0.2s ease;
                    font-family: inherit;
                }}
                
                .uninstall-link-btn:hover {{
                    opacity: 0.8;
                    text-decoration: underline;
                }}
                
                .downloads-section {{
                    display: none;
                    grid-column: 1 / -1;
                }}
                
                .downloads-section.active {{
                    display: block;
                }}
                
                .downloads-list {{
                    max-height: 300px;
                    overflow-y: auto;
                    margin-top: 15px;
                }}
                
                .downloads-table {{
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 0.9rem;
                    background: var(--card-bg);
                    color: var(--text-color);
                    table-layout: fixed;
                }}
                
                .downloads-table th {{
                    text-align: left;
                    padding: 8px 12px;
                    border-bottom: 2px solid var(--table-border);
                    font-weight: 600;
                    color: var(--text-color);
                    background: var(--table-header-bg);
                }}
                
                .downloads-table td {{
                    padding: 8px 12px;
                    border-bottom: 1px solid var(--table-border);
                    vertical-align: middle;
                    color: var(--text-color);
                }}
                
                .downloads-table tr:hover {{
                    background: var(--row-hover-bg);
                }}
                
                .download-title {{
                    font-weight: 600;
                    color: var(--text-color);
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }}
                
                .download-status {{
                    display: inline-flex;
                    align-items: center;
                    gap: 4px;
                    font-size: 0.8rem;
                }}
                
                .status-indicator {{
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    flex-shrink: 0;
                }}
                
                .download-item {{
                    display: flex;
                    align-items: center;
                    gap: 15px;
                    padding: 15px;
                    background: #e8e9eb;
                    border-radius: 8px;
                    margin-bottom: 10px;
                }}
                
                .download-info {{
                    flex: 1;
                }}
                
                .download-progress {{
                    width: 60px;
                    height: 4px;
                    background: #e0e0e0;
                    border-radius: 2px;
                    overflow: hidden;
                    display: inline-block;
                }}
                
                .download-progress-full {{
                    width: 100%;
                    height: 6px;
                    background: #e0e0e0;
                    border-radius: 3px;
                    overflow: hidden;
                    margin: 8px 0;
                }}
                
                .progress-fill {{
                    height: 100%;
                    background: linear-gradient(135deg, #3d4db7, #523a6f);
                    transition: width 0.3s ease;
                }}
                
                .download-meta {{
                    font-size: 0.8rem;
                    color: #666;
                }}
                
                .file-explorer {{
                    max-height: 400px;
                    overflow-y: auto;
                    margin-top: 15px;
                    border: 1px solid var(--card-border);
                    border-radius: 8px;
                    background: var(--card-bg);
                }}
                
                .files-table {{
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 0.9rem;
                    background: var(--card-bg);
                    color: var(--text-color);
                    table-layout: fixed;
                }}
                
                .resizable-column {{
                    position: relative;
                }}
                
                .column-resizer {{
                    position: absolute;
                    top: 0;
                    right: 0;
                    width: 3px;
                    height: 100%;
                    cursor: col-resize;
                    background: transparent;
                    z-index: 10;
                }}
                
                .column-resizer:hover {{
                    background: var(--btn-bg);
                }}
                
                .column-resizing {{
                    user-select: none;
                }}
                
                .files-table thead {{
                    background: var(--table-header-bg);
                    position: sticky;
                    top: 0;
                    z-index: 10;
                }}
                
                .files-table th {{
                    text-align: left;
                    padding: 10px 12px;
                    border-bottom: 2px solid var(--table-border);
                    font-weight: 600;
                    color: var(--text-color);
                    user-select: none;
                }}
                
                .files-table th[onclick] {{
                    cursor: pointer;
                }}
                
                .files-table th[onclick]:hover {{
                    background: var(--table-hover-bg);
                }}
                
                .files-table tbody tr {{
                    border-bottom: 1px solid var(--table-border);
                    transition: background 0.2s ease;
                    cursor: pointer;
                }}
                
                .files-table tbody tr:hover {{
                    background: var(--table-hover-bg);
                }}
                
                .files-table tbody tr.partial-file {{
                    background: var(--table-partial-bg);
                    cursor: default;
                }}
                
                .files-table tbody tr.playing {{
                    background: var(--table-playing-bg);
                }}
                
                .files-table td {{
                    padding: 8px 12px;
                    vertical-align: middle;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    color: var(--text-color);
                }}
                
                .file-name-cell {{
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    max-width: 400px;
                }}
                
                .file-name-text {{
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }}
                
                .name-input {{
                    width: 100% !important;
                    border: 1px solid var(--input-border) !important;
                    background: var(--input-bg) !important;
                    color: var(--text-color) !important;
                    padding: 2px 4px !important;
                    border-radius: 2px !important;
                    font-size: 12px !important;
                    transition: border-color 0.2s ease !important;
                }}
                
                .name-input:focus {{
                    outline: none !important;
                    border-color: var(--btn-bg) !important;
                }}
                
                .file-actions {{
                    display: flex;
                    gap: 5px;
                }}
                
                .file-btn {{
                    padding: 4px 8px;
                    font-size: 0.8rem;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    transition: all 0.2s;
                }}
                
                .file-btn.retry {{
                    background: var(--btn-bg);
                    color: white;
                }}
                
                .file-btn.retry:hover {{
                    background: var(--btn-hover-bg);
                }}
                
                .file-btn.delete {{
                    background: var(--btn-danger-bg);
                    color: white;
                }}
                
                .file-btn.delete:hover {{
                    background: var(--btn-danger-hover-bg);
                }}
                
                /* Keep existing styles for compatibility */
                .file-item {{
                    display: none;
                }}
                
                .file-info {{
                    display: none;
                }}
                
                .file-details {{
                    flex: 1;
                    min-width: 0;
                }}
                
                .file-actions {{
                    display: flex;
                    gap: 8px;
                    flex-shrink: 0;
                }}
                
                .file-btn {{
                    background: linear-gradient(135deg, #3d4db7, #523a6f);
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 0.8rem;
                    transition: all 0.2s ease;
                    display: flex;
                    align-items: center;
                    gap: 4px;
                }}
                
                .file-btn:hover {{
                    transform: translateY(-1px);
                    box-shadow: 0 3px 8px rgba(102, 126, 234, 0.3);
                }}
                
                .file-btn.retry {{
                    background: linear-gradient(135deg, #4caf50, #45a049);
                }}
                
                .file-btn.retry:hover {{
                    box-shadow: 0 3px 8px rgba(76, 175, 80, 0.3);
                }}
                
                .file-btn.delete {{
                    background: linear-gradient(135deg, #d63447, #c42f3a);
                }}
                
                .file-btn.delete:hover {{
                    box-shadow: 0 3px 8px rgba(255, 107, 107, 0.3);
                }}
                
                .file-item:hover {{
                    background: #e8e9eb;
                }}
                
                .file-item.video-file:hover {{
                    background: #d1e5f7;
                    border-color: #2196f3;
                }}
                
                .file-item.partial-file {{
                    opacity: 0.7;
                    background: #f5e6d3;
                }}
                
                .file-item.partial-file:hover {{
                    background: #f0d4a4;
                }}
                
                .file-icon {{
                    width: 20px;
                    text-align: center;
                }}
                
                .file-name {{
                    flex: 1;
                    font-size: 0.9rem;
                }}
                
                .file-size {{
                    font-size: 0.8rem;
                    color: #666;
                }}
                
                .empty-state {{
                    text-align: center;
                    padding: 40px;
                    color: #999;
                }}
                
                .loading-container {{
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    padding: 40px;
                    color: var(--text-color);
                    opacity: 0.7;
                }}
                
                .loading-spinner {{
                    width: 40px;
                    height: 40px;
                    border: 3px solid var(--card-border);
                    border-top: 3px solid var(--btn-bg);
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                    margin-bottom: 15px;
                }}
                
                @keyframes spin {{
                    0% {{ transform: rotate(0deg); }}
                    100% {{ transform: rotate(360deg); }}
                }}
                
                .video-player-section {{
                    width: 100%;
                    max-width: 1200px;
                    margin: 0 auto 30px auto;
                    display: none;
                }}
                
                .video-player-section.active {{
                    display: block;
                }}
                
                .video-player-container {{
                    background: rgba(0, 0, 0, 0.95);
                    border-radius: 15px;
                    overflow: hidden;
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
                    position: relative;
                }}
                
                .video-player {{
                    width: 100%;
                    height: auto;
                    min-height: 300px;
                    max-height: 70vh;
                    display: block;
                    background: #000;
                }}
                
                .video-controls {{
                    background: rgba(255, 255, 255, 0.95);
                    backdrop-filter: blur(10px);
                    padding: 15px 20px;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 15px;
                }}
                
                .video-info {{
                    flex: 1;
                    min-width: 0;
                }}
                
                .video-title {{
                    font-size: 1.1rem;
                    font-weight: 600;
                    color: #333;
                    margin-bottom: 5px;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }}
                
                .video-meta {{
                    font-size: 0.9rem;
                    color: #666;
                }}
                
                .video-actions {{
                    display: flex;
                    gap: 10px;
                    flex-shrink: 0;
                }}
                
                .video-btn {{
                    background: linear-gradient(135deg, #3d4db7, #523a6f);
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 0.9rem;
                    transition: all 0.2s ease;
                    display: flex;
                    align-items: center;
                    gap: 5px;
                }}
                
                .video-btn:hover {{
                    transform: translateY(-1px);
                    box-shadow: 0 4px 12px rgba(61, 77, 183, 0.4);
                }}
                
                .video-btn.close {{
                    background: linear-gradient(135deg, #d63447, #c42f3a);
                }}
                
                .video-btn:disabled {{
                    opacity: 0.5;
                    cursor: not-allowed !important;
                    transform: none !important;
                    box-shadow: none !important;
                }}
                
                /* URL Input Modal */
                .modal-overlay {{
                    display: none;
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.5);
                    z-index: 1000;
                    backdrop-filter: blur(5px);
                }}
                
                .modal-overlay.active {{
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                
                .modal-content {{
                    background: var(--card-bg);
                    border-radius: 15px;
                    padding: 30px;
                    max-width: 600px;
                    width: 90%;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                    animation: modalSlideIn 0.3s ease-out;
                }}
                
                @keyframes modalSlideIn {{
                    from {{
                        opacity: 0;
                        transform: translateY(-20px) scale(0.95);
                    }}
                    to {{
                        opacity: 1;
                        transform: translateY(0) scale(1);
                    }}
                }}
                
                .modal-header {{
                    margin-bottom: 20px;
                }}
                
                .modal-title {{
                    font-size: 1.3rem;
                    font-weight: 600;
                    color: #333;
                    margin-bottom: 10px;
                }}
                
                .modal-subtitle {{
                    color: #666;
                    font-size: 0.9rem;
                    line-height: 1.4;
                }}
                
                .modal-body {{
                    margin-bottom: 25px;
                }}
                
                .url-input-group {{
                    margin-bottom: 15px;
                }}
                
                .url-input-label {{
                    display: block;
                    font-weight: 500;
                    color: #333;
                    margin-bottom: 8px;
                    font-size: 0.9rem;
                }}
                
                .url-input {{
                    width: 100%;
                    padding: 12px 16px;
                    border: 2px solid #e0e0e0;
                    border-radius: 8px;
                    font-size: 0.9rem;
                    font-family: monospace;
                    transition: all 0.2s ease;
                    resize: vertical;
                    min-height: 60px;
                }}
                
                .url-input:focus {{
                    outline: none;
                    border-color: #3d4db7;
                    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
                }}
                
                .filename-display {{
                    background: #e8e9eb;
                    padding: 12px 16px;
                    border-radius: 8px;
                    font-family: monospace;
                    font-size: 0.9rem;
                    color: #666;
                    word-break: break-all;
                }}
                
                .modal-actions {{
                    display: flex;
                    gap: 12px;
                    justify-content: flex-end;
                }}
                
                .modal-btn {{
                    padding: 10px 20px;
                    border: none;
                    border-radius: 6px;
                    font-size: 0.9rem;
                    font-weight: 500;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }}
                
                .modal-btn.primary {{
                    background: linear-gradient(135deg, #3d4db7, #523a6f);
                    color: white;
                }}
                
                .modal-btn.primary:hover {{
                    transform: translateY(-1px);
                    box-shadow: 0 4px 12px rgba(61, 77, 183, 0.4);
                }}
                
                .modal-btn.secondary {{
                    background: #e8e9eb;
                    color: #666;
                    border: 1px solid #e0e0e0;
                }}
                
                .modal-btn.secondary:hover {{
                    background: #d8dce0;
                }}
                
                /* Loading States */
                .file-loading {{
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    color: #3d4db7;
                    font-size: 0.8rem;
                    font-weight: 500;
                }}
                
                .loading-spinner {{
                    width: 16px;
                    height: 16px;
                    border: 2px solid #f3f3f3;
                    border-top: 2px solid #3d4db7;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                }}
                
                @keyframes spin {{
                    0% {{ transform: rotate(0deg); }}
                    100% {{ transform: rotate(360deg); }}
                }}
                
                /* Video highlighting in file list */
                .file-item.playing {{
                    background: linear-gradient(135deg, rgba(61, 77, 183, 0.15), rgba(82, 58, 111, 0.15));
                    border-left: 4px solid #3d4db7;
                    padding-left: 12px;
                }}
                
                .file-item.playing .file-name {{
                    color: #3d4db7;
                    font-weight: 600;
                }}
                
                /* Suggested Downloads Styles */
                .suggested-downloads {{
                    max-height: 200px;
                    overflow-y: auto;
                    border: 1px solid var(--input-border);
                    border-radius: 6px;
                }}
                
                .suggestion-item {{
                    display: grid;
                    grid-template-columns: 3fr 2fr 1fr 120px;
                    align-items: center;
                    padding: 8px 12px;
                    border-bottom: 1px solid var(--input-border);
                    transition: background 0.2s ease;
                    height: 40px;
                    font-size: 0.85rem;
                }}
                
                .suggestion-item:last-child {{
                    border-bottom: none;
                }}
                
                .suggestion-item:hover {{
                    background: var(--table-hover-bg);
                }}
                
                .suggestion-title {{
                    font-weight: 500;
                    color: var(--text-color);
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                    padding-right: 8px;
                }}
                
                .suggestion-url {{
                    font-size: 0.8rem;
                    color: var(--btn-bg);
                    opacity: 0.8;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                    cursor: pointer;
                    text-decoration: underline;
                    padding-right: 8px;
                }}
                
                .suggestion-url:hover {{
                    opacity: 1;
                    color: var(--btn-hover-bg);
                }}
                
                .suggestion-meta {{
                    font-size: 0.75rem;
                    color: var(--text-color);
                    opacity: 0.6;
                    margin-top: 2px;
                }}
                
                .suggestion-actions {{
                    display: flex;
                    gap: 6px;
                    align-items: center;
                    justify-content: flex-end;
                }}
                
                .suggestion-btn {{
                    padding: 4px 8px;
                    font-size: 0.75rem;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    transition: all 0.2s ease;
                    font-weight: 500;
                    white-space: nowrap;
                }}
                
                .suggestion-btn.download {{
                    background: var(--btn-bg);
                    color: white;
                }}
                
                .suggestion-btn.download:hover {{
                    background: var(--btn-hover-bg);
                }}
                
                .suggestion-btn.delete {{
                    background: var(--btn-danger-bg);
                    color: white;
                }}
                
                .suggestion-btn.delete:hover {{
                    background: var(--btn-danger-hover-bg);
                    transform: translateY(-1px);
                }}
                
                /* Collapsible section styles */
                .collapsible-header {{
                    user-select: none;
                }}
                
                .collapsible-header:hover {{
                    background: var(--table-hover-bg);
                    border-radius: 6px;
                    padding: 8px;
                    margin: -8px;
                }}
                
                /* Tags Input System Styles (RS Suite TagInput style) */
                .tags-input-container {{
                    display: flex;
                    flex-wrap: nowrap;
                    align-items: center;
                    gap: 4px;
                    height: 32px;
                    min-height: 32px;
                    max-height: 32px;
                    padding: 4px 8px;
                    border: 1px solid var(--input-border);
                    border-radius: 6px;
                    background: var(--input-bg);
                    cursor: text;
                    transition: border-color 0.2s ease;
                    overflow-x: auto;
                    overflow-y: hidden;
                    scrollbar-width: thin;
                    scrollbar-color: var(--border-color) transparent;
                }}
                
                .tags-input-container::-webkit-scrollbar {{
                    height: 4px;
                }}
                
                .tags-input-container::-webkit-scrollbar-track {{
                    background: transparent;
                }}
                
                .tags-input-container::-webkit-scrollbar-thumb {{
                    background-color: var(--border-color);
                    border-radius: 2px;
                }}
                
                .tags-input-container:hover {{
                    border-color: var(--btn-bg);
                }}
                
                .tags-input-container:focus-within {{
                    border-color: var(--btn-bg);
                    box-shadow: 0 0 0 2px rgba(61, 77, 183, 0.1);
                }}
                
                .tags-chips {{
                    display: flex;
                    flex-wrap: nowrap;
                    gap: 4px;
                    flex: 0 0 auto;
                }}
                
                .tag-chip {{
                    display: inline-flex;
                    align-items: center;
                    gap: 4px;
                    background: var(--btn-bg);
                    color: white;
                    padding: 2px 6px 2px 8px;
                    border-radius: 12px;
                    font-size: 0.75rem;
                    font-weight: 500;
                    max-width: 200px;
                    height: 22px;
                    white-space: nowrap;
                    transition: all 0.2s ease;
                    flex-shrink: 0;
                    cursor: pointer;
                }}
                
                .tag-chip span:first-child {{
                    overflow: hidden;
                    text-overflow: ellipsis;
                    pointer-events: none;
                }}
                
                .tag-chip:hover {{
                    background: var(--btn-hover-bg);
                    transform: scale(1.02);
                }}
                
                .tag-remove {{
                    cursor: pointer;
                    font-size: 14px;
                    line-height: 1;
                    color: rgba(255, 255, 255, 0.7);
                    padding: 0 2px;
                    border-radius: 50%;
                    transition: all 0.2s ease;
                    flex-shrink: 0;
                    margin-left: auto;
                }}
                
                .tag-remove:hover {{
                    background: rgba(255, 255, 255, 0.2);
                    color: white;
                }}
                
                .tags-input-field {{
                    border: none;
                    outline: none;
                    background: transparent;
                    color: var(--text-color);
                    font-size: 0.8rem;
                    padding: 4px 0;
                    min-width: 80px;
                    height: 22px;
                    flex: 1 1 auto;
                    overflow: hidden;
                }}
                
                .tags-input-field::placeholder {{
                    color: var(--secondary-text-color);
                    opacity: 0.6;
                }}
                
                /* Search Bar Styles */
                .search-bar-container {{
                    position: relative;
                    margin-bottom: 15px;
                }}
                
                .search-input {{
                    width: 100%;
                    padding: 12px 16px 12px 45px;
                    border: 2px solid var(--input-border);
                    background: var(--input-bg);
                    color: var(--text-color);
                    border-radius: 8px;
                    font-size: 0.9rem;
                    transition: all 0.2s ease;
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
                }}
                
                .search-input:focus {{
                    outline: none;
                    border-color: var(--btn-bg);
                    box-shadow: 0 0 0 3px rgba(61, 77, 183, 0.1);
                }}
                
                .search-icon {{
                    position: absolute;
                    left: 15px;
                    top: 50%;
                    transform: translateY(-50%);
                    color: var(--secondary-text-color);
                    font-size: 1.1rem;
                    pointer-events: none;
                }}
                
                .search-input:focus + .search-icon {{
                    color: var(--btn-bg);
                }}
                
                @media (max-width: 768px) {{
                    .main-content {{
                        grid-template-columns: 1fr;
                        gap: 20px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <!-- Header with Logo -->
                <div class="header">
                    <div class="header-left">
                        <div class="logo">🎬 VidSnatch</div>
                    </div>
                    <div class="theme-toggle">
                        <label class="toggle-switch">
                            <input type="checkbox" id="themeToggle">
                            <span class="toggle-slider">
                                <span class="toggle-icon light">☀️</span>
                                <span class="toggle-icon dark">🌙</span>
                            </span>
                        </label>
                    </div>
                </div>
                
                <!-- Video Player Section -->
                <div class="video-player-section" id="videoPlayerSection">
                    <div class="video-player-container">
                        <video class="video-player" id="videoPlayer" controls preload="metadata">
                            <source id="videoSource" src="" type="video/mp4">
                            Your browser does not support the video tag.
                        </video>
                        <div class="video-controls">
                            <div class="video-info">
                                <div class="video-title" id="videoTitle">No video selected</div>
                                <div class="video-meta" id="videoMeta">Select a video from the Downloaded Files section to play</div>
                            </div>
                            <div class="video-actions">
                                <button class="video-btn" onclick="playPreviousVideo()" id="prevVideoBtn" title="Previous Video">
                                    ⏮ Previous
                                </button>
                                <button class="video-btn" onclick="playNextVideo()" id="nextVideoBtn" title="Next Video">
                                    Next ⏭
                                </button>
                                <button class="video-btn" onclick="openVideoInExternal()" id="openExternalBtn" style="display: none;">
                                    🎬 Open External
                                </button>
                                <button class="video-btn close" onclick="closeVideoPlayer()">
                                    ✕ Close
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- File Explorer Card (Moved to top) -->
                <div class="card" style="margin-bottom: 20px;">
                    <h3>🗂️ Downloaded Files</h3>
                    <div class="search-bar-container">
                        <input type="text" id="fileSearchBar" class="search-input" 
                               placeholder="Search files by name, tags, or URL..." 
                               oninput="filterFiles(this.value)">
                        <div class="search-icon">🔍</div>
                    </div>
                    <div class="file-explorer" id="fileExplorer">
                        <div class="loading-container">
                            <div class="loading-spinner"></div>
                            <div>Loading files...</div>
                        </div>
                    </div>
                </div>
                
                <!-- Main Content Grid -->
                <div class="main-content">
                    <!-- Downloads Section (Hidden when no downloads) -->
                    <div class="card downloads-section" id="downloadsSection">
                        <h3>📥 Active Downloads</h3>
                        <div class="downloads-list" id="downloadsList"></div>
                    </div>
                    
                    <!-- Server Control Card -->
                    <div class="card">
                        <h3>
                            <span class="status-indicator" id="statusIndicator"></span>
                            Server Control
                        </h3>
                        <div class="server-toggle">
                            <span>Server:</span>
                            <div class="toggle-switch active" id="serverToggle" onclick="toggleServer()">
                                <div class="slider"></div>
                            </div>
                            <span id="serverStatus">Running</span>
                        </div>
                        <div style="font-size: 0.9rem; color: var(--secondary-text-color);">
                            <strong>Port:</strong> 8080<br>
                            <strong>Active Downloads:</strong> <span id="activeCount">{active_count}</span>
                        </div>
                    </div>
                    
                    <!-- Folder Settings Card -->
                    <div class="card">
                        <h3>📁 Download Folder</h3>
                        <div class="folder-section">
                            <div class="folder-path" id="folderPath">Loading...</div>
                            <button class="btn" onclick="openFolder()">Open</button>
                            <button class="btn" onclick="changeFolder()">Change</button>
                        </div>
                        <button class="btn" onclick="refreshFiles()">🔄 Refresh Files</button>
                    </div>
                    
                    
                </div>
                
                <!-- Suggested Downloads Card (Moved to Bottom, Collapsible) -->
                <div class="card" style="grid-column: 1 / -1; margin-top: 20px;">
                    <div class="collapsible-header" onclick="toggleSuggestedDownloads()" style="cursor: pointer; display: flex; align-items: center; gap: 10px;">
                        <span id="suggestedToggleIcon">▶</span>
                        <h3 style="margin: 0;">💡 Suggested Downloads</h3>
                        <span style="color: var(--secondary-text-color); font-size: 0.9rem;">Click to expand</span>
                    </div>
                    <div id="suggestedDownloadsSection" style="display: none; margin-top: 15px;">
                        <p style="margin-bottom: 15px; color: var(--secondary-text-color);">
                            Scan your browser history for frequently visited video URLs
                        </p>
                        <button class="btn" id="loadSuggestionsBtn" onclick="loadSuggestions()">Load Suggestions</button>
                        <div id="suggestedContainer" style="margin-top: 15px; display: none;">
                            <div id="scanStatus" style="margin-bottom: 10px; color: var(--secondary-text-color);"></div>
                            <div class="suggested-downloads" id="suggestedDownloads"></div>
                        </div>
                    </div>
                </div>
            </div>
            
            
            <script>
                let currentFolder = '';
                
                // Person names storage
                const personNames = JSON.parse(localStorage.getItem('personNames') || '{{}}');
                
                // Deleted URLs storage for suggested downloads
                const deletedUrls = JSON.parse(localStorage.getItem('deletedSuggestedUrls') || '{{}}');
                
                function isUrlDeleted(url) {{
                    return deletedUrls[url] === true;
                }}
                
                function markUrlAsDeleted(url) {{
                    deletedUrls[url] = true;
                    localStorage.setItem('deletedSuggestedUrls', JSON.stringify(deletedUrls));
                }}
                
                function toggleSuggestedDownloads() {{
                    const section = document.getElementById('suggestedDownloadsSection');
                    const icon = document.getElementById('suggestedToggleIcon');
                    
                    if (section.style.display === 'none') {{
                        section.style.display = 'block';
                        icon.textContent = '▼';
                    }} else {{
                        section.style.display = 'none';
                        icon.textContent = '▶';
                    }}
                }}
                
                function openUrlInNewTab(url) {{
                    window.open(url, '_blank');
                }}
                
                function getPersonName(filename) {{
                    return personNames[filename] || '';
                }}
                
                function savePersonName(filename, name) {{
                    if (name.trim()) {{
                        personNames[filename] = name.trim();
                    }} else {{
                        delete personNames[filename];
                    }}
                    localStorage.setItem('personNames', JSON.stringify(personNames));
                }}
                
                function escapeFilename(filename) {{
                    // Escape special characters for use in JavaScript strings
                    return filename.replace(/\\\\/g, '\\\\\\\\')
                                  .replace(/'/g, "\\\\'")
                                  .replace(/"/g, '\\\\"')
                                  .replace(/\\n/g, '\\\\n')
                                  .replace(/\\r/g, '\\\\r')
                                  .replace(/\\t/g, '\\\\t');
                }}
                
                
                async function scanBrowserHistory() {{
                    const scanBtn = document.getElementById('scanHistoryBtn');
                    const scanStatus = document.getElementById('scanStatus');
                    const daysSelect = document.getElementById('historyDaysSelect');
                    const suggestedContainer = document.getElementById('suggestedDownloads');
                    
                    const days = parseInt(daysSelect.value);
                    
                    // Disable button and show loading
                    scanBtn.disabled = true;
                    scanBtn.textContent = '🔍 Scanning...';
                    scanStatus.textContent = 'Searching browser history...';
                    
                    try {{
                        // Access browser history (only available in Chrome extensions)
                        if (typeof chrome === 'undefined' || !chrome.history) {{
                            scanStatus.textContent = 'Browser history access not available in web interface';
                            scanStatus.innerHTML = `
                                ❌ Browser history access not available in web interface<br>
                                <small>Use the VidSnatch Chrome Extension for automatic history scanning</small>
                            `;
                            return;
                        }}
                        
                        const startTime = Date.now() - (days * 24 * 60 * 60 * 1000);
                        
                        const historyItems = await new Promise((resolve, reject) => {{
                            chrome.history.search({{
                                text: '',
                                maxResults: 10000,
                                startTime: startTime
                            }}, (results) => {{
                                if (chrome.runtime.lastError) {{
                                    reject(chrome.runtime.lastError);
                                }} else {{
                                    resolve(results);
                                }}
                            }});
                        }});
                        
                        scanStatus.textContent = `Found ${{historyItems.length}} history items, analyzing...`;
                        
                        // Filter for actual video URLs and count visits (excludes home pages, category pages, etc.)
                        const videoUrls = {{}};
                        
                        // Function to check if URL is a valid video page (very strict)
                        function isValidVideoUrl(url) {{
                            // STRICT video-only patterns - must match one of these exactly
                            const videoPatterns = [
                                /youtube\\.com\\/watch\\?v=[a-zA-Z0-9_-]+(&.*)?$/i,
                                /youtu\\.be\\/[a-zA-Z0-9_-]+$/i,
                                /vimeo\\.com\\/\\d+$/i,
                                /dailymotion\\.com\\/video\\/[a-zA-Z0-9_-]+$/i,
                                /tiktok\\.com\\/.*\\/video\\/\\d+$/i,
                                /instagram\\.com\\/p\\/[a-zA-Z0-9_-]+\\/$/i,
                                /instagram\\.com\\/reel\\/[a-zA-Z0-9_-]+\\/$/i,
                                /facebook\\.com\\/.*\\/videos\\/\\d+$/i,
                                /twitter\\.com\\/.*\\/status\\/\\d+$/i,
                                /x\\.com\\/.*\\/status\\/\\d+$/i,
                                /twitch\\.tv\\/videos\\/\\d+$/i,
                                /pornhub\\.com\\/view_video\\.php\\?viewkey=[a-zA-Z0-9_-]+(&.*)?$/i,
                                /xvideos\\.com\\/video\\d+\\/[^/]+$/i,
                                /xhamster\\.com\\/videos\\/[^/]+-\\d+$/i,
                                /redtube\\.com\\/\\d+$/i,
                                /tnaflix\\.com\\/.*\\/video\\/\\d+$/i,
                                /eporner\\.com\\/video-[a-zA-Z0-9_-]+\\/[^/]+$/i,
                                /xnxx\\.com\\/video-[a-zA-Z0-9_-]+\\/[^/]+$/i,
                                /spankbang\\.com\\/[a-zA-Z0-9_-]+\\/video\\/[^/]+$/i
                            ];
                            
                            return videoPatterns.some(pattern => pattern.test(url));
                        }}
                        
                        for (const item of historyItems) {{
                            if (!item.url || !item.title) continue;
                            
                            // Use strict video URL validation
                            if (!isValidVideoUrl(item.url)) continue;
                            
                            // Skip if URL was deleted by user
                            if (isUrlDeleted(item.url)) continue;
                            
                            // Count visits
                            if (!videoUrls[item.url]) {{
                                videoUrls[item.url] = {{
                                    title: item.title,
                                    url: item.url,
                                    visitCount: 0,
                                    lastVisit: item.lastVisitTime
                                }};
                            }}
                            videoUrls[item.url].visitCount++;
                            
                            // Update last visit time if more recent
                            if (item.lastVisitTime > videoUrls[item.url].lastVisit) {{
                                videoUrls[item.url].lastVisit = item.lastVisitTime;
                            }}
                        }}
                        
                        // Filter for URLs visited 3+ times and sort by visit count
                        const suggestions = Object.values(videoUrls)
                            .filter(item => item.visitCount >= 3)
                            .sort((a, b) => {{
                                // Sort by visit count (descending), then by recency
                                if (a.visitCount !== b.visitCount) {{
                                    return b.visitCount - a.visitCount;
                                }}
                                return b.lastVisit - a.lastVisit;
                            }})
                            .slice(0, 20); // Limit to top 20 suggestions
                        
                        displaySuggestions(suggestions);
                        scanStatus.textContent = `Found ${{suggestions.length}} suggested downloads`;
                        
                    }} catch (error) {{
                        console.error('Error scanning browser history:', error);
                        scanStatus.textContent = 'Error accessing browser history';
                        suggestedContainer.innerHTML = `
                            <div class="empty-state" style="text-align: center; padding: 20px; color: var(--text-color); opacity: 0.7;">
                                ❌ Could not access browser history. Make sure the extension has history permission.
                            </div>
                        `;
                    }} finally {{
                        // Re-enable button
                        scanBtn.disabled = false;
                        scanBtn.textContent = '🔍 Scan History';
                    }}
                }}
                
                function displaySuggestions(suggestions) {{
                    const container = document.getElementById('suggestedDownloads');
                    
                    if (suggestions.length === 0) {{
                        container.innerHTML = `
                            <div class="empty-state" style="text-align: center; padding: 20px; color: var(--text-color); opacity: 0.7;">
                                No frequently visited videos found. Try increasing the number of days or visit videos multiple times.
                            </div>
                        `;
                        return;
                    }}
                    
                    const suggestionsHtml = suggestions.map(item => {{
                        const lastVisitDate = new Date(item.lastVisit).toLocaleDateString();
                        return `
                            <div class="suggestion-item" data-url="${{item.url}}">
                                <div class="suggestion-info">
                                    <div class="suggestion-title" title="${{item.title}}">${{item.title}}</div>
                                    <div class="suggestion-url" title="${{item.url}}">${{item.url}}</div>
                                    <div class="suggestion-meta">Visited ${{item.visitCount}} times • Last: ${{lastVisitDate}}</div>
                                </div>
                                <div class="suggestion-actions">
                                    <button class="suggestion-btn download" onclick="downloadSuggestion('${{item.url}}', '${{item.title.replace(/'/g, "\\\\'")}}')">
                                        📥 Download
                                    </button>
                                    <button class="suggestion-btn delete" onclick="deleteSuggestion('${{item.url}}')">
                                        🗑️ Delete
                                    </button>
                                </div>
                            </div>
                        `;
                    }}).join('');
                    
                    container.innerHTML = suggestionsHtml;
                }}
                
                async function downloadSuggestion(url, title) {{
                    try {{
                        const response = await fetch('/download', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                            }},
                            body: JSON.stringify({{ url: url, title: title }})
                        }});
                        
                        if (response.ok) {{
                            const result = await response.json();
                            console.log('Download started:', result);
                            
                            // Refresh downloads to show the new download
                            updateDownloads();
                            
                            // Show success message
                            const scanStatus = document.getElementById('scanStatus');
                            scanStatus.textContent = `Started downloading: ${{title}}`;
                            setTimeout(() => {{
                                scanStatus.textContent = '';
                            }}, 3000);
                        }} else {{
                            throw new Error('Failed to start download');
                        }}
                    }} catch (error) {{
                        console.error('Error starting download:', error);
                        alert('Failed to start download. Please try again.');
                    }}
                }}
                
                function deleteSuggestion(url) {{
                    // Mark URL as deleted
                    markUrlAsDeleted(url);
                    
                    // Remove from UI
                    const suggestionItem = document.querySelector(`[data-url="${{url}}"]`);
                    if (suggestionItem) {{
                        suggestionItem.remove();
                        
                        // Check if there are any suggestions left
                        const container = document.getElementById('suggestedDownloads');
                        const remainingSuggestions = container.querySelectorAll('.suggestion-item');
                        
                        if (remainingSuggestions.length === 0) {{
                            container.innerHTML = `
                                <div class="empty-state" style="text-align: center; padding: 20px; color: var(--text-color); opacity: 0.7;">
                                    No suggestions remaining. Click "Scan History" to find new suggestions.
                                </div>
                            `;
                        }}
                        
                        // Update status
                        const scanStatus = document.getElementById('scanStatus');
                        scanStatus.textContent = 'Suggestion removed';
                        setTimeout(() => {{
                            scanStatus.textContent = '';
                        }}, 2000);
                    }}
                }}
                
                // Dark mode functionality
                function initializeTheme() {{
                    const themeToggle = document.getElementById('themeToggle');
                    const savedTheme = localStorage.getItem('theme') || 'light';
                    
                    // Apply saved theme
                    document.documentElement.setAttribute('data-theme', savedTheme);
                    themeToggle.checked = savedTheme === 'dark';
                    
                    // Add event listener for toggle
                    themeToggle.addEventListener('change', function() {{
                        const newTheme = this.checked ? 'dark' : 'light';
                        document.documentElement.setAttribute('data-theme', newTheme);
                        localStorage.setItem('theme', newTheme);
                    }});
                }}

                // Initialize the page
                document.addEventListener('DOMContentLoaded', function() {{
                    initializeTheme();
                    loadCurrentFolder();
                    loadDownloadedFiles();
                    updateDownloads();
                    setInterval(updateDownloads, 2000); // Update every 2 seconds
                    
                    
                }});
                
                async function loadCurrentFolder() {{
                    try {{
                        const response = await fetch('/current-folder');
                        const result = await response.json();
                        if (result.status === 'success') {{
                            currentFolder = result.folder;
                            document.getElementById('folderPath').textContent = result.folder;
                        }}
                    }} catch (error) {{
                        document.getElementById('folderPath').textContent = 'Error loading folder';
                    }}
                }}
                
                // File sorting state
                let filesData = [];
                let currentSort = {{ column: 'date', order: 'desc' }};
                
                function formatHumanDate(timestamp) {{
                    const date = new Date(timestamp * 1000);
                    
                    const month = date.getMonth() + 1; // 0-indexed, so add 1
                    const day = date.getDate();
                    const year = date.getFullYear();
                    
                    let hours = date.getHours();
                    const minutes = date.getMinutes();
                    const ampm = hours >= 12 ? 'pm' : 'am';
                    hours = hours % 12;
                    hours = hours ? hours : 12; // 0 should be 12
                    const minutesStr = minutes < 10 ? '0' + minutes : minutes;
                    
                    return `${{month}}-${{day}}-${{year}} ${{hours}}:${{minutesStr}}${{ampm}}`;
                }}
                
                function sortFiles(column) {{
                    if (currentSort.column === column) {{
                        currentSort.order = currentSort.order === 'asc' ? 'desc' : 'asc';
                    }} else {{
                        currentSort.column = column;
                        currentSort.order = 'asc';
                    }}
                    
                    filesData.sort((a, b) => {{
                        let aVal, bVal;
                        
                        switch(column) {{
                            case 'title':
                                aVal = a.name.toLowerCase();
                                bVal = b.name.toLowerCase();
                                break;
                            case 'name':
                                aVal = (getPersonName(a.name) || '').toLowerCase();
                                bVal = (getPersonName(b.name) || '').toLowerCase();
                                break;
                            case 'size':
                                aVal = a.sizeBytes;
                                bVal = b.sizeBytes;
                                break;
                            case 'length':
                                // Parse duration from duration or use 0 if not available
                                aVal = a.duration ? parseDurationToSeconds(a.duration) : 0;
                                bVal = b.duration ? parseDurationToSeconds(b.duration) : 0;
                                break;
                            case 'tags':
                                aVal = getFileTags(a.name).join(' ').toLowerCase();
                                bVal = getFileTags(b.name).join(' ').toLowerCase();
                                break;
                            case 'date':
                                aVal = a.timestamp;
                                bVal = b.timestamp;
                                break;
                            default:
                                return 0;
                        }}
                        
                        if (aVal < bVal) return currentSort.order === 'asc' ? -1 : 1;
                        if (aVal > bVal) return currentSort.order === 'asc' ? 1 : -1;
                        return 0;
                    }});
                    
                    renderFilesTable();
                }}
                
                function renderFilesTable() {{
                    const fileExplorer = document.getElementById('fileExplorer');
                    
                    if (!filesData.length) {{
                        fileExplorer.innerHTML = '<div class="empty-state">No files found in downloads folder</div>';
                        return;
                    }}
                    
                    const tableHTML = `
                        <table class="files-table resizable-table">
                            <thead>
                                <tr>
                                    <th class="resizable-column" style="width: 25%; cursor: pointer;" onclick="sortFiles('title')" title="Sort by title">
                                        Title ${{currentSort.column === 'title' ? (currentSort.order === 'asc' ? '↑' : '↓') : '↕'}}
                                        <div class="column-resizer"></div>
                                    </th>
                                    <th class="resizable-column" style="width: 12%; cursor: pointer;" onclick="sortFiles('name')" title="Sort by person name">
                                        Name ${{currentSort.column === 'name' ? (currentSort.order === 'asc' ? '↑' : '↓') : '↕'}}
                                        <div class="column-resizer"></div>
                                    </th>
                                    <th class="resizable-column" style="width: 10%; cursor: pointer;" onclick="sortFiles('size')" title="Sort by file size">
                                        File Size ${{currentSort.column === 'size' ? (currentSort.order === 'asc' ? '↑' : '↓') : '↕'}}
                                        <div class="column-resizer"></div>
                                    </th>
                                    <th class="resizable-column" style="width: 8%; cursor: pointer;" onclick="sortFiles('length')" title="Sort by video length">
                                        Length ${{currentSort.column === 'length' ? (currentSort.order === 'asc' ? '↑' : '↓') : '↕'}}
                                        <div class="column-resizer"></div>
                                    </th>
                                    <th class="resizable-column" style="width: 30%; cursor: pointer;" onclick="sortFiles('tags')" title="Sort by tags">
                                        Tags ${{currentSort.column === 'tags' ? (currentSort.order === 'asc' ? '↑' : '↓') : '↕'}}
                                        <div class="column-resizer"></div>
                                    </th>
                                    <th style="width: 15%; cursor: pointer;" onclick="sortFiles('date')" title="Sort by date">
                                        Date Added ${{currentSort.column === 'date' ? (currentSort.order === 'asc' ? '↑' : '↓') : '↕'}}
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                ${{filesData.map(file => {{
                                    const isVideoFile = /\\.(mp4|avi|mkv|mov|wmv|flv|webm|m4v)$/i.test(file.name);
                                    const isPartialFile = /\\.(part|ytdl|temp)$/i.test(file.name);
                                    
                                    let icon = '📄';
                                    let rowClass = '';
                                    let clickHandler = '';
                                    let length = '—';
                                    
                                    if (isVideoFile) {{
                                        icon = '🎥';
                                        clickHandler = `onclick="playVideo('${{escapeFilename(file.name)}}')"`;
                                        // Format video duration if available
                                        if (file.duration) {{
                                            length = formatDuration(file.duration);
                                        }} else {{
                                            length = '—';
                                        }}
                                    }} else if (isPartialFile) {{
                                        icon = '⚠️';
                                        rowClass = 'partial-file';
                                        length = '—';
                                    }} else {{
                                        clickHandler = `onclick="openFile('${{escapeFilename(file.name)}}')"`;
                                    }}
                                    
                                    const dateAdded = formatHumanDate(file.timestamp);
                                    
                                    const personName = getPersonName(file.name) || '';
                                    
                                    return `
                                        <tr class="${{rowClass}}" data-filename="${{file.name}}" ${{clickHandler}} style="cursor: ${{clickHandler ? 'pointer' : 'default'}}">
                                            <td>
                                                <div class="file-name-cell">
                                                    <span>${{icon}}</span>
                                                    <span class="file-name-text" title="${{file.name}}">${{file.name.replace(/\.(mp4|avi|mkv|mov|wmv|flv|webm|m4v|part|ytdl|temp)$/i, '')}}</span>
                                                </div>
                                            </td>
                                            <td>
                                                <input type="text" class="name-input" value="${{personName}}" 
                                                       placeholder="Enter name..." 
                                                       onclick="event.stopPropagation()" 
                                                       onchange="savePersonName('${{escapeFilename(file.name)}}', this.value)">
                                            </td>
                                            <td>${{file.size}}</td>
                                            <td>${{length}}</td>
                                            <td>
                                                <div class="tags-input-container" data-filename="${{file.name}}" onclick="event.stopPropagation()">
                                                    <div class="tags-chips"></div>
                                                    <input type="text" class="tags-input-field" 
                                                           placeholder="Add tags..." 
                                                           onkeydown="handleTagInputKeydown(event, '${{escapeFilename(file.name)}}')"
                                                           onblur="handleTagInputBlur(event, '${{escapeFilename(file.name)}}')"
                                                           onfocus="handleTagInputFocus(event, '${{escapeFilename(file.name)}}')"
                                                           onclick="event.stopPropagation()">
                                                </div>
                                            </td>
                                            <td>
                                                ${{isPartialFile ? `
                                                    <div class="file-actions">
                                                        <button class="file-btn retry" onclick="event.stopPropagation(); retryPartialDownload('${{escapeFilename(file.name)}}')" title="Retry download">
                                                            🔄 Retry
                                                        </button>
                                                        <button class="file-btn delete" onclick="event.stopPropagation(); deletePartialFile('${{escapeFilename(file.name)}}')" title="Delete partial file">
                                                            🗑️ Delete
                                                        </button>
                                                    </div>
                                                ` : dateAdded}}
                                            </td>
                                        </tr>
                                    `;
                                }}).join('')}}
                            </tbody>
                        </table>
                    `;
                    
                    fileExplorer.innerHTML = tableHTML;
                    
                    // Initialize column resizing
                    initializeColumnResizing();
                    
                    // Initialize tags displays
                    initializeAllTagsDisplays();
                    
                    // Update video files list for navigation
                    videoFilesList = filesData
                        .filter(file => /\\.(mp4|avi|mkv|mov|wmv|flv|webm|m4v)$/i.test(file.name))
                        .map(file => file.name);
                }}
                
                function initializeColumnResizing() {{
                    let isResizing = false;
                    let currentColumn = null;
                    let startX = 0;
                    let startWidth = 0;
                    
                    // Add event listeners to all column resizers
                    document.querySelectorAll('.column-resizer').forEach(resizer => {{
                        resizer.addEventListener('mousedown', (e) => {{
                            isResizing = true;
                            currentColumn = e.target.closest('th');
                            startX = e.clientX;
                            startWidth = currentColumn.offsetWidth;
                            
                            document.body.classList.add('column-resizing');
                            e.preventDefault();
                        }});
                    }});
                    
                    document.addEventListener('mousemove', (e) => {{
                        if (!isResizing || !currentColumn) return;
                        
                        const diff = e.clientX - startX;
                        const newWidth = Math.max(50, startWidth + diff); // Minimum width of 50px
                        const table = currentColumn.closest('table');
                        const columnIndex = Array.from(currentColumn.parentNode.children).indexOf(currentColumn);
                        
                        // Update column width
                        currentColumn.style.width = newWidth + 'px';
                        
                        // Update corresponding cells in body
                        const rows = table.querySelectorAll('tbody tr');
                        rows.forEach(row => {{
                            const cell = row.children[columnIndex];
                            if (cell) {{
                                cell.style.width = newWidth + 'px';
                            }}
                        }});
                    }});
                    
                    document.addEventListener('mouseup', () => {{
                        if (isResizing) {{
                            isResizing = false;
                            currentColumn = null;
                            document.body.classList.remove('column-resizing');
                        }}
                    }});
                }}
                
                async function loadDownloadedFiles() {{
                    try {{
                        const response = await fetch('/browse-downloads');
                        const result = await response.json();
                        const fileExplorer = document.getElementById('fileExplorer');
                        
                        if (result.status === 'success' && result.files.length > 0) {{
                            // Parse files data with size conversion and timestamp extraction
                            filesData = result.files.map(file => {{
                                // Use timestamp directly since it's already a number
                                const timestamp = typeof file.modified === 'number' ? file.modified : parseFloat(file.modified) || Date.now() / 1000;
                                
                                // Parse file size for sorting
                                const sizeMatch = file.size.match(/(\\d+\\.?\\d*)\\s*(\\w+)/);
                                let sizeBytes = 0;
                                if (sizeMatch) {{
                                    const value = parseFloat(sizeMatch[1]);
                                    const unit = sizeMatch[2];
                                    const multipliers = {{ 'B': 1, 'KB': 1024, 'MB': 1024*1024, 'GB': 1024*1024*1024 }};
                                    sizeBytes = value * (multipliers[unit] || 1);
                                }}
                                
                                return {{
                                    name: file.name,
                                    size: file.size,
                                    sizeBytes: sizeBytes,
                                    timestamp: timestamp,
                                    original: file
                                }};
                            }});
                            
                            // Initialize filtered data with all files
                            filteredFilesData = [...filesData];
                            
                            // Apply current sort (default is date descending - newest first)
                            // Don't use sortFiles() as it toggles - apply sort directly
                            filesData.sort((a, b) => {{
                                const aVal = a.timestamp;
                                const bVal = b.timestamp;
                                return currentSort.order === 'asc' ? aVal - bVal : bVal - aVal;
                            }});
                            renderFilesTable();
                        }} else {{
                            filesData = [];
                            filteredFilesData = [];
                            renderFilesTable();
                        }}
                    }} catch (error) {{
                        console.error('Error loading files:', error);
                        document.getElementById('fileExplorer').innerHTML = '<div class="empty-state">Error loading files</div>';
                        // Check if it's a network error
                        if (error instanceof TypeError && error.message === 'Failed to fetch') {{
                            console.error('Network error: Unable to connect to server for file browsing');
                        }}
                    }}
                }}
                
                async function updateDownloads() {{
                    try {{
                        const response = await fetch('/debug');
                        const result = await response.json();
                        const downloadsSection = document.getElementById('downloadsSection');
                        const downloadsList = document.getElementById('downloadsList');
                        const activeCount = document.getElementById('activeCount');
                        
                        activeCount.textContent = result.active_downloads_count;
                        
                        // Show downloads section if there are any downloads OR if active count > 0
                        if ((result.downloads && result.downloads.length > 0) || result.active_downloads_count > 0) {{
                            downloadsSection.classList.add('active');
                            
                            const tableHeader = `
                                <table class="downloads-table">
                                    <thead>
                                        <tr>
                                            <th style="width: 50%;">Title</th>
                                            <th style="width: 15%;">Status</th>
                                            <th style="width: 15%;">Progress</th>
                                            <th style="width: 20%;">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                            `;
                            
                            const tableRows = result.downloads.map(download => {{
                                const isActive = download.status === 'preparing' || download.status === 'downloading' || download.status === 'processing';
                                const isFailed = download.status === 'error' || download.status === 'failed';
                                const isCompleted = download.status === 'completed';
                                const isCancelled = download.status === 'cancelled';
                                
                                let statusColor = '#4caf50'; // Green for active
                                if (isFailed) statusColor = '#f44336'; // Red for failed
                                if (isCancelled) statusColor = '#9e9e9e'; // Gray for cancelled
                                if (isCompleted) statusColor = '#2196f3'; // Blue for completed
                                
                                let buttons = '';
                                if (isActive) {{
                                    buttons = `<button class="btn danger" onclick="cancelDownload('${{download.downloadId}}')">Cancel</button>`;
                                }} else if (isFailed) {{
                                    buttons = `
                                        <button class="btn" onclick="retryDownload('${{download.downloadId}}')">🔄 Retry</button>
                                        <button class="btn danger" onclick="deleteDownload('${{download.downloadId}}')">🗑️ Delete</button>
                                    `;
                                }} else if (isCancelled) {{
                                    buttons = `<button class="btn danger" onclick="deleteDownload('${{download.downloadId}}')">🗑️ Delete</button>`;
                                }} else if (isCompleted) {{
                                    buttons = `<button class="btn danger" onclick="clearDownload('${{download.downloadId}}')">✕</button>`;
                                }}
                                
                                let statusText = '';
                                let progressContent = '';
                                
                                if (isActive) {{
                                    statusText = `<span class="download-status"><span class="status-indicator" style="background: ${{statusColor}};"></span>${{download.status}}</span>`;
                                    progressContent = `
                                        <div style="display: flex; align-items: center; gap: 8px;">
                                            <div class="download-progress">
                                                <div class="progress-fill" style="width: ${{parseFloat(download.percent).toFixed(1) || 0}}%"></div>
                                            </div>
                                            <span style="font-size: 0.8rem;">${{parseFloat(download.percent).toFixed(1) || 0}}%</span>
                                        </div>
                                        <div style="font-size: 0.7rem; color: var(--secondary-text-color); margin-top: 2px;">
                                            ${{download.speed || 'Unknown speed'}} • ${{download.eta || 'Unknown ETA'}}
                                        </div>
                                    `;
                                }} else if (isFailed) {{
                                    const retryText = download.retry_count > 0 ? ` (Retry #${{download.retry_count}})` : '';
                                    statusText = `<span class="download-status"><span class="status-indicator" style="background: ${{statusColor}};"></span>Failed${{retryText}}</span>`;
                                    progressContent = `<span style="color: #f44336; font-size: 0.8rem;">${{download.error || 'Unknown error'}}</span>`;
                                }} else if (isCancelled) {{
                                    statusText = `<span class="download-status"><span class="status-indicator" style="background: ${{statusColor}};"></span>Cancelled</span>`;
                                    progressContent = '—';
                                }} else if (isCompleted) {{
                                    statusText = `<span class="download-status"><span class="status-indicator" style="background: ${{statusColor}};"></span>Completed</span>`;
                                    progressContent = `<span style="color: #4caf50; font-size: 0.8rem;">✅ Done</span>`;
                                }}
                                
                                return `
                                    <tr>
                                        <td>
                                            <div class="download-title" title="${{download.title || 'Unknown Video'}}">${{download.title || 'Unknown Video'}}</div>
                                        </td>
                                        <td>${{statusText}}</td>
                                        <td>${{progressContent}}</td>
                                        <td>
                                            <div style="display: flex; gap: 4px;">
                                                ${{buttons}}
                                            </div>
                                        </td>
                                    </tr>
                                `;
                            }}).join('');
                            
                            const tableFooter = `
                                    </tbody>
                                </table>
                            `;
                            
                            downloadsList.innerHTML = tableHeader + tableRows + tableFooter;
                        }} else {{
                            downloadsSection.classList.remove('active');
                            // Clear the downloads list if no downloads
                            downloadsList.innerHTML = '';
                        }}
                    }} catch (error) {{
                        console.error('Failed to update downloads:', error);
                        // Check if it's a network error
                        if (error instanceof TypeError && error.message === 'Failed to fetch') {{
                            console.error('Network error: Unable to connect to server at localhost:8080');
                            console.error('Make sure the VidSnatch server is running');
                        }}
                    }}
                }}
                
                async function toggleServer() {{
                    const toggle = document.getElementById('serverToggle');
                    const status = document.getElementById('serverStatus');
                    const indicator = document.getElementById('statusIndicator');
                    
                    if (toggle.classList.contains('active')) {{
                        // Stop server
                        if (confirm('Are you sure you want to stop the VidSnatch server? This will also close the web interface.')) {{
                            try {{
                                const response = await fetch('/stop-server', {{ method: 'POST' }});
                                const result = await response.json();
                                
                                if (result.success) {{
                                    toggle.classList.remove('active');
                                    status.textContent = 'Stopping...';
                                    indicator.style.background = '#ff9800';
                                    
                                    // Show message about server stopping
                                    setTimeout(() => {{
                                        document.body.innerHTML = `
                                            <div style="display: flex; align-items: center; justify-content: center; height: 100vh; flex-direction: column; background: linear-gradient(135deg, #3d4db7 0%, #523a6f 100%); color: white; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                                                <h2 style="margin-bottom: 20px;">🎬 VidSnatch Server Stopped</h2>
                                                <p>The server has been stopped. To restart, use the menu bar application or run the server manually.</p>
                                            </div>
                                        `;
                                    }}, 2000);
                                }}
                            }} catch (error) {{
                                alert('Failed to stop server: ' + error.message);
                            }}
                        }}
                    }} else {{
                        // Start server - not possible from web interface since server is needed to serve this page
                        alert('Server is already running (you are viewing this page). Use the menu bar application to restart if needed.');
                    }}
                }}
                
                async function openFolder() {{
                    try {{
                        const response = await fetch('/open-folder', {{ method: 'POST' }});
                        const result = await response.json();
                        if (result.success) {{
                            // Folder opened successfully - no need to alert, it will open in Finder/Explorer
                        }} else {{
                            alert('Failed to open folder: ' + result.message);
                        }}
                    }} catch (error) {{
                        alert('Failed to open folder: ' + error.message);
                    }}
                }}
                
                async function changeFolder() {{
                    try {{
                        const response = await fetch('/select-folder', {{ method: 'POST' }});
                        const result = await response.json();
                        
                        if (result.success) {{
                            // Update the displayed folder path and refresh files
                            currentFolder = result.path;
                            document.getElementById('folderPath').textContent = result.path;
                            loadDownloadedFiles(); // Refresh the file list
                            alert('Folder changed successfully to: ' + result.path);
                        }} else if (result.cancelled) {{
                            // User cancelled folder selection - reload original path
                            loadCurrentFolder();
                        }} else {{
                            alert('Failed to change folder: ' + (result.error || 'Unknown error'));
                        }}
                    }} catch (error) {{
                        alert('Failed to change folder: ' + error.message);
                    }}
                }}
                
                function refreshFiles() {{
                    loadDownloadedFiles();
                }}
                
                async function openFile(filename) {{
                    try {{
                        const response = await fetch(`/open-file/${{encodeURIComponent(filename)}}`);
                        const result = await response.json();
                        
                        if (result.status === 'success') {{
                            // File opened successfully
                        }} else {{
                            alert('Failed to open file: ' + result.message);
                        }}
                    }} catch (error) {{
                        alert('Error opening file');
                    }}
                }}
                
                async function cancelDownload(downloadId) {{
                    try {{
                        const response = await fetch(`/cancel/${{downloadId}}`, {{ method: 'POST' }});
                        const result = await response.json();
                        
                        if (result.status === 'success') {{
                            updateDownloads(); // Refresh the downloads list
                        }} else {{
                            alert('Failed to cancel download');
                        }}
                    }} catch (error) {{
                        alert('Error cancelling download');
                    }}
                }}
                
                async function retryDownload(downloadId) {{
                    try {{
                        const response = await fetch(`/retry/${{downloadId}}`, {{ method: 'POST' }});
                        const result = await response.json();
                        
                        if (result.success) {{
                            console.log(`Retry started for download ${{downloadId}} (attempt #${{result.retry_count}})`);
                            updateDownloads(); // Refresh the downloads list
                        }} else {{
                            alert('Failed to retry download: ' + result.error);
                        }}
                    }} catch (error) {{
                        alert('Error retrying download: ' + error.message);
                    }}
                }}
                
                async function deleteDownload(downloadId) {{
                    try {{
                        const response = await fetch(`/delete/${{downloadId}}`, {{ method: 'POST' }});
                        const result = await response.json();
                        
                        if (result.success) {{
                            console.log(`Deleted download: ${{result.message}}`);
                            if (result.removedFiles && result.removedFiles.length > 0) {{
                                console.log(`Cleaned up files: ${{result.removedFiles.join(', ')}}`);
                            }}
                            updateDownloads(); // Refresh the downloads list
                        }} else {{
                            alert('Failed to delete download: ' + result.error);
                        }}
                    }} catch (error) {{
                        alert('Error deleting download: ' + error.message);
                    }}
                }}
                
                async function clearDownload(downloadId) {{
                    try {{
                        const response = await fetch(`/clear/${{downloadId}}`, {{ method: 'POST' }});
                        const result = await response.json();
                        
                        if (result.success) {{
                            console.log(`Cleared download: ${{result.message}}`);
                            updateDownloads(); // Refresh the downloads list
                        }} else {{
                            alert('Failed to clear download: ' + result.error);
                        }}
                    }} catch (error) {{
                        alert('Error clearing download: ' + error.message);
                    }}
                }}
                
                
                let currentRetryFilename = null;
                
                async function retryPartialDownload(filename) {{
                    // Store the filename for later use
                    currentRetryFilename = filename;
                    
                    // First, check if we have a stored URL for this file
                    const fileData = filesData.find(file => file.name === filename);
                    if (fileData && fileData.url) {{
                        console.log('Found stored URL for file:', fileData.url);
                        try {{
                            const response = await fetch('/download', {{
                                method: 'POST',
                                headers: {{ 'Content-Type': 'application/json' }},
                                body: JSON.stringify({{
                                    url: fileData.url,
                                    title: filename.replace(/\\.(part|ytdl|temp)$/i, ''),
                                    isRetry: true
                                }})
                            }});
                            
                            const result = await response.json();
                            if (result.success) {{
                                alert('✅ Retry started using stored URL!');
                                updateDownloads();
                                return;
                            }}
                        }} catch (error) {{
                            console.log('Stored URL retry failed:', error);
                        }}
                    }}
                    
                    // If no stored URL or stored URL failed, try Chrome extension
                    try {{
                        console.log('Attempting to use Chrome extension for retry...');
                        
                        const extensionResponse = await new Promise((resolve, reject) => {{
                            if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.sendMessage) {{
                                chrome.runtime.sendMessage(
                                    {{ action: 'retryFromWebInterface', filename: filename }},
                                    (response) => {{
                                        if (chrome.runtime.lastError) {{
                                            reject(new Error('Extension communication failed: ' + chrome.runtime.lastError.message));
                                        }} else {{
                                            resolve(response);
                                        }}
                                    }}
                                );
                            }} else {{
                                reject(new Error('Chrome extension not available'));
                            }}
                        }});
                        
                        if (extensionResponse.success) {{
                            alert(`✅ ${{extensionResponse.message}}`);
                            updateDownloads(); // Refresh the downloads list
                            return;
                        }} else {{
                            console.log('Extension retry failed:', extensionResponse.error);
                            // Fall back to local search
                        }}
                    }} catch (extensionError) {{
                        console.log('Chrome extension not available for retry:', extensionError.message);
                        // Fall back to local search
                    }}
                    
                    // First, try to find a matching failed download with stored URL
                    try {{
                        const response = await fetch(`/find-failed-download-for-file/${{encodeURIComponent(filename)}}`);
                        const result = await response.json();
                        
                        if (result.success && result.failed_download) {{
                            // Found a matching failed download, start retry immediately without user input
                            console.log('Found matching failed download:', result.failed_download);
                            await startRetryWithStoredUrl(filename, result.failed_download);
                            return;
                        }}
                    }} catch (error) {{
                        console.log('No matching failed download found, searching browser history:', error);
                    }}
                    
                    // No stored URL found, search browser history for matching URL
                    await searchBrowserHistoryForUrl(filename);
                }}
                
                async function searchBrowserHistoryForUrl(filename) {{
                    try {{
                        // More aggressive cleaning to remove all file extensions and partial indicators
                        let searchTitle = filename
                            .replace(/\\.part$/, '')      // Remove .part
                            .replace(/\\.ytdl$/, '')      // Remove .ytdl  
                            .replace(/\\.temp$/, '')      // Remove .temp
                            .replace(/\\.crdownload$/, '') // Remove .crdownload
                            .replace(/\\.[a-zA-Z0-9]{{2,4}}$/, ''); // Remove common file extensions
                        
                        // Remove any remaining partial indicators
                        searchTitle = searchTitle
                            .replace(/\\s*\\(\\d+\\)$/, '') // Remove (1), (2) etc at end
                            .replace(/\\s*-\\s*Copy$/, '')   // Remove - Copy
                            .trim();
                        
                        console.log(`Searching browser history for: "${{searchTitle}}" (cleaned from "${{filename}}")`);
                        
                        // Search browser history (only available in Chrome extensions)
                        if (typeof chrome !== 'undefined' && chrome.history) {{
                            const historyItems = await new Promise((resolve) => {{
                                chrome.history.search({{
                                    text: '',
                                    maxResults: 3000,
                                    startTime: Date.now() - (30 * 24 * 60 * 60 * 1000) // Last 30 days
                                }}, resolve);
                            }});
                            
                            console.log(`Searching through ${{historyItems.length}} history items`);
                            
                            // Sort by visit time (most recent first)
                            const sortedItems = historyItems
                                .filter(item => item.title && item.url)
                                .sort((a, b) => b.lastVisitTime - a.lastVisitTime);
                            
                            // Find matching URLs with fuzzy search - try up to 4 attempts
                            const candidates = [];
                            
                            for (const item of sortedItems) {{
                                // Use strict video URL validation (same as suggestions)
                                function isValidVideoUrlSearch(url) {{
                                    const videoPatterns = [
                                        /youtube\\.com\\/watch\\?v=[a-zA-Z0-9_-]+(&.*)?$/i,
                                        /youtu\\.be\\/[a-zA-Z0-9_-]+$/i,
                                        /vimeo\\.com\\/\\d+$/i,
                                        /dailymotion\\.com\\/video\\/[a-zA-Z0-9_-]+$/i,
                                        /tiktok\\.com\\/.*\\/video\\/\\d+$/i,
                                        /instagram\\.com\\/p\\/[a-zA-Z0-9_-]+\\/$/i,
                                        /instagram\\.com\\/reel\\/[a-zA-Z0-9_-]+\\/$/i,
                                        /facebook\\.com\\/.*\\/videos\\/\\d+$/i,
                                        /twitter\\.com\\/.*\\/status\\/\\d+$/i,
                                        /x\\.com\\/.*\\/status\\/\\d+$/i,
                                        /twitch\\.tv\\/videos\\/\\d+$/i,
                                        /pornhub\\.com\\/view_video\\.php\\?viewkey=[a-zA-Z0-9_-]+(&.*)?$/i,
                                        /xvideos\\.com\\/video\\d+\\/[^/]+$/i,
                                        /xhamster\\.com\\/videos\\/[^/]+-\\d+$/i,
                                        /redtube\\.com\\/\\d+$/i,
                                        /tnaflix\\.com\\/.*\\/video\\/\\d+$/i,
                                        /eporner\\.com\\/video-[a-zA-Z0-9_-]+\\/[^/]+$/i,
                                        /xnxx\\.com\\/video-[a-zA-Z0-9_-]+\\/[^/]+$/i,
                                        /spankbang\\.com\\/[a-zA-Z0-9_-]+\\/video\\/[^/]+$/i
                                    ];
                                    return videoPatterns.some(pattern => pattern.test(url));
                                }}
                                
                                const isVideoUrl = isValidVideoUrlSearch(item.url);
                                
                                let score = 0;
                                let strategy = '';
                                
                                // Strategy 1: Exact substring match (case-insensitive)
                                if (item.title.toLowerCase().includes(searchTitle.toLowerCase())) {{
                                    score = 1.0;
                                    strategy = 'exact_match';
                                }} else if (searchTitle.toLowerCase().includes(item.title.toLowerCase()) && item.title.length > 8) {{
                                    score = 0.95;
                                    strategy = 'title_in_search';
                                }} else {{
                                    // Strategy 2: Fuzzy matching with Levenshtein-like algorithm
                                    score = calculateFuzzyMatch(searchTitle.toLowerCase(), item.title.toLowerCase());
                                    strategy = 'fuzzy_match';
                                    
                                    // Boost score for matching numbers/dates
                                    const searchNumbers = searchTitle.match(/\\d{{2,}}/g) || [];
                                    const titleNumbers = item.title.match(/\\d{{2,}}/g) || [];
                                    const numberMatches = searchNumbers.filter(num => titleNumbers.includes(num)).length;
                                    if (numberMatches > 0) {{
                                        score += 0.15 * numberMatches; // Boost for number matches
                                        strategy += '+numbers';
                                    }}
                                }}
                                
                                // Boost video URLs
                                if (isVideoUrl && score > 0.3) {{
                                    score += 0.1;
                                    strategy += '+video_url';
                                }}
                                
                                // Only consider matches above 90% similarity (0.9) as requested
                                if (score >= 0.9) {{
                                    candidates.push({{
                                        item: item,
                                        score: score,
                                        strategy: strategy,
                                        isVideoUrl: isVideoUrl
                                    }});
                                }}
                            }}
                            
                            // Sort candidates by score (highest first), then by video URL preference, then by recency
                            candidates.sort((a, b) => {{
                                if (Math.abs(a.score - b.score) < 0.01) {{
                                    if (a.isVideoUrl !== b.isVideoUrl) return a.isVideoUrl ? -1 : 1;
                                    return b.item.lastVisitTime - a.item.lastVisitTime;
                                }}
                                return b.score - a.score;
                            }});
                            
                            console.log(`Found ${{candidates.length}} candidates with 90%+ similarity`);
                            
                            // Try up to 4 candidates
                            for (let i = 0; i < Math.min(4, candidates.length); i++) {{
                                const candidate = candidates[i];
                                console.log(`Trying candidate ${{i + 1}}: ${{candidate.strategy}}, score: ${{candidate.score.toFixed(3)}}, title: "${{candidate.item.title}}", url: ${{candidate.item.url}}`);
                                
                                try {{
                                    const failed_download = {{
                                        url: candidate.item.url,
                                        title: candidate.item.title,
                                        open_folder: true
                                    }};
                                    
                                    await startRetryWithStoredUrl(filename, failed_download);
                                    return; // Success, exit function
                                }} catch (retryError) {{
                                    console.log(`Candidate ${{i + 1}} failed, trying next...`, retryError);
                                    continue;
                                }}
                            }}
                        }}
                        
                        // No suitable match found, open Chrome history
                        console.log('No matching URL found with 90%+ similarity, opening Chrome history');
                        
                        try {{
                            // Open Chrome history in a new tab
                            await chrome.tabs.create({{ 
                                url: 'chrome://history/',
                                active: true
                            }});
                            
                            // Show user a helpful message
                            alert(`Could not automatically find a matching URL for "${{searchTitle}}".\n\nOpened Chrome history for manual search. Look for the video page and try downloading again.`);
                        }} catch (historyError) {{
                            console.error('Could not open Chrome history:', historyError);
                            alert(`Could not find a matching URL for "${{searchTitle}}" and unable to open Chrome history.\n\nPlease manually search your browser history for the video page.`);
                        }}
                        
                    }} catch (error) {{
                        console.error('Error searching browser history:', error);
                        
                        // Provide helpful guidance for web interface users
                        if (typeof chrome === 'undefined' || !chrome.history) {{
                            alert(`Browser history access is not available in the web interface.

To retry "${{filename}}":

🔧 Option 1: Use VidSnatch Chrome Extension
   • The Chrome extension has history access and can automatically find the URL
   • Click the VidSnatch icon in your browser toolbar

📋 Option 2: Manual retry
   • Open Chrome history (Ctrl+H or Cmd+Y)
   • Search for the video title (without file extension)
   • Copy the video page URL
   • Paste it in the download box above

The web interface is limited by browser security - only extensions can access history.`);
                        }} else {{
                            alert(`Could not search browser history for "${{filename}}". Make sure the VidSnatch extension has history permission.`);
                        }}
                    }}
                }}
                
                function calculateFuzzyMatch(str1, str2) {{
                    // Simple fuzzy matching algorithm based on character overlap and position
                    if (!str1 || !str2) return 0;
                    
                    // Normalize strings
                    const s1 = str1.replace(/[^a-z0-9\\s]/g, ' ').replace(/\\s+/g, ' ').trim();
                    const s2 = str2.replace(/[^a-z0-9\\s]/g, ' ').replace(/\\s+/g, ' ').trim();
                    
                    if (s1 === s2) return 1.0;
                    
                    // Word-based similarity
                    const words1 = s1.split(' ').filter(w => w.length > 1);
                    const words2 = s2.split(' ').filter(w => w.length > 1);
                    
                    if (words1.length === 0 || words2.length === 0) return 0;
                    
                    let matchedWords = 0;
                    for (const word1 of words1) {{
                        for (const word2 of words2) {{
                            // Exact match
                            if (word1 === word2) {{
                                matchedWords += 1;
                                break;
                            }}
                            // Partial match for longer words
                            else if (word1.length > 3 && word2.length > 3) {{
                                if (word1.includes(word2) || word2.includes(word1)) {{
                                    matchedWords += 0.8;
                                    break;
                                }}
                                // Character overlap for similar words
                                const overlap = calculateCharOverlap(word1, word2);
                                if (overlap > 0.7) {{
                                    matchedWords += overlap * 0.6;
                                    break;
                                }}
                            }}
                        }}
                    }}
                    
                    return matchedWords / Math.max(words1.length, words2.length);
                }}
                
                function calculateCharOverlap(str1, str2) {{
                    if (!str1 || !str2) return 0;
                    const len1 = str1.length;
                    const len2 = str2.length;
                    const maxLen = Math.max(len1, len2);
                    
                    let matches = 0;
                    for (let i = 0; i < Math.min(len1, len2); i++) {{
                        if (str1[i] === str2[i]) matches++;
                    }}
                    
                    return matches / maxLen;
                }}
                
                function calculateSimilarity(str1, str2) {{
                    // Simple word-based similarity calculation
                    const words1 = str1.split(' ').filter(w => w.length > 2);
                    const words2 = str2.split(' ').filter(w => w.length > 2);
                    
                    if (words1.length === 0 || words2.length === 0) return 0;
                    
                    let matches = 0;
                    for (const word1 of words1) {{
                        for (const word2 of words2) {{
                            if (word1 === word2 || word1.includes(word2) || word2.includes(word1)) {{
                                matches++;
                                break;
                            }}
                        }}
                    }}
                    
                    return matches / Math.max(words1.length, words2.length);
                }}
                
                async function startRetryWithStoredUrl(filename, failed_download) {{
                    try {{
                        // Show loading state for this file
                        showFileLoadingState(filename);
                        
                        // Start the download using stored URL
                        const response = await fetch('/download', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                            }},
                            body: JSON.stringify({{
                                url: failed_download.url,
                                title: failed_download.title,
                                openFolder: failed_download.open_folder || true
                            }})
                        }});
                        
                        const result = await response.json();
                        
                        if (result.success) {{
                            console.log(`🔄 Auto-retry started for: ${{filename}}`);
                            console.log(`Download ID: ${{result.downloadId}}`);
                            
                            // Wait a moment then refresh the file list
                            setTimeout(() => {{
                                loadDownloadedFiles();
                                loadActiveDownloads();
                            }}, 1000);
                        }} else {{
                            hideFileLoadingState(filename);
                            alert('Failed to retry download: ' + (result.error || 'Unknown error'));
                        }}
                    }} catch (error) {{
                        hideFileLoadingState(filename);
                        console.error('Error during auto-retry:', error);
                        alert('Error during auto-retry: ' + error.message);
                    }}
                }}
                
                
                function showFileLoadingState(filename) {{
                    // Find the file row and replace retry/delete buttons with loading spinner
                    const fileElements = document.querySelectorAll('.file-item');
                    for (const fileElement of fileElements) {{
                        const filenameElement = fileElement.querySelector('.file-name');
                        if (filenameElement && filenameElement.textContent.trim() === filename) {{
                            const actionsElement = fileElement.querySelector('.file-actions');
                            if (actionsElement) {{
                                actionsElement.innerHTML = `
                                    <div class="file-loading">
                                        <div class="loading-spinner"></div>
                                        <span>Retrying download...</span>
                                    </div>
                                `;
                            }}
                            break;
                        }}
                    }}
                }}
                
                function hideFileLoadingState(filename) {{
                    // Refresh the file list to restore normal state
                    loadDownloadedFiles();
                }}
                
                function highlightPlayingVideo(filename) {{
                    // Clear any existing highlighting
                    clearVideoHighlighting();
                    
                    // Find and highlight the playing video in the table
                    const tableRows = document.querySelectorAll('.files-table tbody tr');
                    for (const row of tableRows) {{
                        if (row.getAttribute('data-filename') === filename) {{
                            row.classList.add('playing');
                            break;
                        }}
                    }}
                }}
                
                function clearVideoHighlighting() {{
                    // Remove playing class from all table rows
                    const playingRows = document.querySelectorAll('.files-table tbody tr.playing');
                    playingRows.forEach(row => {{
                        row.classList.remove('playing');
                    }});
                }}
                
                async function submitUrlRetry() {{
                    const url = document.getElementById('urlInput').value.trim();
                    
                    if (!url) {{
                        alert('Please enter a URL');
                        return;
                    }}
                    
                    if (!url.includes('http')) {{
                        alert('Please enter a valid URL starting with http:// or https://');
                        return;
                    }}
                    
                    if (!currentRetryFilename) {{
                        alert('Error: No filename specified');
                        return;
                    }}
                    
                    try {{
                        // Save filename before closing modal (since closeUrlModal sets it to null)
                        const filename = currentRetryFilename;
                        
                        // Close modal
                        closeUrlModal();
                        
                        // Show loading state
                        showFileLoadingState(filename);
                        
                        // Extract title from filename (remove .part extension)
                        const title = filename.replace(/\\.part$/, '').replace(/\\.ytdl$/, '').replace(/\\.temp$/, '');
                        
                        // Start the download
                        const response = await fetch('/download', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                            }},
                            body: JSON.stringify({{
                                url: url,
                                title: title,
                                openFolder: true
                            }})
                        }});
                        
                        const result = await response.json();
                        
                        if (result.success) {{
                            console.log(`🔄 Manual retry started for: ${{filename}}`);
                            console.log(`Download ID: ${{result.downloadId}}`);
                            
                            // Wait a moment then refresh the file list
                            setTimeout(() => {{
                                loadDownloadedFiles();
                                loadActiveDownloads();
                            }}, 1000);
                        }} else {{
                            hideFileLoadingState(filename);
                            alert('Failed to retry download: ' + (result.error || 'Unknown error'));
                        }}
                        
                    }} catch (error) {{
                        hideFileLoadingState(filename);
                        console.error('Error retrying partial download:', error);
                        alert('Error retrying download: ' + error.message);
                    }}
                }}
                
                async function deletePartialFile(filename) {{
                    if (confirm(`Are you sure you want to delete the partial file "${{filename}}"?\\n\\nThis action cannot be undone.`)) {{
                        try {{
                            const response = await fetch(`/delete-partial-file/${{encodeURIComponent(filename)}}`, {{
                                method: 'POST'
                            }});
                            
                            const result = await response.json();
                            
                            if (result.success) {{
                                alert(`🗑️ Deleted partial file: ${{filename}}`);
                                // Refresh the file list
                                loadDownloadedFiles();
                            }} else {{
                                alert('Failed to delete file: ' + result.message);
                            }}
                            
                        }} catch (error) {{
                            console.error('Error deleting partial file:', error);
                            alert('Error deleting file: ' + error.message);
                        }}
                    }}
                }}
                
                let currentVideoFile = null;
                let videoFilesList = [];
                let currentVideoIndex = -1;
                
                async function playVideo(filename) {{
                    try {{
                        const videoPlayerSection = document.getElementById('videoPlayerSection');
                        const videoPlayer = document.getElementById('videoPlayer');
                        const videoSource = document.getElementById('videoSource');
                        const videoTitle = document.getElementById('videoTitle');
                        const videoMeta = document.getElementById('videoMeta');
                        const openExternalBtn = document.getElementById('openExternalBtn');
                        
                        // Store current video file for external opening
                        currentVideoFile = filename;
                        
                        // Update current video index
                        currentVideoIndex = videoFilesList.indexOf(filename);
                        updateNavButtons();
                        
                        // Set video source to serve the file through our server
                        const videoUrl = `/stream-video/${{encodeURIComponent(filename)}}`;
                        videoSource.src = videoUrl;
                        videoPlayer.load(); // Reload video element with new source
                        
                        // Set default volume to 25%
                        videoPlayer.volume = 0.25;
                        
                        // Update video info
                        videoTitle.textContent = filename;
                        videoMeta.textContent = 'Loading video...';
                        
                        // Show video player
                        videoPlayerSection.classList.add('active');
                        openExternalBtn.style.display = 'flex';
                        
                        // Try to load video metadata
                        videoPlayer.addEventListener('loadedmetadata', function() {{
                            const duration = formatDuration(videoPlayer.duration);
                            videoMeta.textContent = `Duration: ${{duration}}`;
                        }}, {{ once: true }});
                        
                        videoPlayer.addEventListener('error', function(e) {{
                            videoMeta.textContent = 'Error loading video';
                            console.error('Video loading error:', e);
                        }}, {{ once: true }});
                        
                        // Highlight the playing video in file list
                        highlightPlayingVideo(filename);
                        
                        // Scroll to video player
                        videoPlayerSection.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                        
                    }} catch (error) {{
                        console.error('Error playing video:', error);
                        alert('Error playing video: ' + error.message);
                    }}
                }}
                
                function closeVideoPlayer() {{
                    const videoPlayerSection = document.getElementById('videoPlayerSection');
                    const videoPlayer = document.getElementById('videoPlayer');
                    const openExternalBtn = document.getElementById('openExternalBtn');
                    
                    // Hide video player
                    videoPlayerSection.classList.remove('active');
                    
                    // Stop and clear video
                    videoPlayer.pause();
                    videoPlayer.currentTime = 0;
                    document.getElementById('videoSource').src = '';
                    videoPlayer.load();
                    
                    // Reset info
                    document.getElementById('videoTitle').textContent = 'No video selected';
                    document.getElementById('videoMeta').textContent = 'Select a video from the Downloaded Files section to play';
                    openExternalBtn.style.display = 'none';
                    
                    // Remove highlighting from all videos
                    clearVideoHighlighting();
                    
                    currentVideoFile = null;
                    currentVideoIndex = -1;
                }}
                
                function updateNavButtons() {{
                    const prevBtn = document.getElementById('prevVideoBtn');
                    const nextBtn = document.getElementById('nextVideoBtn');
                    
                    if (prevBtn && nextBtn) {{
                        prevBtn.disabled = currentVideoIndex <= 0;
                        nextBtn.disabled = currentVideoIndex >= videoFilesList.length - 1;
                        
                        // Update button styles based on disabled state
                        prevBtn.style.opacity = prevBtn.disabled ? '0.5' : '1';
                        nextBtn.style.opacity = nextBtn.disabled ? '0.5' : '1';
                        prevBtn.style.cursor = prevBtn.disabled ? 'not-allowed' : 'pointer';
                        nextBtn.style.cursor = nextBtn.disabled ? 'not-allowed' : 'pointer';
                    }}
                }}
                
                function playPreviousVideo() {{
                    if (currentVideoIndex > 0 && videoFilesList.length > 0) {{
                        const prevVideo = videoFilesList[currentVideoIndex - 1];
                        playVideo(prevVideo);
                    }}
                }}
                
                function playNextVideo() {{
                    if (currentVideoIndex < videoFilesList.length - 1 && videoFilesList.length > 0) {{
                        const nextVideo = videoFilesList[currentVideoIndex + 1];
                        playVideo(nextVideo);
                    }}
                }}
                
                async function openVideoInExternal() {{
                    if (currentVideoFile) {{
                        try {{
                            const response = await fetch(`/open-file/${{encodeURIComponent(currentVideoFile)}}`);
                            const result = await response.json();
                            
                            if (!result.status === 'success') {{
                                alert('Failed to open video externally: ' + result.message);
                            }}
                        }} catch (error) {{
                            alert('Error opening video externally: ' + error.message);
                        }}
                    }}
                }}
                
                function formatDuration(seconds) {{
                    if (isNaN(seconds)) return 'Unknown';
                    
                    const hours = Math.floor(seconds / 3600);
                    const minutes = Math.floor((seconds % 3600) / 60);
                    const secs = Math.floor(seconds % 60);
                    
                    if (hours > 0) {{
                        return `${{hours}}:${{minutes.toString().padStart(2, '0')}}:${{secs.toString().padStart(2, '0')}}`;
                    }} else {{
                        return `${{minutes}}:${{secs.toString().padStart(2, '0')}}`;
                    }}
                }}
                
                function parseDurationToSeconds(durationStr) {{
                    if (!durationStr || durationStr === 'Unknown' || durationStr === '—') return 0;
                    
                    // Convert to string if it's not already
                    const durStr = String(durationStr);
                    
                    // Handle duration strings like \"5:30\" or \"1:23:45\"
                    const parts = durStr.split(':').map(p => parseInt(p, 10));
                    
                    if (parts.length === 2) {{
                        // Format: \"MM:SS\"
                        const [minutes, seconds] = parts;
                        return (minutes * 60) + seconds;
                    }} else if (parts.length === 3) {{
                        // Format: \"HH:MM:SS\"
                        const [hours, minutes, seconds] = parts;
                        return (hours * 3600) + (minutes * 60) + seconds;
                    }}
                    
                    // If it's just a number, assume it's already in seconds
                    const numValue = parseFloat(durStr);
                    return isNaN(numValue) ? 0 : numValue;
                }}
                
                async function loadSuggestions() {{
                    const loadBtn = document.getElementById('loadSuggestionsBtn');
                    const suggestedContainer = document.getElementById('suggestedContainer');
                    const scanStatus = document.getElementById('scanStatus');
                    const suggestedDownloads = document.getElementById('suggestedDownloads');
                    
                    // Show loading state
                    loadBtn.disabled = true;
                    loadBtn.textContent = 'Loading...';
                    suggestedContainer.style.display = 'block';
                    scanStatus.textContent = 'Scanning browser history...';
                    suggestedDownloads.innerHTML = '';
                    
                    try {{
                        // Use postMessage to communicate with Chrome extension via content script
                        const requestId = 'suggestions_' + Date.now();
                        
                        const response = await new Promise((resolve, reject) => {{
                            const timeout = setTimeout(() => {{
                                reject(new Error('Extension communication timeout. Make sure the VidSnatch Chrome extension is installed and enabled.'));
                            }}, 10000); // 10 second timeout
                            
                            const messageHandler = (event) => {{
                                if (event.data.action === 'scanSuggestedDownloadsResponse' && 
                                    event.data.requestId === requestId) {{
                                    clearTimeout(timeout);
                                    window.removeEventListener('message', messageHandler);
                                    resolve(event.data.response);
                                }}
                            }};
                            
                            window.addEventListener('message', messageHandler);
                            
                            // Send message to content script
                            window.postMessage({{
                                action: 'scanSuggestedDownloads',
                                requestId: requestId,
                                days: 7
                            }}, window.location.origin);
                        }});
                        
                        if (response.success) {{
                            const suggestions = response.suggestions || [];
                            displaySuggestions(suggestions);
                            scanStatus.textContent = `Found ${{suggestions.length}} suggested downloads`;
                        }} else {{
                            scanStatus.textContent = 'Error: ' + response.error;
                            suggestedDownloads.innerHTML = `
                                <div style="text-align: center; padding: 20px; color: var(--secondary-text-color);">
                                    ${{response.error}}
                                </div>
                            `;
                        }}
                    }} catch (error) {{
                        console.error('Error loading suggestions:', error);
                        scanStatus.textContent = 'Error loading suggestions';
                        suggestedDownloads.innerHTML = `
                            <div style="text-align: center; padding: 20px; color: var(--secondary-text-color);">
                                ${{error.message}}
                            </div>
                        `;
                    }}
                    
                    // Reset button
                    loadBtn.disabled = false;
                    loadBtn.textContent = 'Reload Suggestions';
                }}
                
                function displaySuggestions(suggestions) {{
                    const suggestedDownloads = document.getElementById('suggestedDownloads');
                    
                    // Filter out deleted URLs
                    const filteredSuggestions = suggestions.filter(suggestion => !isUrlDeleted(suggestion.url));
                    
                    if (filteredSuggestions.length === 0) {{
                        suggestedDownloads.innerHTML = `
                            <div style="text-align: center; padding: 20px; color: var(--secondary-text-color);">
                                No suggested downloads found. Visit video sites more frequently to get suggestions.
                            </div>
                        `;
                        return;
                    }}
                    
                    const suggestionsHtml = filteredSuggestions.map(suggestion => {{
                        // Escape single quotes for onclick attributes
                        const escapedUrl = suggestion.url.replace(/'/g, "\\'");
                        const escapedTitle = suggestion.title.replace(/'/g, "\\'");
                        
                        return `
                            <div class="suggestion-item">
                                <div class="suggestion-title" title="${{suggestion.title}}">${{suggestion.title}}</div>
                                <div class="suggestion-url" onclick="openUrlInNewTab('${{escapedUrl}}')" title="Click to open URL">${{suggestion.url}}</div>
                                <div class="suggestion-meta">Visited ${{suggestion.visitCount}} times</div>
                                <div class="suggestion-actions">
                                    <button class="suggestion-btn download" onclick="downloadSuggestion('${{escapedUrl}}', '${{escapedTitle}}')">
                                        Download
                                    </button>
                                    <button class="suggestion-btn delete" onclick="deleteSuggestion('${{escapedUrl}}')">
                                        Delete
                                    </button>
                                </div>
                            </div>
                        `;
                    }}).join('');
                    
                    suggestedDownloads.innerHTML = suggestionsHtml;
                }}
                
                function deleteSuggestion(url) {{
                    // Mark URL as deleted permanently
                    markUrlAsDeleted(url);
                    
                    // Find and remove the suggestion item from the display
                    const suggestionItems = document.querySelectorAll('.suggestion-item');
                    suggestionItems.forEach(item => {{
                        const urlElement = item.querySelector('.suggestion-url');
                        if (urlElement && urlElement.textContent === url) {{
                            item.remove();
                        }}
                    }});
                    
                    // Update the count
                    const remainingCount = document.querySelectorAll('.suggestion-item').length;
                    const scanStatus = document.getElementById('scanStatus');
                    scanStatus.textContent = `Found ${{remainingCount}} suggested downloads`;
                }}
                
                // Search/Filter functionality
                let filteredFilesData = [];
                
                function filterFiles(searchTerm) {{
                    const term = searchTerm.toLowerCase().trim();
                    
                    if (!term) {{
                        // Show all files if search is empty
                        filteredFilesData = [...filesData];
                    }} else {{
                        // Filter files based on search term
                        filteredFilesData = filesData.filter(file => {{
                            // Search in filename
                            const nameMatch = file.name.toLowerCase().includes(term);
                            
                            // Search in URL
                            const urlMatch = (file.url || '').toLowerCase().includes(term);
                            
                            // Search in tags
                            const fileTags = getFileTags(file.name);
                            const tagsMatch = fileTags.some(tag => tag.toLowerCase().includes(term));
                            
                            // Search in person name
                            const personName = getPersonName(file.name) || '';
                            const personMatch = personName.toLowerCase().includes(term);
                            
                            return nameMatch || urlMatch || tagsMatch || personMatch;
                        }});
                    }}
                    
                    // Re-render table with filtered data
                    renderFilteredFilesTable();
                }}
                
                function renderFilteredFilesTable() {{
                    const fileExplorer = document.getElementById('fileExplorer');
                    
                    if (!filteredFilesData.length) {{
                        if (!filesData.length) {{
                            fileExplorer.innerHTML = '<div class="empty-state">No files found in downloads folder</div>';
                        }} else {{
                            fileExplorer.innerHTML = '<div class="empty-state">No files match your search</div>';
                        }}
                        return;
                    }}
                    
                    // Use the existing table rendering logic but with filtered data
                    const tempOriginalData = filesData;
                    filesData = filteredFilesData;
                    renderFilesTable();
                    filesData = tempOriginalData; // Restore original data
                }}
                
                // Tags system storage and management
                const fileTags = JSON.parse(localStorage.getItem('fileTags') || '{{}}');
                
                function getFileTags(filename) {{
                    return fileTags[filename] || [];
                }}
                
                function setFileTags(filename, tags) {{
                    if (tags && tags.length > 0) {{
                        fileTags[filename] = tags.slice(0, 5); // Limit to 5 tags
                    }} else {{
                        delete fileTags[filename];
                    }}
                    localStorage.setItem('fileTags', JSON.stringify(fileTags));
                }}
                
                function editTags(filename) {{
                    const container = document.querySelector(`[data-filename="${{filename}}"]`);
                    if (!container) return;
                    
                    const display = container.querySelector('.tags-display');
                    const editor = container.querySelector('.tags-editor');
                    const input = container.querySelector('.tags-input');
                    
                    // Show editor, hide display
                    display.style.display = 'none';
                    editor.style.display = 'block';
                    
                    // Set current tags as comma-separated string
                    const currentTags = getFileTags(filename);
                    input.value = currentTags.join(', ');
                    input.focus();
                    input.select();
                }}
                
                function saveTags(filename) {{
                    const container = document.querySelector(`[data-filename="${{filename}}"]`);
                    if (!container) return;
                    
                    const display = container.querySelector('.tags-display');
                    const editor = container.querySelector('.tags-editor');
                    const input = container.querySelector('.tags-input');
                    
                    // Parse tags from input
                    const tagString = input.value.trim();
                    const tags = tagString ? tagString.split(',').map(tag => tag.trim()).filter(tag => tag.length > 0) : [];
                    
                    // Save tags
                    setFileTags(filename, tags);
                    
                    // Update display
                    updateTagsDisplay(filename);
                    
                    // Show display, hide editor
                    display.style.display = 'flex';
                    editor.style.display = 'none';
                }}
                
                function handleTagsKeypress(event, filename) {{
                    if (event.key === 'Enter') {{
                        event.preventDefault();
                        saveTags(filename);
                    }} else if (event.key === 'Escape') {{
                        event.preventDefault();
                        cancelTagsEdit(filename);
                    }}
                }}
                
                function cancelTagsEdit(filename) {{
                    const container = document.querySelector(`[data-filename="${{filename}}"]`);
                    if (!container) return;
                    
                    const display = container.querySelector('.tags-display');
                    const editor = container.querySelector('.tags-editor');
                    
                    // Show display, hide editor
                    display.style.display = 'flex';
                    editor.style.display = 'none';
                }}
                
                function updateTagsDisplay(filename) {{
                    const container = document.querySelector(`[data-filename="${{filename}}"]`);
                    if (!container) return;
                    
                    const chipsContainer = container.querySelector('.tags-chips');
                    const tags = getFileTags(filename);
                    
                    if (tags.length === 0) {{
                        chipsContainer.innerHTML = '';
                    }} else {{
                        const tagsHTML = tags.map(tag => `
                            <span class="tag-chip" title="${{tag}}" onclick="addTagToSearch('${{escapeFilename(tag)}}')">
                                <span>${{tag}}</span>
                                <span class="tag-remove" onclick="event.stopPropagation(); removeTag('${{escapeFilename(filename)}}', '${{escapeFilename(tag)}}')">&times;</span>
                            </span>
                        `).join('');
                        chipsContainer.innerHTML = tagsHTML;
                    }}
                }}
                
                function initializeAllTagsDisplays() {{
                    // Initialize tags display for all files
                    document.querySelectorAll('.tags-input-container').forEach(container => {{
                        const filename = container.getAttribute('data-filename');
                        if (filename) {{
                            updateTagsDisplay(filename);
                        }}
                    }});
                }}
                
                function handleTagInputKeydown(event, filename) {{
                    const input = event.target;
                    const value = input.value.trim();
                    
                    // Handle Enter, Space, Comma, or Tab to create tags
                    if ((event.key === 'Enter' || event.key === ' ' || event.key === ',' || event.key === 'Tab') && value) {{
                        event.preventDefault();
                        addTag(filename, value);
                        input.value = '';
                    }}
                    // Handle Backspace on empty input to remove last tag
                    else if (event.key === 'Backspace' && !value) {{
                        const tags = getFileTags(filename);
                        if (tags.length > 0) {{
                            removeTag(filename, tags[tags.length - 1]);
                        }}
                    }}
                }}
                
                function handleTagInputBlur(event, filename) {{
                    const input = event.target;
                    const value = input.value.trim();
                    
                    if (value) {{
                        addTag(filename, value);
                        input.value = '';
                    }}
                }}
                
                function handleTagInputFocus(event, filename) {{
                    // Optional: Add focus styling or behavior
                    event.target.style.outline = 'none';
                }}
                
                function addTag(filename, tagText) {{
                    if (!tagText) return;
                    
                    const currentTags = getFileTags(filename);
                    const newTag = tagText.trim();
                    
                    // Avoid duplicates and limit to 5 tags
                    if (!currentTags.includes(newTag) && currentTags.length < 5) {{
                        const updatedTags = [...currentTags, newTag];
                        setFileTags(filename, updatedTags);
                        updateTagsDisplay(filename);
                    }}
                }}
                
                function removeTag(filename, tagToRemove) {{
                    const currentTags = getFileTags(filename);
                    const updatedTags = currentTags.filter(tag => tag !== tagToRemove);
                    setFileTags(filename, updatedTags);
                    updateTagsDisplay(filename);
                }}
                
                function addTagToSearch(tag) {{
                    const searchInput = document.getElementById('fileSearchBar');
                    const currentValue = searchInput.value.trim();
                    
                    // Check if tag is already in the search
                    if (currentValue.toLowerCase().includes(tag.toLowerCase())) {{
                        return;
                    }}
                    
                    // Add tag to search with a space if there's existing content
                    if (currentValue) {{
                        searchInput.value = currentValue + ' ' + tag;
                    }} else {{
                        searchInput.value = tag;
                    }}
                    
                    // Trigger the filter
                    filterFiles(searchInput.value);
                    
                    // Focus the search input
                    searchInput.focus();
                }}

                async function openUninstaller() {{
                    try {{
                        const response = await fetch('/uninstall');
                        const result = await response.json();
                        
                        if (result.status === 'success') {{
                            alert('Finder opened to uninstaller location. Look for "uninstall-vidsnatch.sh" and double-click to run it.');
                        }} else {{
                            alert('Error: ' + result.message);
                        }}
                    }} catch (error) {{
                        alert('Failed to open uninstaller: ' + error.message);
                    }}
                }}
            </script>
        </body>
        </html>
        """
    
    def log_message(self, format, *args):
        """Override to customize log messages."""
        print(f" [API] {format % args}")

def clean_stuck_downloads():
    """Clean up downloads stuck in preparing state for too long."""
    current_time = time.time()
    stuck_timeout = 30  # Consider stuck after 30 seconds in preparing state
    
    with download_lock:
        stuck_downloads = []
        for download_id, progress in list(active_downloads.items()):
            # Check if download is stuck in preparing state
            if progress.status == 'preparing':
                runtime = current_time - progress.start_time
                if runtime > stuck_timeout:
                    stuck_downloads.append((download_id, progress))
        
        # Clean up stuck downloads
        for download_id, progress in stuck_downloads:
            runtime = current_time - progress.start_time
            print(f" [!] Cleaning stuck download: {progress.title} (stuck in preparing for {runtime:.0f}s)")
            progress.status = 'failed'
            progress.error = 'Download stuck in preparing state'
            
            # Move to failed downloads
            failed_downloads[download_id] = {
                'title': progress.title,
                'url': progress.url,
                'error': 'Stuck in preparing state - cleaned up',
                'retry_count': getattr(progress, 'retry_count', 0),
                'failed_at': current_time
            }
            
            del active_downloads[download_id]
        
        if stuck_downloads:
            save_active_downloads()
            save_failed_downloads()
            print(f" [+] Cleaned {len(stuck_downloads)} stuck downloads")

def monitor_downloads():
    """Background thread to monitor and clean stuck downloads."""
    while True:
        time.sleep(30)  # Check every 30 seconds
        try:
            clean_stuck_downloads()
        except Exception as e:
            print(f" [!] Error in download monitor: {e}")

def auto_retry_incomplete_downloads(handler_class):
    """Automatically retry incomplete downloads from URL tracker."""
    tracker = get_tracker()
    incomplete = tracker.get_incomplete_urls()
    
    if incomplete:
        print(f" [+] Found {len(incomplete)} incomplete downloads to retry")
        
        # Instead of broken auto-retry, just mark them as failed for manual retry
        for url_track_id, url_data in incomplete:
            try:
                # Create a failed download entry
                download_id = str(uuid.uuid4())
                failed_downloads[download_id] = {
                    'title': url_data['title'],
                    'url': url_data['url'],
                    'error': 'Download interrupted by server restart',
                    'retry_count': url_data.get('attempts', 0),
                    'failed_at': time.time()
                }
                print(f" [!] Marked as failed: {url_data['title']}")
                tracker.mark_failed(url_track_id, "Server restart - marked for manual retry")
                
            except Exception as e:
                print(f" [!] Error processing incomplete download {url_data['title']}: {e}")

def start_server(port=8080):
    """Start the enhanced Quikvid-DL web server."""
    server_address = ('localhost', port)
    httpd = HTTPServer(server_address, QuikvidHandler)
    
    # Initialize URL tracker
    init_tracker(os.path.expanduser("~/Applications/VidSnatch/.logs/url_tracker.json"))
    
    # Load interrupted downloads from previous session
    load_active_downloads()
    
    # Load failed downloads from storage
    load_failed_downloads()
    
    server_logger.info(f"Starting Enhanced VidSnatch Server on http://localhost:{port}")
    server_logger.info("Logging enabled - check .logs/server.log for detailed logs")
    print(f" [+] Starting Enhanced VidSnatch Server on http://localhost:{port}")
    print(f" [+] Features: Progress tracking, cancellation, folder control, retry/delete")
    print(f" [+] Chrome extension ready for enhanced downloads")
    print(f" [+] Logs saved to .logs/server.log (circular buffer: 15MB total)")
    print(f" [+] Press Ctrl+C to stop the server")
    
    # Auto-retry incomplete downloads after a short delay
    def delayed_auto_retry():
        time.sleep(5)  # Wait 5 seconds for server to fully start
        auto_retry_incomplete_downloads(QuikvidHandler)
    
    retry_thread = threading.Thread(target=delayed_auto_retry)
    retry_thread.daemon = True
    retry_thread.start()
    
    # Start monitor thread to clean stuck downloads
    monitor_thread = threading.Thread(target=monitor_downloads)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # Clean any currently stuck downloads immediately
    clean_stuck_downloads()
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n [+] Server stopped")
        httpd.server_close()

if __name__ == "__main__":
    start_server()