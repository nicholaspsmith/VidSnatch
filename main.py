LICNECE = """
Copyright © 2021 N² - logicguy.mailandcontact@gmail.com
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

__version__ = "Cloased Beta 1.1"
__author__  = "N²"

import time

print(LICNECE)

time.sleep(1)

import os # Standerd python modules
import sys
import traceback
import modules.utilities as utilities

os.system('cls' if os.name == 'nt' else 'clear') # Clear the LICNECE information to make the screen look nicer

DEBUG = True
# Check if the required folders are setup
print(" [+] Checking requred folders")

torrent_path = os.path.expanduser("~/Documents/Torrent")
video_downloads_path = os.path.join(torrent_path, "pron")

if not os.path.exists(video_downloads_path):
    inp = input(" [!] Missing folders detected, do you wish to create the requred folders? (Y/n) ")
    if "y" not in inp.lower() and inp != "":
        exit()

    os.makedirs(torrent_path, exist_ok=True)
    if not os.path.exists(video_downloads_path):
        os.mkdir(video_downloads_path)

else:
    print(" [+] Found all requred folders")

# Check every module / package and ask the user to install them if they arent installed

packages = { # Some packages go under a diffrent pip name than what you use to import
    "youtube_dl" : "youtube_dl",
    "requests" : "requests",
    "pync" : "pync",
    "bs4" : "bs4"
}

print("\n [+] Checking requred packages")

while True: # Will run untill all the packages has been installed and imported successfully
    try:
        # import youtube_dl # Python packages that needs to be installed
        from bs4 import BeautifulSoup
        import pync
        import requests
        import youtube_dl # type: ignore


        print(" [+] All requred packages are installed")
        break
    except ImportError as e:
        package = str(e)[17:-1]
        inp = input(f" [!] Missing '{package}', do you wish to install {package}? (Y/n) ")

        if "y" not in inp.lower() and inp != "":
            exit()

        utilities.install(packages[package])

print("\n [+] Loading Modules") # Load the external files of the project
try:
    import modules.videoDownloader as videoDownloader

    print(" [+] All modules imported successfully")
except ImportError as e:
    if DEBUG:
        exc_info = sys.exc_info()
        traceback.print_exception(*exc_info)
        del exc_info

    input(" [!] Falied loading modules, make sure you cloned all the files from the github, press enter to exit")
    exit()

while True:
    utilities.clear() # Clear the screen

    videoDownloader.main() # Call the main function of the video downloader module

    input(f"\n [!] Done! Press enter to continue")
