"""
JARVIS AI — Dynamic App & Action Resolver
Fuzzy matching, alias recognition, and intelligent fallback for app/website resolution.
Supports: "vs code" = "code" = "vscode" = "visual studio code"
"""

import logging
from difflib import get_close_matches

logger = logging.getLogger("jarvis.app_resolver")


# ============================================
# APP ALIAS DATABASE
# Maps any alias → (canonical_name, command)
# ============================================
APP_ALIASES = {
    # Browsers
    "chrome": ("Google Chrome", "start chrome"),
    "google chrome": ("Google Chrome", "start chrome"),
    "firefox": ("Firefox", "start firefox"),
    "mozilla": ("Firefox", "start firefox"),
    "edge": ("Microsoft Edge", "start msedge"),
    "microsoft edge": ("Microsoft Edge", "start msedge"),
    "brave": ("Brave", "start brave"),

    # Code editors
    "vs code": ("VS Code", "code"),
    "vscode": ("VS Code", "code"),
    "visual studio code": ("VS Code", "code"),
    "code": ("VS Code", "code"),
    "sublime": ("Sublime Text", "start sublime_text"),
    "sublime text": ("Sublime Text", "start sublime_text"),
    "notepad++": ("Notepad++", "start notepad++"),
    "atom": ("Atom", "start atom"),

    # System
    "notepad": ("Notepad", "notepad"),
    "calculator": ("Calculator", "calc"),
    "calc": ("Calculator", "calc"),
    "paint": ("Paint", "mspaint"),
    "camera": ("Camera", "start microsoft.windows.camera:"),
    "cmd": ("Command Prompt", "start cmd"),
    "command prompt": ("Command Prompt", "start cmd"),
    "terminal": ("Windows Terminal", "start wt"),
    "windows terminal": ("Windows Terminal", "start wt"),
    "powershell": ("PowerShell", "start powershell"),
    "explorer": ("File Explorer", "explorer"),
    "file explorer": ("File Explorer", "explorer"),
    "file manager": ("File Explorer", "explorer"),
    "task manager": ("Task Manager", "taskmgr"),
    "settings": ("Settings", "start ms-settings:"),
    "control panel": ("Control Panel", "control"),
    "device manager": ("Device Manager", "devmgmt.msc"),
    "snipping tool": ("Snipping Tool", "snippingtool"),
    "snip": ("Snipping Tool", "snippingtool"),

    # Office
    "word": ("Microsoft Word", "start winword"),
    "microsoft word": ("Microsoft Word", "start winword"),
    "excel": ("Microsoft Excel", "start excel"),
    "microsoft excel": ("Microsoft Excel", "start excel"),
    "powerpoint": ("PowerPoint", "start powerpnt"),
    "ppt": ("PowerPoint", "start powerpnt"),
    "outlook": ("Outlook", "start outlook"),
    "teams": ("Microsoft Teams", "start msteams:"),
    "onenote": ("OneNote", "start onenote:"),

    # Communication
    "whatsapp": ("WhatsApp", "start whatsapp:"),
    "telegram": ("Telegram", "start telegram:"),
    "discord": ("Discord", "start discord:"),
    "slack": ("Slack", "start slack:"),
    "zoom": ("Zoom", "start zoom"),
    "skype": ("Skype", "start skype:"),

    # Media
    "spotify": ("Spotify", "start spotify:"),
    "vlc": ("VLC", "start vlc"),
    "media player": ("Windows Media Player", "start wmplayer"),

    # Dev tools
    "docker": ("Docker Desktop", "start docker"),
    "git bash": ("Git Bash", 'start "" "C:\\Program Files\\Git\\git-bash.exe"'),
    "postman": ("Postman", "start postman"),
    "android studio": ("Android Studio", "start studio64"),
}

# ============================================
# WEBSITE ALIAS DATABASE
# Maps name → URL
# ============================================
WEBSITE_ALIASES = {
    "youtube": "https://youtube.com",
    "yt": "https://youtube.com",
    "google": "https://google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "linkedin": "https://linkedin.com",
    "chatgpt": "https://chat.openai.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "facebook": "https://facebook.com",
    "fb": "https://facebook.com",
    "instagram": "https://instagram.com",
    "insta": "https://instagram.com",
    "reddit": "https://reddit.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "amazon": "https://amazon.in",
    "flipkart": "https://flipkart.com",
    "netflix": "https://netflix.com",
    "spotify": "https://open.spotify.com",
    "whatsapp web": "https://web.whatsapp.com",
    "maps": "https://maps.google.com",
    "google maps": "https://maps.google.com",
    "drive": "https://drive.google.com",
    "google drive": "https://drive.google.com",
    "docs": "https://docs.google.com",
    "google docs": "https://docs.google.com",
    "sheets": "https://sheets.google.com",
    "google sheets": "https://sheets.google.com",
    "canva": "https://canva.com",
    "figma": "https://figma.com",
    "notion": "https://notion.so",
    "trello": "https://trello.com",
    "wikipedia": "https://wikipedia.org",
    "wiki": "https://wikipedia.org",
}


def resolve_app(name: str) -> dict | None:
    """
    Resolve an app name (with fuzzy matching) to its canonical name and command.

    Returns:
        {"name": str, "command": str} or None if not found
    """
    if not name:
        return None

    clean = name.lower().strip()

    # 1. Exact match
    if clean in APP_ALIASES:
        canonical, cmd = APP_ALIASES[clean]
        logger.debug(f"Exact app match: '{name}' → {canonical}")
        return {"name": canonical, "command": cmd}

    # 2. Fuzzy match
    all_aliases = list(APP_ALIASES.keys())
    matches = get_close_matches(clean, all_aliases, n=1, cutoff=0.7)
    if matches:
        canonical, cmd = APP_ALIASES[matches[0]]
        logger.info(f"Fuzzy app match: '{name}' → {canonical} (via '{matches[0]}')")
        return {"name": canonical, "command": cmd}

    # 3. Partial match — if the input contains a known alias
    for alias, (canonical, cmd) in APP_ALIASES.items():
        if alias in clean or clean in alias:
            logger.info(f"Partial app match: '{name}' → {canonical}")
            return {"name": canonical, "command": cmd}

    logger.debug(f"No app match for: '{name}'")
    return None


def resolve_website(name: str) -> dict | None:
    """
    Resolve a website name to its URL.

    Returns:
        {"name": str, "url": str} or None if not found
    """
    if not name:
        return None

    clean = name.lower().strip()

    # 1. Exact match
    if clean in WEBSITE_ALIASES:
        url = WEBSITE_ALIASES[clean]
        return {"name": clean.title(), "url": url}

    # 2. Check if it looks like a URL already
    if "." in clean or "http" in clean:
        url = clean if clean.startswith("http") else f"https://{clean}"
        return {"name": clean, "url": url}

    # 3. Fuzzy match
    all_sites = list(WEBSITE_ALIASES.keys())
    matches = get_close_matches(clean, all_sites, n=1, cutoff=0.7)
    if matches:
        url = WEBSITE_ALIASES[matches[0]]
        return {"name": matches[0].title(), "url": url}

    return None


def resolve_target(name: str) -> dict:
    """
    Resolve any target — tries app first, then website, then generic fallback.
    App takes priority so 'whatsapp' opens the desktop app, not the web version.

    Returns:
        {
            "type": "app" | "website" | "unknown",
            "name": str,
            "command": str (for apps) | "url": str (for websites)
        }
    """
    # Try app first (so "whatsapp" opens the app, not whatsapp web)
    app = resolve_app(name)
    if app:
        return {"type": "app", **app}

    # Then try website (for things like "youtube", "google")
    website = resolve_website(name)
    if website:
        return {"type": "website", **website}

    # Unknown — return a best-effort fallback
    return {
        "type": "unknown",
        "name": name,
        "command": f"start {name}",
    }


def get_app_suggestions(name: str, n: int = 3) -> list[str]:
    """Get suggested app names for a failed match."""
    all_aliases = list(APP_ALIASES.keys())
    return get_close_matches(name.lower(), all_aliases, n=n, cutoff=0.4)
