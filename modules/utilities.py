"""Utility functions for the video downloader application."""

import os
import subprocess
import sys

def clear():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def install(package):
    """Install a Python package using pip."""
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def clean_video_title(title):
    """Clean video title by removing unwanted prefixes and suffixes.
    
    Args:
        title (str): The original video title
        
    Returns:
        str: The cleaned video title
    """
    if not title:
        return title
        
    # Remove "NA - " prefix (case-insensitive)
    if title.lower().startswith('na - '):
        title = title[5:]  # Remove the first 5 characters "NA - "
    
    # Remove other common unwanted prefixes
    prefixes_to_remove = [
        'undefined - ',
        'null - ',
        '[object Object] - ',
        'untitled - ',
    ]
    
    title_lower = title.lower()
    for prefix in prefixes_to_remove:
        if title_lower.startswith(prefix.lower()):
            title = title[len(prefix):]
            break
    
    # Remove uploader/channel name prefixes (common pattern: "ChannelName - ActualTitle")
    # Look for patterns like "Word - " or "Word1Word2 - " at the beginning
    import re
    
    # Pattern to match uploader prefixes: one or more words followed by " - "
    # Only remove if there's substantial content after the " - "
    uploader_pattern = r'^([A-Za-z0-9_]+(?:\s+[A-Za-z0-9_]+)*)\s*-\s*(.{10,})$'
    match = re.match(uploader_pattern, title)
    
    if match:
        uploader_name = match.group(1)
        actual_title = match.group(2).strip()
        
        # Only remove uploader prefix if:
        # 1. The actual title is substantial (10+ chars)
        # 2. The uploader name looks like a channel name (not part of the title)
        if (len(actual_title) >= 10 and 
            len(uploader_name) <= 20 and  # Reasonable uploader name length
            not any(word in uploader_name.lower() for word in ['and', 'the', 'with', 'for', 'on', 'in'])):  # Avoid removing descriptive parts
            title = actual_title
    
    # Clean up any leading/trailing whitespace
    title = title.strip()
    
    # Remove any trailing " - " or leading "- "
    title = re.sub(r'^-\s*', '', title)
    title = re.sub(r'\s*-$', '', title)
    
    # If title is empty after cleaning, return a default
    if not title:
        return 'Unknown Video'
        
    return title
