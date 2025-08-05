"""Video downloader module using yt-dlp."""

import os
import sys
import subprocess

import yt_dlp

import modules.utilities as utilities
import modules.config as config
import modules.settings as settings
import modules.folderSelector as folderSelector

def download_video(url, download_path):
    """Download a video from the given URL."""
    ydl_opts = {
        'outtmpl': os.path.join(download_path, config.DEFAULT_OUTPUT_TEMPLATE),
        'socket_timeout': 180,  # 3 minutes socket timeout for slow CDNs
        'retries': 5,  # Retry 5 times on failure  
        'fragment_retries': 5,  # Retry fragments 5 times
        'file_access_retries': 3,  # Retry file access
        # Add headers to improve CDN compatibility
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        },
        # CDN-specific optimizations  
        'external_downloader_args': {
            'default': ['--retry-connrefused', '--retry', '5', '--timeout', '300']
        }
    }
    
    # Apply site-specific settings for better compatibility
    if 'youtube.com' in url or 'youtu.be' in url:
        ydl_opts['extractor_args'] = {
            'youtube': {
                'player_client': ['android'],  # Use Android client for better compatibility
            }
        }
    elif 'pornhub.com' in url:
        # Add Pornhub-specific configuration
        ydl_opts.update({
            'retries': 10,
            'fragment_retries': 10,
            'sleep_interval_requests': 3,
            'http_headers': {
                **ydl_opts['http_headers'],
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.pornhub.com/',
            }
        })
    
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

def show_help():
    """Display help information and supported sites."""
    print(" [?] Quikvid-DL Help")
    print(" [?] Enter a video URL from any supported site to download it to your computer.")
    
    current_path = settings.get_download_path()
    if current_path:
        print(f" [+] Current download folder: {current_path}")
    
    print("\n [+] Commands:")
    print(" [+] 'help' - Show this help message")
    print(" [+] 'folder' - Change download folder")
    print(" [+] 'exit' - Exit the program")
    
    print("\n [+] Top 20 Supported Sites:")
    sites = [
        "YouTube", "TikTok", "Instagram", "Facebook", "Twitter/X",
        "Twitch", "Vimeo", "Dailymotion", "SoundCloud", "Spotify",
        "Bilibili", "Reddit", "9GAG", "BBC iPlayer", "Bandcamp",
        "Pornhub", "Mastodon", "Pinterest", "XHamster", "XVIDEOS"
    ]
    
    for i, site in enumerate(sites, 1):
        print(f" [{i:2d}] {site}")
    
    print("\n [+] Note: Over 1000+ sites are supported! See README for complete list.")
    input("\n [?] Press Enter to continue...")

def main():
    """Main function for the video downloader module."""
    utilities.clear()
    
    download_path = config.get_video_download_path()
    
    while True:
        url = input(" [?] Video URL from supported sites (or 'help'/'folder'/'exit'): ")
        
        if url.lower() == "exit":
            sys.exit(0)
        
        if url.lower() == "help":
            show_help()
            utilities.clear()
            continue
        
        if url.lower() == "folder":
            print(" [?] Changing download folder...")
            new_folder = folderSelector.select_download_folder()
            if new_folder:
                settings.set_download_path(new_folder)
                download_path = config.get_video_download_path()
                print(f" [+] Download folder changed to: {new_folder}")
            else:
                print(" [!] No folder selected. Keeping current folder.")
            input(" [?] Press Enter to continue...")
            utilities.clear()
            continue
        
        if not url.strip():
            print(" [!] Please enter a valid URL, 'help', 'folder', or 'exit' to quit\n")
            continue

        print(" [+] Downloading, please stand by...\n")
        
        if download_video(url, download_path):
            print(" [+] Download completed successfully!")
            open_finder(download_path)
            break
        else:
            print(" [!] Please try a different URL, 'help', 'folder', or 'exit' to quit\n")