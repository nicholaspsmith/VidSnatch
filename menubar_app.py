#!/usr/bin/env python3
"""VidSnatch Menu Bar Application"""
import threading
import time
import subprocess
import os
import sys
import signal
import platform
from pathlib import Path

try:
    import pystray
    from PIL import Image, ImageDraw
    import requests
    import setproctitle
except ImportError:
    print("Installing required packages...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pystray", "pillow", "requests", "setproctitle"])
    import pystray
    from PIL import Image, ImageDraw
    import requests
    import setproctitle

# PyObjC is usually pre-installed on macOS, but import it conditionally
try:
    from AppKit import NSApplication, NSImage
    from Foundation import NSBundle
    PYOBJC_AVAILABLE = True
except ImportError:
    PYOBJC_AVAILABLE = False

class VidSnatchMenuBar:
    def __init__(self):
        # Set process name to "vidsnatch"
        try:
            setproctitle.setproctitle("vidsnatch")
            # Also try to set the process name for Activity Monitor
            if platform.system() == "Darwin" and PYOBJC_AVAILABLE:
                try:
                    app = NSApplication.sharedApplication()
                    # Set the application name
                    bundle = NSBundle.mainBundle()
                    if bundle:
                        info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
                        if info:
                            info['CFBundleName'] = 'VidSnatch'
                            info['CFBundleDisplayName'] = 'VidSnatch'
                except:
                    pass
        except:
            pass
        
        # Kill any existing instances first
        self.kill_existing_instances()
        
        self.server_process = None
        self.server_running = False
        self.install_dir = os.path.expanduser("~/Applications/VidSnatch")
        
        # Set up dock icon if we're on macOS
        self.setup_dock_icon()
        
    def setup_dock_icon(self):
        """Set up custom dock icon on macOS"""
        try:
            import platform
            if platform.system() == "Darwin" and PYOBJC_AVAILABLE:  # macOS
                # Try to set the dock icon using PyObjC
                icon_path = os.path.join(self.install_dir, "chrome-extension", "icons", "icon128.png")
                if os.path.exists(icon_path):
                    try:
                        app = NSApplication.sharedApplication()
                        image = NSImage.alloc().initWithContentsOfFile_(icon_path)
                        if image:
                            app.setApplicationIconImage_(image)
                            print(f"Set dock icon to: {icon_path}")
                    except Exception as e:
                        print(f"Failed to set dock icon: {e}")
        except Exception as e:
            print(f"Could not set dock icon: {e}")
    
    def kill_existing_instances(self):
        """Kill any existing VidSnatch menubar app instances to prevent duplicates"""
        try:
            import psutil
        except ImportError:
            # Install psutil if not available
            subprocess.run([sys.executable, "-m", "pip", "install", "psutil"], capture_output=True)
            import psutil
        
        current_pid = os.getpid()
        killed_count = 0
        
        try:
            # Find all Python processes running menubar_app.py
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['pid'] == current_pid:
                        continue  # Skip current process
                    
                    if (proc.info['name'] and ('python' in proc.info['name'].lower() or proc.info['name'] == 'vidsnatch') and 
                        proc.info['cmdline'] and any('menubar_app.py' in arg for arg in proc.info['cmdline'])):
                        
                        print(f"Killing existing VidSnatch menubar instance (PID: {proc.info['pid']})")
                        proc.kill()
                        killed_count += 1
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    # Process may have already died or we don't have permission
                    continue
            
            if killed_count > 0:
                print(f"Killed {killed_count} existing VidSnatch menubar instance(s)")
                # Brief delay to let processes fully terminate
                time.sleep(0.5)
                
        except Exception as e:
            print(f"Error checking for existing instances: {e}")
        
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
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid  # Create new process group
                )
                
                # Wait a moment and verify server actually started
                time.sleep(2)
                if self.check_server_status():
                    self.server_running = True
                    return True
                else:
                    # Server failed to start, clean up
                    if self.server_process and self.server_process.poll() is None:
                        self.server_process.terminate()
                    self.server_process = None
                    return False
            except Exception as e:
                print(f"Error starting server: {e}")
                return False
    
    def stop_server(self):
        """Stop the VidSnatch server"""
        if self.server_process and self.server_running:
            try:
                # First try to stop via HTTP request
                try:
                    requests.post("http://localhost:8080/stop-server", timeout=2)
                    time.sleep(1)  # Give server time to shutdown gracefully
                except:
                    pass  # Server might already be shutting down
                
                # Kill the process and all its children
                import signal
                import os
                if self.server_process.poll() is None:  # Process still running
                    # Kill process group (parent and all children)
                    try:
                        os.killpg(os.getpgid(self.server_process.pid), signal.SIGTERM)
                    except:
                        # Fallback to just killing the main process
                        self.server_process.terminate()
                    
                    # Wait for process to end
                    try:
                        self.server_process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        # Force kill if still running
                        try:
                            os.killpg(os.getpgid(self.server_process.pid), signal.SIGKILL)
                        except:
                            self.server_process.kill()
                
                self.server_running = False
                self.server_process = None
                return True
            except Exception as e:
                print(f"Error stopping server: {e}")
                self.server_running = False
                self.server_process = None
                return False
        elif self.server_running:
            # Server is marked as running but no process - update state
            self.server_running = False
            self.server_process = None
        return True
    
    def check_server_status(self):
        """Check if server is responding"""
        try:
            response = requests.get("http://localhost:8080", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def toggle_server(self, icon, item):
        """Toggle server on/off"""
        # Check actual server status first
        actual_running = self.check_server_status()
        
        if actual_running or self.server_running:
            # Try to stop the server
            success = self.stop_server()
            
            # Also try to kill any orphaned web_server.py processes
            try:
                subprocess.run(["pkill", "-f", "web_server.py"], capture_output=True)
            except:
                pass
            
            # Wait a moment and verify server is actually stopped
            time.sleep(0.5)
            actual_stopped = not self.check_server_status()
            
            # Update internal state
            self.server_running = False
            
            # Update menu immediately
            self.update_menu(icon)
            
            if success and actual_stopped:
                icon.notify("VidSnatch server stopped")
            else:
                icon.notify("Failed to stop server")
        else:
            if self.start_server():
                self.server_running = True
                # Update menu immediately after starting
                self.update_menu(icon)
                icon.notify("VidSnatch server started - http://localhost:8080")
            else:
                # Update menu even if failed to start
                self.update_menu(icon)
                icon.notify("Failed to start server")
    
    def open_web_interface(self, icon, item):
        """Open the web interface in browser with smart tab handling"""
        import webbrowser
        import subprocess
        import platform
        
        web_url = "http://localhost:8080"
        
        # On macOS, try to use AppleScript to find existing tabs
        if platform.system() == "Darwin":
            try:
                # Try to find existing tab in common browsers and switch to it
                browsers_to_check = [
                    ("Arc", '''
                        tell application "Arc"
                            if it is running then
                                set tabFound to false
                                repeat with w in windows
                                    repeat with t in tabs of w
                                        if URL of t contains "localhost:8080" then
                                            set active tab of w to t
                                            activate
                                            set tabFound to true
                                            exit repeat
                                        end if
                                    end repeat
                                    if tabFound then exit repeat
                                end repeat
                                return tabFound
                            end if
                        end tell
                    '''),
                    ("Safari", '''
                        tell application "Safari"
                            if it is running then
                                set tabFound to false
                                repeat with w in windows
                                    repeat with t in tabs of w
                                        if URL of t contains "localhost:8080" then
                                            set current tab of w to t
                                            activate
                                            set tabFound to true
                                            exit repeat
                                        end if
                                    end repeat
                                    if tabFound then exit repeat
                                end repeat
                                return tabFound
                            end if
                        end tell
                    '''),
                    ("Google Chrome", '''
                        tell application "Google Chrome"
                            if it is running then
                                set tabFound to false
                                repeat with w in windows
                                    repeat with t in tabs of w
                                        if URL of t contains "localhost:8080" then
                                            set active tab index of w to index of t
                                            activate
                                            set tabFound to true
                                            exit repeat
                                        end if
                                    end repeat
                                    if tabFound then exit repeat
                                end repeat
                                return tabFound
                            end if
                        end tell
                    ''')
                ]
                
                # Try each browser to find existing tab
                for browser_name, applescript in browsers_to_check:
                    try:
                        result = subprocess.run(
                            ["osascript", "-e", applescript],
                            capture_output=True, text=True, timeout=3
                        )
                        if result.returncode == 0 and "true" in result.stdout:
                            print(f"Switched to existing tab in {browser_name}")
                            return
                    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                        continue
                
                # If no existing tab found, open in default browser
                webbrowser.open(web_url)
                
            except Exception as e:
                print(f"Error with smart tab handling: {e}")
                # Fallback to default browser
                webbrowser.open(web_url)
        else:
            # Non-macOS systems use default browser
            webbrowser.open(web_url)
    
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
        
        # Force icon to update immediately
        try:
            icon.update_menu()
        except AttributeError:
            # update_menu method might not exist in all versions of pystray
            pass
    
    def periodic_status_check(self, icon):
        """Periodically check server status and update menu"""
        while True:
            time.sleep(5)  # Check every 5 seconds
            try:
                actual_running = self.check_server_status()
                if actual_running != self.server_running:
                    self.server_running = actual_running
                    self.update_menu(icon)
            except:
                pass
    
    def run(self):
        """Run the menu bar application"""
        # Check if server is already running, if not, start it
        if not self.check_server_status():
            self.start_server()
        else:
            self.server_running = True
        
        icon = pystray.Icon(
            "VidSnatch",
            self.create_icon(),
            "VidSnatch Video Downloader"
        )
        
        self.update_menu(icon)
        
        # Start periodic status check in background
        import threading
        status_thread = threading.Thread(target=self.periodic_status_check, args=(icon,))
        status_thread.daemon = True
        status_thread.start()
        
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