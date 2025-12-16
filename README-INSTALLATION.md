# VidSnatch Installation Guide

## Prerequisites

VidSnatch requires Python 3.10+ installed via Homebrew. The system Python that comes with macOS is not compatible due to SDK version mismatches with required dependencies.

### Fresh macOS Installation Steps

**1. Install Homebrew**

Open Terminal and run:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the post-installation instructions to add Homebrew to your PATH. Typically:
```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

**2. Install Python 3.12 and tkinter**

```bash
brew install python@3.12
brew install python-tk@3.12
```

## Quick Installation

**For most users:**
1. Double-click **VidSnatch Manager.command** to launch the graphical installer
2. Follow the on-screen instructions
3. VidSnatch will appear in your menu bar when installation is complete

## Alternative Installation Methods

**Command Line Users:**
- Run `./install.sh` in Terminal for command-line installation
- Run `./uninstall.sh` to remove VidSnatch completely

**Manual Installation:**
- See the full documentation in the `macos-installer/` directory

## What Gets Installed

- Python server with all dependencies (in a virtual environment)
- VidSnatch menu bar application
- Chrome extension files
- Desktop shortcut for extension setup

## After Installation

1. Look for the VidSnatch icon in your menu bar (top-right corner)
2. Click the menu bar icon to start/stop the server
3. Install the Chrome extension using the desktop shortcut
4. Start downloading videos!

## Troubleshooting

### "macOS XX required" error
This occurs when using the system Python instead of Homebrew Python. Install Python via Homebrew:
```bash
brew install python@3.12
brew install python-tk@3.12
```

### Syntax errors during installation
Ensure you're using Python 3.10+. Check your version:
```bash
/opt/homebrew/bin/python3.12 --version
```

### tkinter not found
Install tkinter for your Python version:
```bash
brew install python-tk@3.12
```

### General issues
- Check the logs in `~/Applications/VidSnatch/.logs/`
- Run the uninstaller if you need to start fresh
- Ensure Homebrew Python is being used (not system Python)

---

**Support:** https://github.com/nicholaspsmith/VidSnatch
