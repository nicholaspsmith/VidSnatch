"""Configuration constants for Quikvid-DL."""

import os
import modules.settings as settings

__version__ = "2.0"
__author__ = "N²"

APP_NAME = "Quikvid-DL"
APP_VERSION = "2.0"
APP_AUTHOR = "N²"

DEFAULT_BASE_PATH = os.path.expanduser("~/Documents/Torrent")
DEFAULT_VIDEO_SUBDIR = "videos"

REQUIRED_PACKAGES = {
    "yt_dlp": "yt-dlp",
}

DEFAULT_OUTPUT_TEMPLATE = "%(uploader)s - %(title)s - %(id)s.%(ext)s"

DEBUG = False

def get_video_download_path():
    """Get the path for video downloads (user preference or default)."""
    user_path = settings.get_download_path()
    if user_path and os.path.exists(user_path):
        return user_path
    else:
        return os.path.join(DEFAULT_BASE_PATH, DEFAULT_VIDEO_SUBDIR)