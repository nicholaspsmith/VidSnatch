#!/usr/bin/env python3
"""
Create a simple executable launcher for VidSnatch Manager
This avoids Gatekeeper issues with shell scripts in app bundles
"""

import os
import subprocess
import sys

# Create a simple Python executable that launches the GUI
launcher_content = '''#!/usr/bin/env python3
import os
import subprocess
import sys

# Change to VidSnatch directory
vidsnatch_dir = "/Users/nicholassmith/Code/Quikvid-DL"
os.chdir(vidsnatch_dir)

# Launch GUI installer
try:
    subprocess.Popen([sys.executable, "gui_installer.py"], cwd=vidsnatch_dir)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
'''

# Write the launcher
launcher_path = "/Users/nicholassmith/Desktop/VidSnatch Manager.app/Contents/MacOS/VidSnatch Manager"
with open(launcher_path, 'w') as f:
    f.write(launcher_content)

# Make executable
os.chmod(launcher_path, 0o755)

print("✅ Created simple Python launcher")