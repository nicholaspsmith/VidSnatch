# Quikvid-DL Chrome Extension

A Chrome extension that allows you to download videos from any supported site with one click.

## Installation

1. **Enable Developer Mode in Chrome:**
   - Open Chrome and go to `chrome://extensions/`
   - Toggle "Developer mode" in the top right corner

2. **Load the Extension:**
   - Click "Load unpacked"
   - Select the `chrome-extension` folder from your Quikvid-DL directory

3. **Start the Local Server:**
   ```bash
   cd /path/to/Quikvid-DL
   ./start
   ```

## Usage

1. **Start the Server:** Run `python web_server.py` in your Quikvid-DL directory
2. **Browse to Video:** Navigate to any supported video site (YouTube, TikTok, Instagram, etc.)
3. **Download:** Click the Quikvid-DL extension icon and press "Download Video"
4. **Complete:** Video will download to your configured folder

## Features

- ✅ **Auto-Detection:** Automatically detects video pages
- ✅ **One-Click Download:** Simple button click to start downloads  
- ✅ **Visual Feedback:** Badge shows when videos are detected
- ✅ **Real-time Status:** Shows download progress and status
- ✅ **Cross-Platform:** Works on Windows, Mac, and Linux

## Supported Sites

The extension works with all sites supported by yt-dlp including:
- YouTube, TikTok, Instagram, Facebook, Twitter/X
- Twitch, Vimeo, Dailymotion, SoundCloud
- Reddit, 9GAG, Bilibili, Pinterest
- And 1000+ more sites!

## Technical Details

- **Architecture:** Chrome Extension → Local HTTP Server → yt-dlp
- **Server:** Runs on `http://localhost:8080`
- **API:** Simple REST API for download requests
- **Security:** Only accepts requests from localhost

## Troubleshooting

**Extension not working?**
- Make sure the local server is running (`python web_server.py`)
- Check if the site is supported by yt-dlp
- Try refreshing the page and clicking the extension again

**Server not starting?**
- Make sure port 8080 is not in use by another application
- Check that all Python dependencies are installed

**Downloads not working?**
- Verify your download folder is set correctly in Quikvid-DL
- Check console output in the terminal running the server
- Some sites may have restrictions or require specific handling

## Icons

To add custom icons, replace the placeholder files in the `icons/` directory:
- `icon16.png` - 16x16 pixels
- `icon32.png` - 32x32 pixels  
- `icon48.png` - 48x48 pixels
- `icon128.png` - 128x128 pixels