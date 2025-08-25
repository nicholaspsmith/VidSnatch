"""Utility functions for installer operations."""

import os
import subprocess
import sys
import time
from modules.config import REQUIRED_PACKAGES


def check_and_install_dependencies():
    """Check for required packages and install if missing."""
    missing_packages = []
    
    for package_import, package_install in REQUIRED_PACKAGES.items():
        try:
            __import__(package_import)
            print(f" [+] {package_import} is already installed")
        except ImportError:
            missing_packages.append((package_import, package_install))
    
    if not missing_packages:
        print(" [+] All required packages are installed")
        return True
    
    print(f" [!] Missing packages: {[pkg[1] for pkg in missing_packages]}")
    print(" [+] Installing missing packages...")
    
    for package_import, package_install in missing_packages:
        try:
            print(f" [+] Installing {package_install}...")
            result = subprocess.run([
                sys.executable, '-m', 'pip', 'install', package_install
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                print(f" [+] Successfully installed {package_install}")
            else:
                print(f" [!] Failed to install {package_install}")
                print(f"     Error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f" [!] Timeout installing {package_install}")
            return False
        except Exception as e:
            print(f" [!] Error installing {package_install}: {e}")
            return False
    
    # Verify installation
    for package_import, _ in missing_packages:
        try:
            __import__(package_import)
        except ImportError:
            print(f" [!] Failed to verify installation of {package_import}")
            return False
    
    print(" [+] All packages installed successfully")
    return True


def kill_processes_by_pattern(patterns):
    """Kill processes matching the given patterns."""
    killed_processes = []
    
    for pattern in patterns:
        try:
            # Use pgrep to find processes
            result = subprocess.run(
                ['pgrep', '-f', pattern],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid:
                        try:
                            subprocess.run(
                                ['kill', '-TERM', pid],
                                timeout=5
                            )
                            killed_processes.append((pattern, pid))
                        except subprocess.TimeoutExpired:
                            # Force kill if TERM doesn't work
                            try:
                                subprocess.run(
                                    ['kill', '-KILL', pid],
                                    timeout=5
                                )
                                killed_processes.append((pattern, pid))
                            except Exception:
                                pass
                        except Exception:
                            pass
        except Exception:
            pass
    
    if killed_processes:
        print(f" [+] Killed {len(killed_processes)} processes")
        for pattern, pid in killed_processes:
            print(f"     - {pattern} (PID: {pid})")
    else:
        print(" [+] No matching processes found")
    
    return killed_processes


def create_virtual_environment(venv_path):
    """Create a Python virtual environment."""
    try:
        print(f" [+] Creating virtual environment at {venv_path}...")
        result = subprocess.run([
            sys.executable, '-m', 'venv', venv_path
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            print(" [+] Virtual environment created successfully")
            return True
        else:
            print(f" [!] Failed to create virtual environment: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(" [!] Timeout creating virtual environment")
        return False
    except Exception as e:
        print(f" [!] Error creating virtual environment: {e}")
        return False


def install_requirements_in_venv(venv_path, requirements_file):
    """Install requirements in a virtual environment."""
    if not os.path.exists(requirements_file):
        print(f" [!] Requirements file not found: {requirements_file}")
        return False
    
    # Get the pip path in the virtual environment
    if sys.platform == 'win32':
        pip_path = os.path.join(venv_path, 'Scripts', 'pip')
        python_path = os.path.join(venv_path, 'Scripts', 'python')
    else:
        pip_path = os.path.join(venv_path, 'bin', 'pip')
        python_path = os.path.join(venv_path, 'bin', 'python')
    
    try:
        # Upgrade pip first
        print(" [+] Upgrading pip...")
        subprocess.run([
            python_path, '-m', 'pip', 'install', '--upgrade', 'pip'
        ], capture_output=True, timeout=120)
        
        # Install requirements
        print(f" [+] Installing requirements from {requirements_file}...")
        result = subprocess.run([
            pip_path, 'install', '-r', requirements_file
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print(" [+] Requirements installed successfully")
            return True
        else:
            print(f" [!] Failed to install requirements: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(" [!] Timeout installing requirements")
        return False
    except Exception as e:
        print(f" [!] Error installing requirements: {e}")
        return False


def create_macos_app_bundle(app_path, app_name, executable_content,
                           bundle_id=None, version="1.0"):
    """Create a macOS app bundle."""
    try:
        # Create directory structure
        contents_dir = os.path.join(app_path, "Contents")
        macos_dir = os.path.join(contents_dir, "MacOS")
        resources_dir = os.path.join(contents_dir, "Resources")
        
        os.makedirs(macos_dir, exist_ok=True)
        os.makedirs(resources_dir, exist_ok=True)
        
        # Create executable
        executable_path = os.path.join(macos_dir, app_name)
        with open(executable_path, 'w') as f:
            f.write(executable_content)
        os.chmod(executable_path, 0o755)
        
        # Create Info.plist
        bundle_id = bundle_id or f"com.vidsnatch.{app_name.lower()}"
        info_plist = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" 
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>{app_name}</string>
    <key>CFBundleIdentifier</key>
    <string>{bundle_id}</string>
    <key>CFBundleName</key>
    <string>{app_name}</string>
    <key>CFBundleVersion</key>
    <string>{version}</string>
    <key>CFBundleShortVersionString</key>
    <string>{version}</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.9</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>'''
        
        info_plist_path = os.path.join(contents_dir, "Info.plist")
        with open(info_plist_path, 'w') as f:
            f.write(info_plist)
        
        print(f" [+] Created app bundle: {app_path}")
        return True
        
    except Exception as e:
        print(f" [!] Error creating app bundle: {e}")
        return False


def wait_for_process_completion(process_names, timeout=30):
    """Wait for specific processes to complete or timeout."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        still_running = []
        
        for process_name in process_names:
            try:
                result = subprocess.run(
                    ['pgrep', '-f', process_name],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    still_running.append(process_name)
            except Exception:
                pass
        
        if not still_running:
            print(" [+] All processes completed")
            return True
        
        print(f" [+] Waiting for processes: {still_running}")
        time.sleep(2)
    
    print(f" [!] Timeout waiting for processes: {still_running}")
    return False