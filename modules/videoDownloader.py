"""Video downloader module using youtube-dl."""

import os
import sys
import subprocess

import yt_dlp

import modules.utilities as utilities
import modules.config as config

def download_video(url, download_path):
    """Download a video from the given URL."""
    ydl_opts = {
        'outtmpl': os.path.join(download_path, config.DEFAULT_OUTPUT_TEMPLATE)
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
        return True
    except yt_dlp.DownloadError as e:
        handle_download_error(e)
        return False
    except Exception as e:
        print(f" [!] Error: An unexpected error occurred - {type(e).__name__}")
        return False

def handle_download_error(error):
    """Handle download errors with specific messages."""
    error_msg = str(error).lower()
    
    if "unsupported url" in error_msg or "no video formats found" in error_msg:
        print(" [!] Error: This URL is not supported or no video was found at this link")
    elif "video unavailable" in error_msg or "private video" in error_msg:
        print(" [!] Error: This video is unavailable, private, or has been removed")
    elif "age" in error_msg and "restricted" in error_msg:
        print(" [!] Error: This video is age-restricted and cannot be downloaded")
    else:
        error_summary = str(error).split(':')[0] if ':' in str(error) else str(error)
        print(f" [!] Error: Unable to download video - {error_summary}")

def open_finder(path):
    """Open Finder window to the specified directory (macOS only)."""
    try:
        subprocess.run(["open", path], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

def main():
    """Main function for the video downloader module."""
    utilities.clear()
    
    download_path = config.get_video_download_path()
    
    while True:
        url = input(" [?] Video URL from supported sites like Pornhub, xHamster, etc. (or 'exit' to quit): ")
        
        if url.lower() == "exit":
            sys.exit(0)
        
        if not url.strip():
            print(" [!] Please enter a valid URL or 'exit' to quit\n")
            continue

        print(" [+] Downloading, please stand by...\n")
        
        if download_video(url, download_path):
            print(" [+] Download completed successfully!")
            open_finder(download_path)
            break
        else:
            print(" [!] Please try a different URL or 'exit' to quit\n")