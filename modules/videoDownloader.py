LICENSE = """
Copyright © 2021 N² - alphakingaustin@gmail.com
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files
(the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge,
publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF 
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR 
ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH 
THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

__version__ = "1.1"
__author__  = "N²"

import modules.utilities as utilities
from contextlib import contextmanager
import subprocess
import sys, os
import youtube_dl
import time
import os
import shutil

def main():
    utilities.clear()
    url = input(" [?] Video URL (or 'exit' to quit): ")
    
    if url.lower() == "exit":
        exit()

    print(" [+] Downloading stand by\n")

    torrent_path = os.path.expanduser("~/Documents/Torrent")
    video_downloads_path = os.path.join(torrent_path, "pron")
    
    ydl = youtube_dl.YoutubeDL({'outtmpl': f'{video_downloads_path}/%(uploader)s - %(title)s - %(id)s.%(ext)s'}) # If anyone knows how to mute the output of this send help :,)

    with ydl:
        result = ydl.extract_info(
            url,
            download = True
        )


#https://www.pornhub.com/view_video.php?viewkey=ph5e80ec51bc6b5
