"""Enhanced web server for Chrome extension integration with Quikvid-DL."""

import json
import os
import sys
import threading
import time
import uuid
import signal
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Import with dependency check like main.py
import modules.config as config
import modules.utilities as utilities

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

class DownloadProgress:
    """Track download progress and status."""
    def __init__(self, download_id, url, title):
        self.download_id = download_id
        self.url = url
        self.title = title
        self.status = 'preparing'  # preparing, downloading, processing, completed, error, cancelled
        self.percent = 0.0
        self.speed = ''
        self.eta = ''
        self.error = None
        self.cancelled = False
        self.process = None
        self.start_time = time.time()

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
        elif parsed_path.path == '/select-folder':
            self.handle_folder_selection_request()
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
    
    def handle_cancel_request(self, download_id):
        """Handle download cancellation requests."""
        with download_lock:
            if download_id not in active_downloads:
                self.send_json_response({'error': 'Download not found'}, status=404)
                return
            
            progress = active_downloads[download_id]
            progress.cancelled = True
            progress.status = 'cancelled'
            
            # Try to terminate the process if it exists
            if progress.process:
                try:
                    progress.process.terminate()
                    # Give it a moment to terminate gracefully
                    time.sleep(1)
                    if progress.process.poll() is None:
                        progress.process.kill()
                except:
                    pass
            
            print(f" [!] Download cancelled: {progress.title}")
            self.send_json_response({'success': True, 'message': 'Download cancelled'})
            
            # Clean up any partial files
            self.cleanup_partial_files(progress)
    
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
                        except:
                            pass
        except Exception as e:
            print(f" [!] Error cleaning up files: {e}")
    
    def handle_current_folder_request(self):
        """Handle request for current download folder."""
        try:
            current_path = config.get_video_download_path()
            self.send_json_response({
                'success': True,
                'path': current_path
            })
        except Exception as e:
            print(f" [!] Error getting current folder: {e}")
            self.send_json_response({'error': str(e)}, status=500)
    
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
    
    def handle_download_request(self):
        """Handle download requests from Chrome extension."""
        try:
            # Get request body
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            # Parse JSON data
            data = json.loads(post_data.decode('utf-8'))
            url = data.get('url')
            title = data.get('title', 'Unknown')
            open_folder = data.get('openFolder', True)
            
            if not url:
                self.send_json_response({'error': 'No URL provided'}, status=400)
                return
            
            # Generate unique download ID
            download_id = str(uuid.uuid4())
            
            # Create progress tracker
            progress = DownloadProgress(download_id, url, title)
            
            with download_lock:
                active_downloads[download_id] = progress
            
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
            
            progress.status = 'downloading'
            print(f" [+] Starting download: {progress.title}")
            
            # Create yt-dlp options with progress hook
            ydl_opts = {
                'outtmpl': os.path.join(download_path, config.DEFAULT_OUTPUT_TEMPLATE),
                'progress_hooks': [lambda d: self.progress_hook(d, progress)],
            }
            
            # Download with yt-dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if progress.cancelled:
                    return
                
                progress.status = 'downloading'
                ydl.extract_info(progress.url, download=True)
            
            if not progress.cancelled:
                progress.status = 'completed'
                progress.percent = 100.0
                print(f" [+] Download completed: {progress.title}")
                
                # Open finder on macOS if requested
                if open_folder and sys.platform == 'darwin':
                    videoDownloader.open_finder(download_path)
            
        except Exception as e:
            if not progress.cancelled:
                progress.status = 'error'
                progress.error = str(e)
                print(f" [!] Download error: {e}")
        finally:
            # Clean up from active downloads after 5 minutes
            def cleanup():
                time.sleep(300)  # 5 minutes
                with download_lock:
                    if progress.download_id in active_downloads:
                        del active_downloads[progress.download_id]
            
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
            
        elif d['status'] == 'finished':
            progress.status = 'processing'
            progress.percent = 100.0
    
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
        """Get enhanced web interface HTML."""
        active_count = len(active_downloads)
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Quikvid-DL Server</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
                .status {{ background: #e8f5e8; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .info {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .downloads {{ background: #fff3e0; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                code {{ background: #f5f5f5; padding: 2px 4px; border-radius: 3px; }}
                .progress-bar {{ width: 100%; height: 10px; background: #eee; border-radius: 5px; margin: 5px 0; }}
                .progress-fill {{ height: 100%; background: #4caf50; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <h1>🎬 VidSnatch Server Enhanced</h1>
            <div class="status">
                <strong>✅ Server Status:</strong> Running on http://localhost:8080<br>
                <strong>📊 Active Downloads:</strong> {active_count}
            </div>
            <div class="info">
                <h3>🚀 Chrome Extension Features</h3>
                <ul>
                    <li>✅ <strong>Real-time Progress:</strong> Visual progress bar with percentage, speed, and ETA</li>
                    <li>✅ <strong>Cancel Downloads:</strong> Stop downloads and clean up partial files</li>
                    <li>✅ <strong>Folder Control:</strong> Toggle automatic folder opening</li>
                    <li>✅ <strong>Smart Detection:</strong> Auto-detects videos on 1000+ sites</li>
                </ul>
            </div>
            <div class="info">
                <h3>📡 Enhanced API Endpoints</h3>
                <ul>
                    <li><code>GET /status</code> - Check server status</li>
                    <li><code>POST /download</code> - Start video download with progress tracking</li>
                    <li><code>GET /progress/{{id}}</code> - Get real-time download progress</li>
                    <li><code>POST /cancel/{{id}}</code> - Cancel active download</li>
                </ul>
            </div>
            <div class="downloads">
                <h3>📥 How to Use Enhanced Extension</h3>
                <ol>
                    <li>Navigate to any video site (YouTube, TikTok, etc.)</li>
                    <li>Click the Quikvid-DL extension icon</li>
                    <li>Watch real-time progress with speed and ETA</li>
                    <li>Use cancel button if needed</li>
                    <li>Toggle folder opening in settings</li>
                </ol>
            </div>
        </body>
        </html>
        """
    
    def log_message(self, format, *args):
        """Override to customize log messages."""
        print(f" [API] {format % args}")

def start_server(port=8080):
    """Start the enhanced Quikvid-DL web server."""
    server_address = ('localhost', port)
    httpd = HTTPServer(server_address, QuikvidHandler)
    
    print(f" [+] Starting Enhanced VidSnatch Server on http://localhost:{port}")
    print(f" [+] Features: Progress tracking, cancellation, folder control")
    print(f" [+] Chrome extension ready for enhanced downloads")
    print(f" [+] Press Ctrl+C to stop the server")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n [+] Server stopped")
        httpd.server_close()

if __name__ == "__main__":
    start_server()