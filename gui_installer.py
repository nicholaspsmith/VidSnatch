#!/usr/bin/env python3
"""
VidSnatch GUI Installer for macOS
A user-friendly graphical installer with Install, Uninstall, and Reinstall options
"""

# Check if tkinter is available, fall back to command line if not
try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False
    print("❌ tkinter not available. Falling back to command line installer.")
    print("To use the GUI installer, install tkinter with: brew install python-tk")

import subprocess
import threading
import os
import sys
import shutil
import signal
import time
from pathlib import Path
from modules.config import UIConstants
from modules.installer_utils import (
    check_and_install_dependencies,
    kill_processes_by_pattern,
    create_virtual_environment,
    install_requirements_in_venv,
    create_macos_app_bundle
)

class VidSnatchInstaller:
    def __init__(self, root):
        self.root = root
        self.root.title("VidSnatch Manager")
        geometry = f"{UIConstants.MAIN_WINDOW_WIDTH}x{UIConstants.MAIN_WINDOW_HEIGHT}"
        self.root.geometry(geometry)
        self.root.resizable(False, False)
        
        # Center the window on screen
        self.center_window()
        
        # Set up the UI
        self.setup_ui()
        
        # Installation paths
        self.install_dir = os.path.expanduser("~/Applications/VidSnatch")
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Track installation status
        self.is_installed = self.check_installation()
        self.update_status()
        
        # Show current status in output window
        if self.is_installed:
            self.log_output("✅ VidSnatch is currently INSTALLED")
        else:
            self.log_output("❌ VidSnatch is currently NOT INSTALLED")
        
    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
        # Ensure window is brought to front and focused
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))
        self.root.focus_force()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="🎬 VidSnatch Manager", 
                               font=("Helvetica", 24, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Description - create centered frame with left-aligned text
        desc_frame = ttk.Frame(main_frame)
        desc_frame.grid(row=1, column=0, columnspan=2, pady=(0, 20))
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        desc_frame.columnconfigure(0, weight=1)
        
        desc_text = ("VidSnatch is a powerful video downloader that works with YouTube and many other sites.\n\n"
                    "It includes a menu bar app and Chrome extension for easy video downloading.\n"
                    "Use the buttons below to install, uninstall, or reinstall VidSnatch.")
        desc_label = ttk.Label(desc_frame, text=desc_text, justify=tk.LEFT, wraplength=480)
        desc_label.grid(row=0, column=0, sticky='w')
        
        # Status frame - create centered frame to match description width
        status_outer_frame = ttk.Frame(main_frame)
        status_outer_frame.grid(row=2, column=0, columnspan=2, pady=(0, 20))
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        status_outer_frame.columnconfigure(0, weight=1)
        
        status_frame = ttk.LabelFrame(status_outer_frame, text="Installation Status", padding="10", width=480)
        status_frame.grid(row=0, column=0)
        status_frame.grid_propagate(False)  # Prevent frame from shrinking to fit content
        
        # Configure status frame to center content
        status_frame.columnconfigure(0, weight=1)
        
        self.status_label = ttk.Label(status_frame, text="Checking installation...", 
                                     font=("TkDefaultFont", 9), wraplength=460)
        self.status_label.grid(row=0, column=0)
        
        # Buttons frame - create centered frame to match other container widths
        buttons_outer_frame = ttk.Frame(main_frame)
        buttons_outer_frame.grid(row=3, column=0, columnspan=2, pady=(0, 20))
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        buttons_outer_frame.columnconfigure(0, weight=1)
        
        buttons_frame = ttk.Frame(buttons_outer_frame)
        buttons_frame.grid(row=0, column=0)
        
        # Configure button frame to center buttons
        buttons_frame.columnconfigure(0, weight=1)
        buttons_frame.columnconfigure(1, weight=1)
        buttons_frame.columnconfigure(2, weight=1)
        
        # Create custom style for larger text
        style = ttk.Style()
        style.configure('Large.TButton', font=('TkDefaultFont', 10))
        
        # Install button
        self.install_button = ttk.Button(buttons_frame, text="📦 Install", 
                                        command=self.install_vidsnatch, width=12,
                                        style='Large.TButton')
        self.install_button.grid(row=0, column=0, padx=5, sticky='ew')
        
        # Uninstall button
        self.uninstall_button = ttk.Button(buttons_frame, text="🗑️ Uninstall", 
                                          command=self.uninstall_vidsnatch, width=12,
                                          style='Large.TButton')
        self.uninstall_button.grid(row=0, column=1, padx=5, sticky='ew')
        
        # Reinstall button
        self.reinstall_button = ttk.Button(buttons_frame, text="🔄 Reinstall", 
                                          command=self.reinstall_vidsnatch, width=12,
                                          style='Large.TButton')
        self.reinstall_button.grid(row=0, column=2, padx=5, sticky='ew')
        
        # Progress bar - create centered frame to match other container widths
        progress_outer_frame = ttk.Frame(main_frame)
        progress_outer_frame.grid(row=4, column=0, columnspan=2, pady=(0, 10))
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        progress_outer_frame.columnconfigure(0, weight=1)
        
        self.progress = ttk.Progressbar(progress_outer_frame, mode='indeterminate', length=480)
        self.progress.grid(row=0, column=0)
        
        # Output text area - create centered frame to match other container widths
        output_outer_frame = ttk.Frame(main_frame)
        output_outer_frame.grid(row=5, column=0, columnspan=2, pady=(0, 10))
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        output_outer_frame.columnconfigure(0, weight=1)
        
        output_frame = ttk.LabelFrame(output_outer_frame, text="Installation Output", padding="5")
        output_frame.grid(row=0, column=0)
        
        self.output_text = scrolledtext.ScrolledText(output_frame, height=15, width=65)
        self.output_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Chrome Extension section - fixed width to match other containers
        extension_outer_frame = ttk.Frame(main_frame)
        extension_outer_frame.grid(row=6, column=0, columnspan=2, pady=(10, 10))
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        extension_outer_frame.columnconfigure(0, weight=1)
        
        extension_frame = ttk.LabelFrame(extension_outer_frame, text="Chrome Extension Setup", padding="10")
        extension_frame.grid(row=0, column=0)
        
        # Configure extension frame to center content
        extension_frame.columnconfigure(0, weight=1)
        
        # Create a centered frame for the extension description
        extension_desc_frame = ttk.Frame(extension_frame)
        extension_desc_frame.grid(row=0, column=0, pady=(0, 10))
        extension_frame.columnconfigure(0, weight=1)
        
        extension_info = ttk.Label(extension_desc_frame, 
                                  text="After installing VidSnatch, set up the Chrome extension to download videos directly from web pages.",
                                  wraplength=460, justify=tk.LEFT)
        extension_info.pack()
        
        extension_button = ttk.Button(extension_frame, text="🌐 Setup Chrome Extension", 
                                     command=self.setup_chrome_extension, style='Large.TButton')
        extension_button.grid(row=1, column=0, pady=(0, 5))
        
        # Close button - center between Chrome extension and bottom with proper spacing
        close_button = ttk.Button(main_frame, text="❌ Close", command=self.root.quit, width=15)
        close_button.grid(row=7, column=0, columnspan=2, pady=(20, 30))
        
        # Configure grid weights - distribute space better
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(5, weight=1)  # Output area gets most space
        main_frame.rowconfigure(7, weight=0)  # Close button row - no expansion
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        
    def check_installation(self):
        """Check if VidSnatch is currently installed"""
        app_path = os.path.expanduser("~/Applications/VidSnatch.app")
        server_path = self.install_dir
        
        app_exists = os.path.exists(app_path)
        server_exists = os.path.exists(server_path)
        
        # Check for key files to ensure it's a complete installation
        key_files_exist = True
        if server_exists:
            required_files = ['web_server.py', 'modules', 'venv']
            for file in required_files:
                if not os.path.exists(os.path.join(server_path, file)):
                    key_files_exist = False
                    break
        
        # Also check if the app bundle has the executable
        if app_exists:
            executable_path = os.path.join(app_path, "Contents", "MacOS", "VidSnatch")
            if not os.path.exists(executable_path):
                app_exists = False
        
        return app_exists and server_exists and key_files_exist
        
    def update_status(self):
        """Update the installation status display"""
        if self.is_installed:
            self.status_label.config(text="✅ VidSnatch is installed", foreground="green")
            self.install_button.config(state="disabled")
            self.uninstall_button.config(state="normal")
            self.reinstall_button.config(state="normal")
        else:
            self.status_label.config(text="❌ VidSnatch is not installed", foreground="red")
            self.install_button.config(state="normal")
            self.uninstall_button.config(state="disabled")
            self.reinstall_button.config(state="disabled")
            
    def log_output(self, message):
        """Add message to output text area"""
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
        self.root.update()
        
    def show_custom_confirmation(self, title, message):
        """Show a custom confirmation dialog that doesn't un-minimize other apps"""
        # Create a new dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("400x200")
        dialog.resizable(False, False)
        dialog.transient(self.root)  # Make it stay on top of parent
        dialog.grab_set()  # Make it modal
        
        # Center the dialog on the parent window
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 200
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 100
        dialog.geometry(f"400x200+{x}+{y}")
        
        # Store the result
        result = tk.BooleanVar()
        result.set(False)
        
        # Create the dialog content
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.grid(row=0, column=0, sticky='nsew')
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        
        # Message label
        message_label = ttk.Label(main_frame, text=message, wraplength=350, justify='center')
        message_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=1, column=0, columnspan=2)
        
        def on_yes():
            result.set(True)
            dialog.destroy()
            
        def on_no():
            result.set(False)
            dialog.destroy()
        
        yes_button = ttk.Button(buttons_frame, text="Yes", command=on_yes, width=10)
        yes_button.grid(row=0, column=0, padx=(0, 10))
        
        no_button = ttk.Button(buttons_frame, text="No", command=on_no, width=10)
        no_button.grid(row=0, column=1, padx=(10, 0))
        
        # Set focus to No button (safer default)
        no_button.focus_set()
        
        # Handle window close as "No"
        dialog.protocol("WM_DELETE_WINDOW", on_no)
        
        # Wait for the dialog to close
        dialog.wait_window()
        
        return result.get()
        
    def show_custom_error(self, title, message):
        """Show a custom error dialog that doesn't un-minimize other apps"""
        self._show_custom_info_dialog(title, message, "Error", "#d63447")
        
    def show_custom_info(self, title, message):
        """Show a custom info dialog that doesn't un-minimize other apps"""
        self._show_custom_info_dialog(title, message, "Information", "#3d4db7")
        
    def _show_custom_info_dialog(self, title, message, dialog_type, color):
        """Helper method for custom info/error dialogs"""
        # Create a new dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("450x250")
        dialog.resizable(False, False)
        dialog.transient(self.root)  # Make it stay on top of parent
        dialog.grab_set()  # Make it modal
        
        # Center the dialog on the parent window
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 225
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 125
        dialog.geometry(f"450x250+{x}+{y}")
        
        # Create the dialog content
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.grid(row=0, column=0, sticky='nsew')
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        
        # Icon and title frame
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, sticky='ew', pady=(0, 15))
        
        icon = "❌" if dialog_type == "Error" else "ℹ️"
        icon_label = ttk.Label(header_frame, text=icon, font=("Arial", 20))
        icon_label.grid(row=0, column=0, padx=(0, 10))
        
        title_label = ttk.Label(header_frame, text=dialog_type, font=("Arial", 12, "bold"))
        title_label.grid(row=0, column=1, sticky='w')
        
        # Message label
        message_label = ttk.Label(main_frame, text=message, wraplength=400, justify='left')
        message_label.grid(row=1, column=0, pady=(0, 20), sticky='ew')
        
        # OK button
        def on_ok():
            dialog.destroy()
        
        ok_button = ttk.Button(main_frame, text="OK", command=on_ok, width=10)
        ok_button.grid(row=2, column=0)
        ok_button.focus_set()
        
        # Handle window close
        dialog.protocol("WM_DELETE_WINDOW", on_ok)
        
        # Wait for the dialog to close
        dialog.wait_window()
        
    def disable_buttons(self):
        """Disable all buttons during operations"""
        self.install_button.config(state="disabled")
        self.uninstall_button.config(state="disabled")
        self.reinstall_button.config(state="disabled")
        self.progress.start()
        
    def enable_buttons(self):
        """Re-enable buttons after operations"""
        self.progress.stop()
        self.update_status()
        
    def run_command(self, command, description):
        """Run a shell command and log output"""
        self.log_output(f"🔨 {description}...")
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=self.current_dir)
            
            if result.stdout:
                self.log_output(result.stdout)
            if result.stderr:
                self.log_output(f"Error: {result.stderr}")
                
            if result.returncode == 0:
                self.log_output(f"✅ {description} completed successfully")
                return True
            else:
                self.log_output(f"❌ {description} failed with return code {result.returncode}")
                return False
                
        except Exception as e:
            self.log_output(f"❌ Error running {description}: {str(e)}")
            return False
            
    def install_vidsnatch(self):
        """Install VidSnatch"""
        def install_thread():
            self.disable_buttons()
            self.log_output("🎬 Starting VidSnatch installation...")
            
            try:
                success = self.run_install_steps()
                
                if success:
                    self.log_output("\n🎉 Installation completed successfully!")
                    self.log_output("📋 Next Steps:")
                    self.log_output("1. Look for VidSnatch icon in your menu bar")
                    self.log_output("2. Click it to start/stop the server")
                    self.log_output("3. Use the Chrome Extension Setup button below")
                    
                    # Refresh installation status
                    self.is_installed = self.check_installation()
                    self.update_status()
                    
                    self.log_output("\n✅ VidSnatch is now ready to use! Check your menu bar for the VidSnatch icon.")
                else:
                    self.log_output("\n❌ Installation failed. Please check the output above.")
                    self.log_output("❌ You may need to install missing dependencies or fix permission issues.")
                    
            except Exception as e:
                self.log_output(f"\n❌ Installation error: {str(e)}")
                self.log_output("❌ Please check the error details above and try again.")
                
            finally:
                self.enable_buttons()
                
        threading.Thread(target=install_thread, daemon=True).start()
        
    def uninstall_vidsnatch(self):
        """Uninstall VidSnatch"""
        if not self.show_custom_confirmation("Confirm Uninstall", 
                                  "Are you sure you want to uninstall VidSnatch?\n\n"
                                  "This will remove all VidSnatch files and stop all processes."):
            return
            
        def uninstall_thread():
            self.disable_buttons()
            self.log_output("🗑️ Starting VidSnatch uninstallation...")
            
            try:
                success = self.run_uninstall_steps()
                
                if success:
                    self.log_output("\n🎉 Uninstallation completed successfully!")
                    
                    # Refresh installation status
                    self.is_installed = self.check_installation()
                    self.update_status()
                    
                    self.log_output("\n✅ VidSnatch has been completely removed from your system.")
                else:
                    self.log_output("\n❌ Uninstallation failed. Please check the output above.")
                    self.log_output("❌ Some files may not have been removed. You can try again or manually delete the installation directory.")
                    
            except Exception as e:
                self.log_output(f"\n❌ Uninstallation error: {str(e)}")
                self.log_output("❌ Please check the error details above and try again.")
                
            finally:
                self.enable_buttons()
                
        threading.Thread(target=uninstall_thread, daemon=True).start()
        
    def reinstall_vidsnatch(self):
        """Reinstall VidSnatch (uninstall then install)"""
        if not self.show_custom_confirmation("Confirm Reinstall", 
                                  "Are you sure you want to reinstall VidSnatch?\n\n"
                                  "This will first uninstall the current version, then install a fresh copy."):
            return
            
        def reinstall_thread():
            self.disable_buttons()
            self.log_output("🔄 Starting VidSnatch reinstallation...")
            
            try:
                # First uninstall
                self.log_output("\n--- UNINSTALL PHASE ---")
                uninstall_success = self.run_uninstall_steps()
                
                if not uninstall_success:
                    self.log_output("❌ Uninstall phase failed, aborting reinstall.")
                    self.log_output("❌ Please check the output above for details and try again.")
                    return
                    
                # Wait a moment between operations
                time.sleep(2)
                
                # Then install
                self.log_output("\n--- INSTALL PHASE ---")
                install_success = self.run_install_steps()
                
                if install_success:
                    self.log_output("\n🎉 Reinstallation completed successfully!")
                    self.is_installed = True
                    # Update status instead of showing popup to avoid un-minimizing apps
                    self.update_status()
                    self.log_output("\n✅ VidSnatch has been successfully reinstalled and is ready to use!")
                else:
                    self.log_output("\n❌ Install phase failed.")
                    self.log_output("❌ Please check the output above for details and try again.")
                    
            except Exception as e:
                self.log_output(f"\n❌ Reinstallation error: {str(e)}")
                self.log_output("❌ Please check the error details above and try again.")
                
            finally:
                self.enable_buttons()
                
        threading.Thread(target=reinstall_thread, daemon=True).start()
        
    def setup_chrome_extension(self):
        """Setup Chrome extension for VidSnatch"""
        def extension_thread():
            try:
                self.log_output("🌐 Setting up Chrome extension...")
                
                # Check if VidSnatch is installed
                if not self.check_installation():
                    self.show_custom_error("Error", "Please install VidSnatch first before setting up the Chrome extension.")
                    return
                
                extension_dir = os.path.join(self.install_dir, "chrome-extension")
                
                if not os.path.exists(extension_dir):
                    self.show_custom_error("Error", f"Chrome extension files not found at {extension_dir}")
                    return
                
                self.log_output("📋 Instructions for Chrome Extension Setup:")
                self.log_output("1. Opening Chrome Extensions page...")
                self.log_output("2. Enable 'Developer mode' (toggle in top-right)")
                self.log_output("3. Click 'Load unpacked'")
                self.log_output(f"4. Navigate to: {extension_dir}")
                self.log_output("5. Select the chrome-extension folder")
                self.log_output("")
                
                # Open Chrome extensions page
                import subprocess
                try:
                    subprocess.run(["open", "-a", "Google Chrome", "chrome://extensions/"], check=True)
                    self.log_output("✅ Chrome Extensions page opened")
                    
                    # Also open the extension directory in Finder
                    subprocess.run(["open", extension_dir], check=True)
                    self.log_output(f"✅ Extension directory opened: {extension_dir}")
                    
                    self.show_custom_info("Chrome Extension Setup", 
                                      "Chrome Extensions page and extension folder have been opened.\n\n"
                                      "Follow these steps:\n"
                                      "1. Enable 'Developer mode' in Chrome\n"
                                      "2. Click 'Load unpacked'\n"
                                      "3. Select the chrome-extension folder that just opened\n"
                                      "4. The VidSnatch extension will be installed!")
                                      
                except subprocess.CalledProcessError as e:
                    self.log_output(f"❌ Error opening Chrome: {e}")
                    self.show_custom_error("Error", f"Could not open Chrome. Please manually navigate to chrome://extensions/ and load the extension from:\n{extension_dir}")
                    
            except Exception as e:
                self.log_output(f"❌ Extension setup error: {e}")
                self.show_custom_error("Error", f"Extension setup error: {e}")
                
        threading.Thread(target=extension_thread, daemon=True).start()
        
    def run_install_steps(self):
        """Run the actual installation steps"""
        # Create installation directory
        self.log_output("📁 Creating installation directory...")
        os.makedirs(self.install_dir, exist_ok=True)
        
        # Copy Python server files from current directory
        self.log_output("🐍 Installing Python server...")
        server_files = ['web_server.py', 'url_tracker.py', 'main.py', 'server_only.py', 'start_with_server.py', 'menubar_app.py', 'file_metadata.py']
        for file in server_files:
            src_path = os.path.join(self.current_dir, file)
            if os.path.exists(src_path):
                dst_path = os.path.join(self.install_dir, file)
                shutil.copy2(src_path, dst_path)
                self.log_output(f"  ✅ Copied {file}")
        
        # Copy modules directory
        modules_src = os.path.join(self.current_dir, "modules")
        modules_dst = os.path.join(self.install_dir, "modules")
        if os.path.exists(modules_src):
            if os.path.exists(modules_dst):
                shutil.rmtree(modules_dst)
            shutil.copytree(modules_src, modules_dst)
            self.log_output("  ✅ Copied modules directory")
        
        # Set up Python virtual environment
        self.log_output("⚙️ Setting up Python environment...")
        venv_path = os.path.join(self.install_dir, "venv")
        
        if not self.run_command(f"cd '{self.install_dir}' && python3 -m venv venv", "Creating virtual environment"):
            return False
            
        # Install dependencies
        pip_path = os.path.join(venv_path, "bin", "pip")
        requirements_path = os.path.join(self.current_dir, "requirements.txt")
        
        if not self.run_command(f"'{pip_path}' install --upgrade pip", "Upgrading pip"):
            return False
            
        if os.path.exists(requirements_path):
            if not self.run_command(f"'{pip_path}' install -r '{requirements_path}'", "Installing dependencies"):
                return False
        
        # Install additional dependencies needed for menu bar app
        menu_bar_deps = ["requests", "pillow", "pystray"]
        for dep in menu_bar_deps:
            if not self.run_command(f"'{pip_path}' install {dep}", f"Installing {dep} for menu bar app"):
                return False
        
        # Create menu bar app launcher (script-based approach)
        self.log_output("📱 Creating menu bar app launcher...")
        app_dir = os.path.expanduser("~/Applications/VidSnatch.app")
        contents_dir = os.path.join(app_dir, "Contents")
        macos_dir = os.path.join(contents_dir, "MacOS")
        
        # Create app bundle structure
        os.makedirs(macos_dir, exist_ok=True)
        
        # Create Info.plist
        info_plist_content = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>VidSnatch</string>
    <key>CFBundleIdentifier</key>
    <string>com.vidsnatch.menubar</string>
    <key>CFBundleName</key>
    <string>VidSnatch</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>'''
        
        with open(os.path.join(contents_dir, "Info.plist"), 'w') as f:
            f.write(info_plist_content)
        
        # Create launcher script
        launcher_script = os.path.join(macos_dir, "VidSnatch")
        launcher_content = f'''#!/bin/bash
cd "{self.install_dir}"
source venv/bin/activate
python3 menubar_app.py
'''
        
        with open(launcher_script, 'w') as f:
            f.write(launcher_content)
        
        # Make executable
        os.chmod(launcher_script, 0o755)
        self.log_output("✅ Menu bar app launcher created")
        
        # Install Chrome extension files
        self.log_output("🌐 Installing Chrome extension...")
        ext_src = os.path.join(self.current_dir, "chrome-extension")
        ext_dst = os.path.join(self.install_dir, "chrome-extension")
        
        if os.path.exists(ext_src):
            if os.path.exists(ext_dst):
                shutil.rmtree(ext_dst)
            shutil.copytree(ext_src, ext_dst)
        
        # Desktop shortcut creation removed - user should use main installer shortcut
        
        # Create launch scripts
        self.create_launch_scripts()
        
        # Try to launch the menu bar app
        self.log_output("🚀 Starting VidSnatch menu bar app...")
        
        try:
            # Method 1: Try to open the app bundle directly
            app_path = os.path.expanduser("~/Applications/VidSnatch.app")
            result = subprocess.run(["open", app_path], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                self.log_output("✅ Menu bar app launched via 'open' command")
            else:
                raise subprocess.CalledProcessError(result.returncode, "open")
                
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            # Method 2: Fallback to launch script
            try:
                launch_script = os.path.join(self.install_dir, "launch-menubar.py")
                python_path = os.path.join(venv_path, "bin", "python3")
                
                if os.path.exists(launch_script):
                    subprocess.Popen([python_path, launch_script], 
                                   cwd=self.install_dir,
                                   stdout=subprocess.DEVNULL, 
                                   stderr=subprocess.DEVNULL)
                    self.log_output("✅ Menu bar app launched via launch script")
                else:
                    self.log_output("⚠️ Launch script not found")
                    
            except Exception as e:
                self.log_output(f"⚠️ Could not auto-launch menu bar app: {e}")
                self.log_output("📝 You can manually launch it from Applications folder")
        
        time.sleep(2)
            
        return True
        
    def run_uninstall_steps(self):
        """Run the actual uninstallation steps"""
        # Stop all VidSnatch processes (URL tracker automatically persists incomplete downloads)
        self.log_output("🛑 Stopping all VidSnatch processes...")
        
        commands = [
            "killall -9 VidSnatch 2>/dev/null || true",
            "pkill -9 -f 'menubar_app.py' 2>/dev/null || true",
            "pkill -9 -f 'web_server.py' 2>/dev/null || true",
            "pkill -9 -f 'VidSnatch' 2>/dev/null || true",
            "pkill -9 -f 'pystray' 2>/dev/null || true",
            "pkill -9 -f 'launch-menubar.py' 2>/dev/null || true"
        ]
        
        for cmd in commands:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if "Stopped" in cmd or "pkill" in cmd:
                # Log successful process termination
                if result.returncode == 0:
                    self.log_output(f"✅ {cmd.split("'")[1] if "'" in cmd else 'Process'} terminated")
            
        # Kill any Python processes running from VidSnatch directory
        try:
            result = subprocess.run("ps aux | grep python | grep '/Applications/VidSnatch' | grep -v grep | awk '{print $2}'", 
                                  shell=True, capture_output=True, text=True)
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid:  # Make sure pid is not empty
                        subprocess.run(f"kill -9 {pid}", shell=True, capture_output=True)
                self.log_output("✅ Stopped VidSnatch Python processes")
        except:
            pass
            
        # Kill anything using port 8080
        try:
            result = subprocess.run("lsof -ti :8080 2>/dev/null", shell=True, capture_output=True, text=True)
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    subprocess.run(f"kill -9 {pid}", shell=True, capture_output=True)
                self.log_output("✅ Freed port 8080")
        except:
            pass
            
        # Remove installation directory
        if os.path.exists(self.install_dir):
            shutil.rmtree(self.install_dir)
            self.log_output(f"✅ Removed {self.install_dir}")
            
        # Remove app bundle
        app_path = os.path.expanduser("~/Applications/VidSnatch.app")
        if os.path.exists(app_path):
            shutil.rmtree(app_path)
            self.log_output("✅ Removed ~/Applications/VidSnatch.app")
            
        # Remove any old desktop shortcuts
        old_shortcuts = [
            os.path.expanduser("~/Desktop/Install VidSnatch Extension.command")
        ]
        for shortcut in old_shortcuts:
            if os.path.exists(shortcut):
                os.remove(shortcut)
                self.log_output(f"✅ Removed old desktop shortcut: {os.path.basename(shortcut)}")
        
        # Note: We don't restart the Dock as it un-minimizes applications
        self.log_output("✅ Menu bar items will be cleared on next login")
            
        return True
        
    def create_launch_scripts(self):
        """Create launch scripts for the application"""
        venv_python = os.path.join(self.install_dir, "venv", "bin", "python3")
        
        # Create launch script for command line
        start_script = os.path.join(self.install_dir, "start-vidsnatch.command")
        start_content = f'''#!/bin/bash
cd "{self.install_dir}"
source venv/bin/activate
python3 "{os.path.expanduser('~/Applications/VidSnatch.app/Contents/MacOS/VidSnatch')}"
'''
        
        with open(start_script, 'w') as f:
            f.write(start_content)
        os.chmod(start_script, 0o755)
        
        # Create Python launcher for menu bar
        launcher_script = os.path.join(self.install_dir, "launch-menubar.py")
        venv_python = os.path.join(self.install_dir, "venv", "bin", "python3")
        launcher_content = f'''#!/usr/bin/env python3
import subprocess
import sys
import os

# Change to the VidSnatch directory
os.chdir(os.path.expanduser("~/Applications/VidSnatch"))

# Run the menu bar app with the correct Python interpreter
try:
    # Use the virtual environment Python
    python_path = "{venv_python}"
    app_script = os.path.expanduser("~/Applications/VidSnatch.app/Contents/MacOS/VidSnatch")
    
    # Run with proper environment including virtual environment paths
    env = os.environ.copy()
    env['PYTHONPATH'] = os.path.expanduser("~/Applications/VidSnatch")
    
    # Add virtual environment to PATH so it can find dependencies
    venv_bin = os.path.expanduser("~/Applications/VidSnatch/venv/bin")
    env['PATH'] = venv_bin + ":" + env.get('PATH', '')
    
    # Set virtual environment activation
    env['VIRTUAL_ENV'] = os.path.expanduser("~/Applications/VidSnatch/venv")
    
    subprocess.run([python_path, app_script], env=env)
except Exception as e:
    print(f"Error launching menu bar app: {{e}}")
    # Install required dependencies system-wide as fallback
    try:
        print("Installing required dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--break-system-packages", "requests", "pillow", "pystray"], check=True)
        subprocess.run([sys.executable, os.path.expanduser("~/Applications/VidSnatch.app/Contents/MacOS/VidSnatch")])
    except Exception as e2:
        print(f"Fallback also failed: {{e2}}")
'''
        
        with open(launcher_script, 'w') as f:
            f.write(launcher_content)
        os.chmod(launcher_script, 0o755)
        
    def run_install_steps_cli(self):
        """CLI version of installation steps with print output"""
        print("📁 Creating installation directory...")
        os.makedirs(self.install_dir, exist_ok=True)
        
        # Copy Python server files from current directory
        print("🐍 Installing Python server...")
        server_files = ['web_server.py', 'url_tracker.py', 'main.py', 'server_only.py', 'start_with_server.py', 'menubar_app.py', 'file_metadata.py']
        for file in server_files:
            src_path = os.path.join(self.current_dir, file)
            if os.path.exists(src_path):
                dst_path = os.path.join(self.install_dir, file)
                shutil.copy2(src_path, dst_path)
                print(f"  ✅ Copied {file}")
        
        # Copy modules directory
        modules_src = os.path.join(self.current_dir, "modules")
        modules_dst = os.path.join(self.install_dir, "modules")
        if os.path.exists(modules_src):
            if os.path.exists(modules_dst):
                shutil.rmtree(modules_dst)
            shutil.copytree(modules_src, modules_dst)
            print("  ✅ Copied modules directory")
        
        # Set up Python virtual environment
        print("⚙️ Setting up Python environment...")
        venv_path = os.path.join(self.install_dir, "venv")
        
        result = subprocess.run(f"cd '{self.install_dir}' && python3 -m venv venv", 
                              shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Error creating virtual environment: {result.stderr}")
            return False
            
        # Install dependencies
        pip_path = os.path.join(venv_path, "bin", "pip")
        requirements_path = os.path.join(self.current_dir, "requirements.txt")
        
        result = subprocess.run(f"'{pip_path}' install --upgrade pip", 
                              shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Error upgrading pip: {result.stderr}")
            return False
            
        if os.path.exists(requirements_path):
            result = subprocess.run(f"'{pip_path}' install -r '{requirements_path}'", 
                                  shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ Error installing dependencies: {result.stderr}")
                return False
        
        # Install additional dependencies needed for menu bar app
        menu_bar_deps = ["requests", "pillow", "pystray"]
        for dep in menu_bar_deps:
            print(f"Installing {dep} for menu bar app...")
            result = subprocess.run(f"'{pip_path}' install {dep}", 
                                  shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ Error installing {dep}: {result.stderr}")
                return False
        
        # Create menu bar app launcher (script-based approach)
        print("📱 Creating menu bar app launcher...")
        app_dir = os.path.expanduser("~/Applications/VidSnatch.app")
        contents_dir = os.path.join(app_dir, "Contents")
        macos_dir = os.path.join(contents_dir, "MacOS")
        
        # Create app bundle structure
        os.makedirs(macos_dir, exist_ok=True)
        
        # Create Info.plist
        info_plist_content = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>VidSnatch</string>
    <key>CFBundleIdentifier</key>
    <string>com.vidsnatch.menubar</string>
    <key>CFBundleName</key>
    <string>VidSnatch</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>'''
        
        with open(os.path.join(contents_dir, "Info.plist"), 'w') as f:
            f.write(info_plist_content)
        
        # Create launcher script
        launcher_script = os.path.join(macos_dir, "VidSnatch")
        launcher_content = f'''#!/bin/bash
cd "{self.install_dir}"
source venv/bin/activate
python3 menubar_app.py
'''
        
        with open(launcher_script, 'w') as f:
            f.write(launcher_content)
        
        # Make executable
        os.chmod(launcher_script, 0o755)
        print("✅ Menu bar app launcher created")
        
        # Install Chrome extension files
        print("🌐 Installing Chrome extension...")
        ext_src = os.path.join(self.current_dir, "chrome-extension")
        ext_dst = os.path.join(self.install_dir, "chrome-extension")
        
        if os.path.exists(ext_src):
            if os.path.exists(ext_dst):
                shutil.rmtree(ext_dst)
            shutil.copytree(ext_src, ext_dst)
        
        # Desktop shortcut creation removed - user should use main installer shortcut
        
        # Create launch scripts
        self.create_launch_scripts()
        
        # Try to launch the menu bar app
        print("🚀 Starting VidSnatch menu bar app...")
        launch_script = os.path.join(self.install_dir, "launch-menubar.py")
        python_path = os.path.join(venv_path, "bin", "python3")
        
        if os.path.exists(launch_script):
            subprocess.Popen([python_path, launch_script], 
                           cwd=self.install_dir,
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            time.sleep(2)
            
        return True
        
    def run_uninstall_steps_cli(self):
        """CLI version of uninstallation steps with print output"""
        # Stop all VidSnatch processes (URL tracker automatically persists incomplete downloads)
        print("🛑 Stopping all VidSnatch processes...")
        
        commands = [
            "killall -9 VidSnatch 2>/dev/null || true",
            "pkill -9 -f 'menubar_app.py' 2>/dev/null || true",
            "pkill -9 -f 'web_server.py' 2>/dev/null || true",
            "pkill -9 -f 'VidSnatch' 2>/dev/null || true",
            "pkill -9 -f 'pystray' 2>/dev/null || true",
            "pkill -9 -f 'launch-menubar.py' 2>/dev/null || true"
        ]
        
        for cmd in commands:
            subprocess.run(cmd, shell=True, capture_output=True)
            
        # Kill any Python processes running from VidSnatch directory
        try:
            result = subprocess.run("ps aux | grep python | grep '/Applications/VidSnatch' | grep -v grep | awk '{print $2}'", 
                                  shell=True, capture_output=True, text=True)
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid:  # Make sure pid is not empty
                        subprocess.run(f"kill -9 {pid}", shell=True, capture_output=True)
                print("✅ Stopped VidSnatch Python processes")
        except:
            pass
            
        # Kill anything using port 8080
        try:
            result = subprocess.run("lsof -ti :8080 2>/dev/null", shell=True, capture_output=True, text=True)
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    subprocess.run(f"kill -9 {pid}", shell=True, capture_output=True)
                print("✅ Freed port 8080")
        except:
            pass
            
        # Remove installation directory
        if os.path.exists(self.install_dir):
            shutil.rmtree(self.install_dir)
            print(f"✅ Removed {self.install_dir}")
            
        # Remove app bundle
        app_path = os.path.expanduser("~/Applications/VidSnatch.app")
        if os.path.exists(app_path):
            shutil.rmtree(app_path)
            print("✅ Removed ~/Applications/VidSnatch.app")
            
        # Remove any old desktop shortcuts
        old_shortcuts = [
            os.path.expanduser("~/Desktop/Install VidSnatch Extension.command")
        ]
        for shortcut in old_shortcuts:
            if os.path.exists(shortcut):
                os.remove(shortcut)
                print(f"✅ Removed old desktop shortcut: {os.path.basename(shortcut)}")
        
        # Note: We don't restart the Dock as it un-minimizes applications
        print("✅ Menu bar items will be cleared on next login")
            
        return True

class CommandLineInstaller:
    """Fallback command line installer when tkinter is not available"""
    
    def __init__(self):
        self.install_dir = os.path.expanduser("~/Applications/VidSnatch")
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        
    def run(self):
        print("\n🎬 VidSnatch Manager (Command Line)")
        print("=" * 40)
        
        # Check installation status
        is_installed = self.check_installation()
        if is_installed:
            print("✅ VidSnatch is currently installed")
        else:
            print("❌ VidSnatch is not installed")
            
        print("\nOptions:")
        print("1. Install VidSnatch")
        print("2. Uninstall VidSnatch")
        print("3. Reinstall VidSnatch")
        print("4. Exit")
        
        while True:
            try:
                choice = input("\nEnter your choice (1-4): ").strip()
                
                if choice == "1":
                    if is_installed:
                        print("❌ VidSnatch is already installed. Use option 3 to reinstall.")
                    else:
                        self.install()
                        is_installed = True
                elif choice == "2":
                    if not is_installed:
                        print("❌ VidSnatch is not installed.")
                    else:
                        confirm = input("Are you sure you want to uninstall VidSnatch? (y/N): ")
                        if confirm.lower() == 'y':
                            self.uninstall()
                            is_installed = False
                elif choice == "3":
                    confirm = input("Are you sure you want to reinstall VidSnatch? (y/N): ")
                    if confirm.lower() == 'y':
                        if is_installed:
                            print("🗑️ Uninstalling current version...")
                            self.uninstall()
                        print("📦 Installing fresh version...")
                        self.install()
                        is_installed = True
                elif choice == "4":
                    print("👋 Goodbye!")
                    break
                else:
                    print("❌ Invalid choice. Please enter 1-4.")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
                
    def check_installation(self):
        app_exists = os.path.exists(os.path.expanduser("~/Applications/VidSnatch.app"))
        server_exists = os.path.exists(self.install_dir)
        return app_exists and server_exists
        
    def install(self):
        print("\n🎬 Installing VidSnatch...")
        installer = VidSnatchInstaller(None)
        installer.install_dir = self.install_dir
        installer.current_dir = self.current_dir
        
        try:
            success = installer.run_install_steps_cli()
            if success:
                print("✅ Installation completed successfully!")
            else:
                print("❌ Installation failed.")
        except Exception as e:
            print(f"❌ Installation error: {e}")
            
    def uninstall(self):
        print("\n🗑️ Uninstalling VidSnatch...")
        installer = VidSnatchInstaller(None)
        installer.install_dir = self.install_dir
        installer.current_dir = self.current_dir
        
        try:
            success = installer.run_uninstall_steps_cli()
            if success:
                print("✅ Uninstallation completed successfully!")
            else:
                print("❌ Uninstallation failed.")
        except Exception as e:
            print(f"❌ Uninstallation error: {e}")

def main():
    if not TKINTER_AVAILABLE:
        # Fall back to command line installer
        cli_installer = CommandLineInstaller()
        cli_installer.run()
        return
        
    try:
        # Set up the GUI
        root = tk.Tk()
        
        # Set the app icon if available
        try:
            # Try to use the VidSnatch icon
            icon_path = os.path.join(os.path.dirname(__file__), "chrome-extension", "icons", "icon128.png")
            if os.path.exists(icon_path):
                root.iconphoto(True, tk.PhotoImage(file=icon_path))
        except Exception as e:
            print(f"Could not set icon: {e}")
        
        app = VidSnatchInstaller(root)
        
        # Handle window close
        def on_closing():
            root.quit()
            root.destroy()
            
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # Start the GUI
        root.mainloop()
        
    except Exception as e:
        print(f"GUI Error: {e}")
        print("Falling back to command line installer...")
        cli_installer = CommandLineInstaller()
        cli_installer.run()

if __name__ == "__main__":
    main()