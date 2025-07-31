"""Configuration constants for the video downloader application."""

import os

__version__ = "1.1"
__author__ = "N²"

APP_NAME = "Video Downloader"
APP_VERSION = "1.1"
APP_AUTHOR = "N²"

DEFAULT_BASE_PATH = os.path.expanduser("~/Documents/Torrent")
DEFAULT_VIDEO_SUBDIR = "pron"

REQUIRED_PACKAGES = {
    "yt_dlp": "yt-dlp",
}

DEFAULT_OUTPUT_TEMPLATE = "%(uploader)s - %(title)s - %(id)s.%(ext)s"

DEBUG = False

def get_video_download_path():
    """Get the default path for video downloads."""
    return os.path.join(DEFAULT_BASE_PATH, DEFAULT_VIDEO_SUBDIR)