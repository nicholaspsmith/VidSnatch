#!/usr/bin/env python3
"""VidSnatch Menu Bar Application"""
import threading
import time
import subprocess
import os
import sys
import signal
from pathlib import Path

try:
    import pystray
    from PIL import Image, ImageDraw
    import requests
except ImportError:
    print("Installing required packages...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pystray", "pillow", "requests"])
    import pystray
    from PIL import Image, ImageDraw
    import requests

class VidSnatchMenuBar:
    def __init__(self):
        self.server_process = None
        self.server_running = False
        self.install_dir = os.path.expanduser("~/Applications/VidSnatch")
        
    def create_icon(self):
        """Create an icon for the menu bar using the extension icon"""
        try:
            # Try to load the extension icon
            icon_path = os.path.join(self.install_dir, "chrome-extension", "icons", "icon128.png")
            if os.path.exists(icon_path):
                image = Image.open(icon_path)
                # Resize to menu bar size (typically 16-22px on macOS)
                image = image.resize((22, 22), Image.Resampling.LANCZOS)
                return image
        except Exception as e:
            print(f"Could not load extension icon: {e}")
        
        # Fallback: Create a download arrow icon similar to the extension
        width = height = 22
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Draw dark background circle
        draw.ellipse([1, 1, width-1, height-1], fill=(26, 26, 26, 255))
        
        # Draw download arrow (simplified version of the extension icon)
        center_x, center_y = width//2, height//2
        
        # Arrow shaft
        shaft_width = 3
        shaft_height = 8
        draw.rectangle([
            center_x - shaft_width//2, center_y - shaft_height//2,
            center_x + shaft_width//2, center_y + shaft_height//2 - 2
        ], fill=(135, 206, 235, 255))  # Sky blue like the extension
        
        # Arrow head
        arrow_points = [
            (center_x - 4, center_y + 2),
            (center_x, center_y + 6),
            (center_x + 4, center_y + 2)
        ]
        draw.polygon(arrow_points, fill=(135, 206, 235, 255))
        
        return image
    
    def start_server(self):
        """Start the VidSnatch server"""
        if not self.server_running:
            try:
                os.chdir(self.install_dir)
                # Use the virtual environment python
                python_path = os.path.join(self.install_dir, "venv", "bin", "python3")
                server_script = os.path.join(self.install_dir, "web_server.py")
                
                self.server_process = subprocess.Popen(
                    [python_path, server_script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self.server_running = True
                return True
            except Exception as e:
                print(f"Error starting server: {e}")
                return False
    
    def stop_server(self):
        """Stop the VidSnatch server"""
        if self.server_process and self.server_running:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
                self.server_running = False
                return True
            except:
                try:
                    self.server_process.kill()
                    self.server_running = False
                    return True
                except:
                    return False
    
    def check_server_status(self):
        """Check if server is responding"""
        try:
            response = requests.get("http://localhost:8080", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def toggle_server(self, icon, item):
        """Toggle server on/off"""
        if self.server_running:
            if self.stop_server():
                icon.notify("VidSnatch server stopped")
            else:
                icon.notify("Failed to stop server")
        else:
            if self.start_server():
                icon.notify("VidSnatch server started - http://localhost:8080")
            else:
                icon.notify("Failed to start server")
        self.update_menu(icon)
    
    def open_web_interface(self, icon, item):
        """Open the web interface in browser"""
        import webbrowser
        webbrowser.open("http://localhost:8080")
    
    def quit_app(self, icon, item):
        """Quit the application"""
        self.stop_server()
        icon.stop()
    
    def update_menu(self, icon):
        """Update the menu based on server status"""
        status_text = "Stop Server" if self.server_running else "Start Server"
        
        menu = pystray.Menu(
            pystray.MenuItem(status_text, self.toggle_server),
            pystray.MenuItem("Open Web Interface", self.open_web_interface),
            pystray.MenuItem("Quit VidSnatch", self.quit_app)
        )
        icon.menu = menu
    
    def run(self):
        """Run the menu bar application"""
        # Auto-start server
        self.start_server()
        
        icon = pystray.Icon(
            "VidSnatch",
            self.create_icon(),
            "VidSnatch Video Downloader"
        )
        
        self.update_menu(icon)
        
        # Handle clean shutdown
        def signal_handler(signum, frame):
            self.stop_server()
            icon.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        icon.run()

if __name__ == "__main__":
    app = VidSnatchMenuBar()
    app.run()