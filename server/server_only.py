"""Standalone web server for Chrome extension integration."""

import sys
import signal
import modules.utilities as utilities
import modules.config as config

# Clear screen and check dependencies like main.py
utilities.clear()

# Display the VidSnatch logo
try:
    import modules.logo as logo
    logo.print_startup_logo()
except ImportError:
    print(" VidSnatch - Fast Video Downloader")
    print(" Mercury's Swift Touch")
    print("")

print(" [+] Starting VidSnatch Web Server for Chrome Extension")

# Check if download path is configured
video_downloads_path = config.get_video_download_path()
import os
if not os.path.exists(video_downloads_path):
    print(f" [+] Creating download directory: {video_downloads_path}")
    os.makedirs(video_downloads_path, exist_ok=True)

print(" [+] Checking required packages")

# Check for yt-dlp dependency
while True:
    try:
        import yt_dlp  # noqa: F401
        print(" [+] All required packages are installed")
        break
    except ImportError as e:
        package_name = str(e).split("'")[1] if "'" in str(e) else str(e)[17:-1]
        print(f" [!] Missing '{package_name}', installing...")
        
        pip_package = config.REQUIRED_PACKAGES.get(package_name, package_name)
        utilities.install(pip_package)

print(" [+] Loading Modules")
try:
    import modules.videoDownloader as videoDownloader
    print(" [+] All modules imported successfully")
except ImportError as e:
    print(f" [!] Failed loading modules: {e}")
    sys.exit(1)

# Import server after dependencies are ready
from web_server import start_server

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    print("\n [+] Server stopped")
    sys.exit(0)

def main():
    """Start only the web server."""
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    print("\n" + "=" * 60)
    print(" [+] VidSnatch Web Server - Chrome Extension Ready")
    print(" [+] Server URL: http://localhost:8080")
    print(" [+] Status Page: http://localhost:8080/")
    print(" [+] Press Ctrl+C to stop")
    print("=" * 60 + "\n")
    
    try:
        # Start server (this will block)
        start_server(8080)
    except KeyboardInterrupt:
        print("\n [+] Server stopped")
    except Exception as e:
        print(f" [!] Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()