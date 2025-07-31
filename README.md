<p align="center">
  <h1 align="center">🎬 VidSnatch</h1>
  <p align="center">
    <strong>2 Ways to Download Videos from 1000+ Sites!</strong>
  </p>
  <p align="center">
    YouTube • TikTok • Instagram • Facebook • Twitter • Twitch • And Many More!
  </p>
</p>

<div align="center">

| 🖱️ **Chrome Extension** | 💻 **Command Line** |
|-------------------------|---------------------|
| One-click downloads | Copy/paste URLs |
| Real-time progress bars | Terminal interface |
| Multiple simultaneous downloads | Single downloads |
| Visual interface | Developer-friendly |

</div>

---

## 🚀 Super Simple Setup

**One-Command Setup:** VidSnatch automatically handles virtual environments!

```bash
# 1. Download VidSnatch
git clone https://github.com/nicholaspsmith/VidSnatch.git
cd VidSnatch

# 2. Choose your style - that's it! (No manual venv setup needed)
```

### 🖱️ Option 1: Chrome Extension (Recommended)

**Auto-setup + Start Server:**
```bash
./start           # macOS/Linux
start.bat         # Windows

# OR use the universal method:
python setup.py server_only.py
```

**Install Chrome Extension:**
1. Open Chrome → `chrome://extensions/`
2. Enable **"Developer mode"** (top-right toggle)
3. Click **"Load unpacked"** 
4. Select the `chrome-extension` folder
5. Start downloading! 🎉

### 💻 Option 2: Command Line Interface

**Auto-setup + Start CLI:**
```bash
./cli             # macOS/Linux  
cli.bat           # Windows

# OR use the universal method:
python setup.py main.py
```

### 🔄 Option 3: Both CLI + Extension Server

**Auto-setup + Start Both:**
```bash
./start           # macOS/Linux
start.bat         # Windows

# OR use the universal method:
python setup.py start_with_server.py
```

## 🛠️ How It Works

VidSnatch uses a **setup.py** script that automatically:
- ✅ Detects if you're in a virtual environment  
- ✅ Creates one if missing (`venv/`)
- ✅ Installs dependencies from `requirements.txt`
- ✅ Starts the requested component

**Available Scripts:**
```bash
# Quick scripts (cross-platform)
./start     # CLI + Server
./server    # Server only
./cli       # CLI only

# Universal method (any OS)
python setup.py <script_name>
```

---

## 📋 Prerequisites
- **Python 3.7+** - Download from [python.org](https://www.python.org/downloads/)
- **Chrome Browser** (for extension option)

## Supported Sites

Quikvid-DL supports downloading from 1000+ sites through yt-dlp. Here are the top 20 most popular platforms:

1. **YouTube** - The world's largest video platform
2. **TikTok** - Short-form video content
3. **Instagram** - Photos and videos from posts, stories, and reels
4. **Facebook** - Social media videos and posts
5. **Twitter/X** - Social media videos and GIFs
6. **Twitch** - Live streaming and gaming content
7. **Vimeo** - High-quality video hosting
8. **Dailymotion** - Video sharing platform
9. **SoundCloud** - Audio and music content
10. **Spotify** - Music streaming platform
11. **Bilibili** - Popular video platform in Asia
12. **Reddit** - Video content from Reddit posts
13. **9GAG** - Entertainment and meme videos
14. **BBC iPlayer** - BBC's streaming service
15. **Bandcamp** - Independent music platform
16. **Pornhub** - Adult content platform
17. **Mastodon** - Decentralized social media
18. **Pinterest** - Image and video sharing
19. **XHamster** - Adult content platform
20. **XVIDEOS** - Adult content platform

*Note: Not all sites are guaranteed to work as websites constantly change. The complete list of supported extractors can be found in the [yt-dlp documentation](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).*

## 🖱️ Chrome Extension Deep Dive

### ✨ Why Choose the Chrome Extension?

- **🎯 Zero Learning Curve** - If you can click a button, you can download videos
- **⚡ Instant Downloads** - No copying URLs or switching windows
- **📊 Beautiful Progress** - Watch your downloads with real-time progress bars
- **🔄 Multitasking Master** - Download multiple videos simultaneously
- **💾 Smart Resume** - Close the popup, downloads continue in background
- **📁 Folder Control** - Click to change download location anytime

### 🎬 How to Use the Extension

1. **Navigate** to any video site (YouTube, TikTok, etc.)
2. **Click** the VidSnatch extension icon in your Chrome toolbar
3. **Hit** the "📹 Download Video" button
4. **Watch** the progress bar fill up in real-time
5. **Enjoy** your downloaded video!

### 📡 Technical Overview

- **Local Server** - Python server runs on `http://localhost:8080`
- **Real-Time Communication** - Extension polls server for progress updates
- **Background Processing** - Downloads continue even if you close the popup
- **Cross-Platform** - Works on Windows, macOS, and Linux

## 💻 Command Line Deep Dive

### ✨ Why Choose CLI?

- **🔧 Developer Friendly** - Perfect for automation and scripting
- **🎯 Direct Control** - Full access to all yt-dlp features
- **💾 Lightweight** - No browser required
- **🔄 Batch Processing** - Easy to integrate into workflows

### 🛠️ Available Commands

```bash
# CLI only (no Chrome extension support)
python main.py

# Start server only (for Chrome extension)  
python server_only.py

# Start both server + CLI interface
python start_with_server.py
```

### ⚙️ CLI Features

- **📁 Folder Selection** - First run opens native folder picker
- **❓ Help System** - Type `help` for supported sites list
- **⚙️ Settings** - Type `folder` to change download location
- **🚪 Easy Exit** - Type `exit` to quit gracefully

### 🐛 Troubleshooting

**Extension shows "Server not running":**
- Make sure you started the server: `python server_only.py`
- Check if port 8080 is free: `lsof -i :8080`

**Downloads not working:**
- Verify the site is supported (see list above)
- Check server console for error messages
- Try refreshing the page and clicking extension again

**Extension not loading:**
- Make sure Developer mode is enabled in `chrome://extensions/`
- Check for any error messages in the extension details
- Try reloading the extension

### 🎉 Why Use the Chrome Extension?

| Feature | CLI Only | Chrome Extension |
|---------|----------|------------------|
| Ease of Use | ❌ Copy/paste URLs | ✅ One-click downloads |
| Multiple Downloads | ❌ One at a time | ✅ Unlimited simultaneous |
| Progress Tracking | ❌ Terminal only | ✅ Visual progress bars |
| Background Downloads | ❌ Blocks terminal | ✅ Runs in background |
| Site Integration | ❌ Manual URL copying | ✅ Auto-detects videos |
| User Experience | ❌ Command line | ✅ Beautiful popup interface |

## Credit
Created from a fork of [PH-DL](https://github.com/logicguy1/PH-DL)
Original author: Drillenissen#4268 - [logicguy.mailandcontact@gmail.com](mailto:logicguy.mailandcontact@gmail.com)
