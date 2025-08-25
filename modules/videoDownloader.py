"""Video downloader module using yt-dlp."""

import os
import sys
import subprocess

import yt_dlp

import modules.utilities as utilities
import modules.config as config
import modules.settings as settings
import modules.folderSelector as folderSelector
from modules.config import get_site_config

def download_video(url, download_path):
    """Download a video from the given URL."""
    
    def clean_title_hook(d):
        """Hook to clean video title during extraction."""
        if d.get('status') == 'finished':
            # Clean title for display
            if 'title' in d.get('info_dict', {}):
                cleaned_title = utilities.clean_video_title(d['info_dict']['title'])
                print(f" [+] Downloaded: {cleaned_title}")
    
    # Get site-specific configuration
    site_config = get_site_config(url)
    
    # Base configuration
    ydl_opts = {
        'outtmpl': os.path.join(
            download_path, 
            site_config.get('output_template', config.DEFAULT_OUTPUT_TEMPLATE)
        ),
        'socket_timeout': 180,
        'retries': site_config.get('retries', 5),
        'fragment_retries': site_config.get('retries', 5),
        'file_access_retries': 3,
        'progress_hooks': [clean_title_hook],
        'http_headers': {
            'User-Agent': site_config.get(
                'user_agent',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/131.0.0.0 Safari/537.36'
            ),
            'Accept': ('text/html,application/xhtml+xml,application/xml;'
                      'q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        },
        'external_downloader_args': {
            'default': ['--retry-connrefused', '--retry', '5', '--timeout', '300']
        }
    }
    
    # Apply site-specific sleep interval if configured
    if 'sleep_interval' in site_config:
        ydl_opts['sleep_interval_requests'] = site_config['sleep_interval']
    
    # Apply YouTube-specific extractor args if configured
    if 'player_client' in site_config:
        ydl_opts['extractor_args'] = {
            'youtube': {
                'player_client': site_config['player_client']
            }
        }
    
    try:
        # Custom preprocessor to clean titles before file naming
        class TitleCleanerPP(yt_dlp.postprocessor.PostProcessor):
            def run(self, info):
                # Clean the title for file naming
                if 'title' in info:
                    original_title = info['title']
                    cleaned_title = utilities.clean_video_title(original_title)
                    info['title'] = cleaned_title
                    if original_title != cleaned_title:
                        print(f" [+] Cleaned title: '{original_title}' → '{cleaned_title}'")
                return [], info
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Add the title cleaner postprocessor
            ydl.add_post_processor(TitleCleanerPP(ydl), when='pre_process')
            ydl.extract_info(url, download=True)
        return True
    except (yt_dlp.DownloadError, AttributeError) as e:
        # Try manual extraction for Eporner if the built-in extractor fails
        if 'eporner.com' in url and ('Unable to extract hash' in str(e) or isinstance(e, AttributeError)):
            print(f" [+] Attempting manual Eporner extraction...")
            try:
                import requests
                import re
                
                # Get page content
                response = requests.get(url, 
                    headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'},
                    timeout=30)
                
                # Extract video URL patterns
                video_patterns = [
                    r'src[\s]*=[\s]*["\']([^"\']*\.mp4[^"\']*)["\']',
                    r'video_url[\s]*=[\s]*["\']([^"\']*\.mp4[^"\']*)["\']',
                    r'"file"\s*:\s*"([^"]+\.mp4[^"]*)"',
                    r'source\s+src=["\']([^"\']*\.mp4[^"\']*)["\']',
                ]
                
                video_url = None
                for pattern in video_patterns:
                    matches = re.findall(pattern, response.text, re.IGNORECASE)
                    if matches:
                        video_url = matches[0]
                        break
                
                if video_url:
                    print(f" [+] Found direct video URL, downloading...")
                    
                    # Create simple options for direct download
                    direct_opts = {
                        'outtmpl': os.path.join(download_path, 'Eporner_Video.%(ext)s'),
                        'http_headers': {
                            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                            'Referer': 'https://www.eporner.com/',
                        }
                    }
                    
                    with yt_dlp.YoutubeDL(direct_opts) as direct_ydl:
                        direct_ydl.download([video_url])
                    
                    print(f" [+] Manual Eporner extraction successful!")
                    return True
                else:
                    print(f" [!] Could not find video URL in page content")
                    
            except Exception as manual_e:
                print(f" [!] Manual extraction failed: {manual_e}")
        
        # Handle DownloadError specifically
        if isinstance(e, yt_dlp.DownloadError):
            handle_download_error(e)
        else:
            print(f" [!] Error: Extraction failed - {type(e).__name__}: {e}")
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