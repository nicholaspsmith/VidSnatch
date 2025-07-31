"""Start Quikvid-DL with web server for Chrome extension support."""

import sys
import threading
import time
import signal
from web_server import start_server

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    print("\n [+] Shutting down...")
    sys.exit(0)

def main():
    """Main function to start both server and CLI application."""
    # Display the VidSnatch logo
    try:
        import modules.logo as logo
        logo.print_startup_logo()
    except ImportError:
        print(" VidSnatch - Fast Video Downloader")
        print(" Mercury's Swift Touch")
        print("")
    
    print(" [+] Starting VidSnatch with Chrome Extension Support")
    print(" [+] " + "=" * 50)
    
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Start web server in background thread
        server_thread = threading.Thread(target=start_server, args=(8080,))
        server_thread.daemon = True
        server_thread.start()
        
        # Give server time to start
        time.sleep(2)
        
        print(" [+] Web server started - Chrome extension can now connect")
        print(" [+] You can also use the CLI interface below")
        print(" [+] " + "=" * 50)
        
        # Import and start the main CLI application
        import main as quikvid_main
        quikvid_main.main()
        
    except KeyboardInterrupt:
        print("\n [+] Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f" [!] Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()