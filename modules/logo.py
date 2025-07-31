"""ASCII art logo for VidSnatch with Mercury symbolism."""

def get_ascii_logo():
    """Return ASCII art logo that subtly represents the Mercury planetary symbol.
    
    The design uses crescents, circles, and lines to create the Mercury symbol (☿)
    which represents communication, speed, and transformation - perfect for video downloading.
    """
    return """
    ╭─────────────────────────────────────────╮
    │                                         │
    │        ◜◝     VidSnatch     ◜◝         │
    │      ◜   ◝                 ◜   ◝       │
    │     ◜  ╭─○─╮  Fast Video  ◜  ╭─○─╮     │
    │    ◝   │   │   Downloader ◝   │   │     │
    │   ◟    ╰─○─╯              ◟    ╰─○─╯    │
    │  ◟ ◜                     ◟ ◜           │
    │ ◟   ◝      ╭─────╮      ◟   ◝          │
    │◟     ◜     │  ☿  │     ◟     ◜         │
    │       ◝    ╰──┬──╯    ◟       ◝        │
    │        ◜      │      ◟         ◜       │
    │         ◝     ┼     ◟          ◝       │
    │          ◜    │    ◟           ◜       │
    │           ◝   ╱╲  ◟            ◝       │
    │            ◜ ╱  ╲◟             ◜       │
    │             ◝╱  ╲              ◝       │
    │              ╱  ╲               ◜      │
    │                                         │
    ╰─────────────────────────────────────────╯
    
    Mercury's Blessing: Swift Downloads, Seamless Transformation
    
    """

def get_compact_logo():
    """Return a compact ASCII logo for smaller displays."""
    return """
     ◜◝  VidSnatch  ◜◝
    ◜ ╭○╮ Download ◜ ╭○╮
   ◟  ╰○╯  Videos  ◟  ╰○╯
  ◟◜    ☿ ┼ ╱╲    ◟◜
    Mercury's Swift Touch
    """

def print_startup_logo():
    """Print the startup logo with color if available."""
    try:
        # Try to use colors if available
        import colorama
        from colorama import Fore, Style
        colorama.init()
        
        logo = get_ascii_logo()
        # Color the logo with Mercury-inspired colors (blue-green gradient)
        colored_logo = logo.replace('◜', f'{Fore.CYAN}◜{Style.RESET_ALL}')
        colored_logo = colored_logo.replace('◝', f'{Fore.BLUE}◝{Style.RESET_ALL}')
        colored_logo = colored_logo.replace('◟', f'{Fore.GREEN}◟{Style.RESET_ALL}')
        colored_logo = colored_logo.replace('○', f'{Fore.YELLOW}○{Style.RESET_ALL}')
        colored_logo = colored_logo.replace('☿', f'{Fore.MAGENTA}☿{Style.RESET_ALL}')
        colored_logo = colored_logo.replace('VidSnatch', f'{Fore.BLUE}{Style.BRIGHT}VidSnatch{Style.RESET_ALL}')
        print(colored_logo)
    except ImportError:
        # Fall back to plain ASCII if colorama not available
        print(get_ascii_logo())

if __name__ == "__main__":
    print_startup_logo()