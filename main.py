"""Quikvid-DL - Video downloader using yt-dlp with automatic dependency management."""

import os
import sys
import traceback

import modules.utilities as utilities
import modules.config as config
import modules.settings as settings
import modules.folderSelector as folderSelector

utilities.clear()

# Check if this is first run or no download path is set
if settings.is_first_run() or not settings.get_download_path():
    selected_folder = folderSelector.prompt_for_download_folder()
    if selected_folder:
        settings.set_download_path(selected_folder)
        utilities.clear()

print(" [+] Checking required folders")

video_downloads_path = config.get_video_download_path()

if not os.path.exists(video_downloads_path):
    inp = input(" [!] Missing folders detected, do you wish to create the required folders? (Y/n) ")
    if "y" not in inp.lower() and inp != "":
        sys.exit(1)

    os.makedirs(video_downloads_path, exist_ok=True)
    print(" [+] Created required folders")
else:
    print(" [+] Found all required folders")

print("\n [+] Checking required packages")

while True:
    try:
        import yt_dlp  # noqa: F401
        print(" [+] All required packages are installed")
        break
    except ImportError as e:
        package_name = str(e).split("'")[1] if "'" in str(e) else str(e)[17:-1]
        inp = input(f" [!] Missing '{package_name}', do you wish to install {package_name}? (Y/n) ")

        if "y" not in inp.lower() and inp != "":
            sys.exit(1)

        pip_package = config.REQUIRED_PACKAGES.get(package_name, package_name)
        utilities.install(pip_package)

print("\n [+] Loading Modules")
try:
    import modules.videoDownloader as videoDownloader
    print(" [+] All modules imported successfully")
except ImportError as e:
    if config.DEBUG:
        exc_info = sys.exc_info()
        traceback.print_exception(*exc_info)
        del exc_info

    input(" [!] Failed loading modules, make sure all files are present. Press enter to exit.")
    sys.exit(1)

def main():
    """Main application loop."""
    try:
        while True:
            utilities.clear()
            videoDownloader.main()
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)

if __name__ == "__main__":
    main()

