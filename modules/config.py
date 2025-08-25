"""Configuration constants for Quikvid-DL."""

import os
import modules.settings as settings

__version__ = "2.0"
__author__ = "N²"

# Application constants
APP_NAME = "Quikvid-DL"
APP_VERSION = "2.0"
APP_AUTHOR = "N²"

# Path constants
DEFAULT_BASE_PATH = os.path.expanduser("~/Documents/Torrent")
DEFAULT_VIDEO_SUBDIR = "videos"
LOGS_DIR = ".logs"
URL_TRACKER_FILE = os.path.join(LOGS_DIR, "url_tracker.json")
FILE_METADATA_FILE = os.path.join(LOGS_DIR, "file_metadata.json")
SERVER_LOG_FILE = os.path.join(LOGS_DIR, "server.log")

# Package requirements
REQUIRED_PACKAGES = {
    "yt_dlp": "yt-dlp",
}

# Download templates
DEFAULT_OUTPUT_TEMPLATE = "%(title)s.%(ext)s"

# UI constants
class UIConstants:
    MAIN_WINDOW_WIDTH = 700
    MAIN_WINDOW_HEIGHT = 800
    DIALOG_WIDTH = 400
    DIALOG_HEIGHT = 200
    PROGRESS_BAR_LENGTH = 480
    MENU_ICON_SIZE = 22

# Network constants
DEFAULT_SERVER_PORT = 8080
DEFAULT_SERVER_HOST = "localhost"
REQUEST_TIMEOUT = 30

# File extension patterns
VIDEO_EXTENSIONS = (
    '.mp4', '.mkv', '.webm', '.avi', '.mov', '.m4v',
    '.flv', '.wmv', '.3gp', '.mpg', '.mpeg', '.ts',
    '.m2ts', '.vob', '.ogv', '.rm', '.rmvb', '.asf',
    '.divx', '.xvid', '.f4v'
)

PARTIAL_EXTENSIONS = (
    '.part', '.ytdl', '.temp', '.download', '.crdownload'
)

# Site configurations for video downloads
SITE_CONFIGS = {
    'youtube.com': {
        'retries': 5,
        'player_client': ['android'],
        'user_agent': ('Mozilla/5.0 (Linux; Android 11; SM-G973F) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/90.0.4430.210 Mobile Safari/537.36')
    },
    'pornhub.com': {
        'retries': 10,
        'sleep_interval': 3,
        'user_agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/91.0.4472.124 Safari/537.36')
    },
    'xhamster.com': {
        'retries': 8,
        'sleep_interval': 2,
        'user_agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/91.0.4472.124 Safari/537.36')
    },
    'eporner.com': {
        'retries': 6,
        'output_template': 'Eporner_Video.%(ext)s',
        'user_agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/91.0.4472.124 Safari/537.36')
    }
}

# Debug settings
DEBUG = False

def get_video_download_path():
    """Get the path for video downloads (user preference or default)."""
    user_path = settings.get_download_path()
    if user_path and os.path.exists(user_path):
        return user_path
    else:
        return os.path.join(DEFAULT_BASE_PATH, DEFAULT_VIDEO_SUBDIR)


def get_site_config(url):
    """Get site-specific configuration for a URL."""
    from urllib.parse import urlparse
    
    try:
        domain = urlparse(url).netloc.lower()
        # Remove www. prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]
        
        return SITE_CONFIGS.get(domain, {})
    except Exception:
        return {}