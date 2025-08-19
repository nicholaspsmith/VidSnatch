"""ASCII art logo for VidSnatch with Mercury symbolism."""

def get_ascii_logo():
    """Return ASCII art logo representing the download arrow design.
    
    45 characters wide, featuring a prominent download arrow with 
    Mercury symbol signature, reflecting the new icon design.
    """
    return """
╭─────────────────────────────────────────────╮
│   ▲ ░░▒▒▓     VidSnatch     ▓▒▒░░ ⚠         │
│  ▲▲▲ ░▒▓██                 ██▓▒░  ⚠         │
│ ▲▲▲▲▲ ▒▓███               ███▓▒             │
│▲▲▲▲▲▲▲ ▓████  Download  ████▓              │
│ ▲▲▲▲▲ ▒▓███    Videos   ███▓▒              │
│  ▲▲▲ ░▒▓██               ██▓▒░              │
│   ▲ ░░▒▒▓     ▓▓▓▓▓▓▓     ▓▒▒░░              │
│             ▓▓███████▓▓                     │
│            ▓███████████▓                    │
│           ▓█████████████▓                   │
│          ▓███████████████▓                  │
│         ▓█████████████████▓                 │
│        ▓███████████████████▓                │
│       ▓█████████████████████▓               │
│      ▓███████▼▼▼▼▼███████████▓              │
│     ▓███████▼▼▼▼▼▼▼███████████▓             │
│    ▓██████▼▼▼▼▼▼▼▼▼▼▼██████████▓            │
│   ▓█████▼▼▼▼▼▼▼▼▼▼▼▼▼█████████▓             │
│  ▓████▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼████████▓              │
│ ▓███▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼███████▓               │
│▓██▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼██████▓                │
│▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼████▓                 │
│ ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼██▓                    │
│   ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▓                       │
│     ▼▼▼▼▼▼▼▼▼▼▼▼▼▼                          │
│       ▼▼▼▼▼▼▼▼▼▼                     ☿      │
╰─────────────────────────────────────────────╯

    Lightning-Fast Downloads • Handle With Care
    
    """

def get_compact_logo():
    """Return a compact ASCII logo for smaller displays."""
    return """
    ▓▓▓▓  VidSnatch  ▓▓▓▓  ⚠
   ▓████  Download  ████▓   
  ▓██████ Videos ██████▓    
 ▓████████████████████▓     
▓██████▼▼▼▼▼▼▼██████▓       
 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▓           
   ▼▼▼▼▼▼▼▼▼▼▼         ☿   
    Swift Downloads          
    """

def print_startup_logo():
    """Print the startup logo with color if available."""
    try:
        # Try to use colors if available
        import colorama
        from colorama import Fore, Style
        colorama.init()
        
        logo = get_ascii_logo()
        # Color the logo with download arrow theme (blue to orange gradient)
        colored_logo = logo.replace('▲', f'{Fore.CYAN}▲{Style.RESET_ALL}')
        colored_logo = colored_logo.replace('▼', f'{Fore.YELLOW}▼{Style.RESET_ALL}')
        colored_logo = colored_logo.replace('█', f'{Fore.BLUE}█{Style.RESET_ALL}')
        colored_logo = colored_logo.replace('▓', f'{Fore.CYAN}▓{Style.RESET_ALL}')
        colored_logo = colored_logo.replace('▒', f'{Fore.WHITE}▒{Style.RESET_ALL}')
        colored_logo = colored_logo.replace('░', f'{Fore.WHITE}░{Style.RESET_ALL}')
        colored_logo = colored_logo.replace('⚠', f'{Fore.YELLOW}{Style.BRIGHT}⚠{Style.RESET_ALL}')
        colored_logo = colored_logo.replace('☿', f'{Fore.MAGENTA}{Style.BRIGHT}☿{Style.RESET_ALL}')
        colored_logo = colored_logo.replace('VidSnatch', f'{Fore.BLUE}{Style.BRIGHT}VidSnatch{Style.RESET_ALL}')
        colored_logo = colored_logo.replace('Download', f'{Fore.CYAN}Download{Style.RESET_ALL}')
        colored_logo = colored_logo.replace('Videos', f'{Fore.CYAN}Videos{Style.RESET_ALL}')
        print(colored_logo)
    except ImportError:
        # Fall back to plain ASCII if colorama not available
        print(get_ascii_logo())

if __name__ == "__main__":
    print_startup_logo()