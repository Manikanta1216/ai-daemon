"""
JARVIS AI — Browser Module
Handles opening websites, searching, and web navigation.
"""

import logging
import webbrowser

logger = logging.getLogger("jarvis.modules.browser")

# Well-known URL mappings
KNOWN_SITES = {
    "youtube": "https://youtube.com",
    "google": "https://google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "linkedin": "https://linkedin.com",
    "chatgpt": "https://chat.openai.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "facebook": "https://facebook.com",
    "instagram": "https://instagram.com",
    "reddit": "https://reddit.com",
    "stackoverflow": "https://stackoverflow.com",
    "amazon": "https://amazon.in",
    "flipkart": "https://flipkart.com",
    "netflix": "https://netflix.com",
    "spotify": "https://open.spotify.com",
    "whatsapp web": "https://web.whatsapp.com",
}


def open_website(url: str = None, app: str = None) -> str:
    """Open a website by URL or app name."""
    # Resolve URL from app name if needed
    if not url and app:
        app_clean = str(app).lower().strip()
        url = KNOWN_SITES.get(app_clean)
        if not url:
            if "." in app_clean or "http" in app_clean:
                url = app_clean if app_clean.startswith("http") else f"https://{app_clean}"

    if not url:
        return f"I don't know the URL for '{app or 'that'}'"

    # Ensure url is a clean string
    url = str(url).strip()

    try:
        webbrowser.open(url)
        name = app or url
        logger.info(f"Opened website: {url}")
        return f"Opening {name}"
    except Exception as e:
        logger.error(f"Failed to open website: {e}")
        return f"Failed to open website: {e}"


def search_google(query: str) -> str:
    """Search Google for a query."""
    url = f"https://www.google.com/search?q={query}"
    webbrowser.open(url)
    logger.info(f"Google search: {query}")
    return f"Searching Google for: {query}"


def search_youtube(query: str) -> str:
    """Search YouTube for a query."""
    url = f"https://www.youtube.com/results?search_query={query}"
    webbrowser.open(url)
    logger.info(f"YouTube search: {query}")
    return f"Searching YouTube for: {query}"


def search(query: str, engine: str = "google") -> str:
    """Search using specified engine."""
    engines = {
        "google": search_google,
        "youtube": search_youtube,
    }
    func = engines.get(engine.lower(), search_google)
    return func(query)


# Module capabilities for auto-registration
CAPABILITIES = {
    "open_website": {
        "handler": lambda entities: open_website(
            url=entities.get("url", ""),
            app=entities.get("app", ""),
        ),
        "description": "Open a website in the browser",
    },
    "search": {
        "handler": lambda entities: search(
            entities.get("query", ""),
            entities.get("engine", "google"),
        ),
        "description": "Search the web",
    },
}
