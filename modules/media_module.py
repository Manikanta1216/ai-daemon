"""
JARVIS AI — Media Module
Handles screenshots, playing media, camera operations.
"""

import logging
import os
import time

logger = logging.getLogger("jarvis.modules.media")


def take_screenshot() -> str:
    """Capture a screenshot and save it."""
    try:
        import pyautogui
        timestamp = int(time.time())
        filename = f"screenshot_{timestamp}.png"
        img = pyautogui.screenshot()
        img.save(filename)
        logger.info(f"Screenshot saved: {filename}")
        return f"Screenshot saved as {filename}"
    except ImportError:
        return "pyautogui not installed for screenshots"
    except Exception as e:
        logger.error(f"Screenshot error: {e}")
        return f"Failed to take screenshot: {e}"


def play_media(query: str) -> str:
    """Play music/video on YouTube."""
    try:
        import pywhatkit
        pywhatkit.playonyt(query)
        logger.info(f"Playing on YouTube: {query}")
        return f"Playing {query}"
    except ImportError:
        # Fallback to YouTube search
        url = f"https://www.youtube.com/results?search_query={query}"
        os.system(f'start "" "{url}"')
        return f"Searching YouTube for: {query}"
    except Exception as e:
        logger.error(f"Play media error: {e}")
        return f"Failed to play {query}: {e}"


def open_camera() -> str:
    """Open the system camera app."""
    os.system("start microsoft.windows.camera:")
    return "Opening camera"


def capture_photo() -> str:
    """Capture a photo from webcam."""
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return "Camera not accessible"
        ret, frame = cap.read()
        cap.release()
        if ret:
            timestamp = int(time.time())
            filename = f"photo_{timestamp}.jpg"
            cv2.imwrite(filename, frame)
            return f"Photo saved as {filename}"
        return "Failed to capture photo"
    except ImportError:
        return "OpenCV not installed for camera"
    except Exception as e:
        return f"Camera error: {e}"


# Module capabilities for auto-registration
CAPABILITIES = {
    "screenshot": {
        "handler": lambda entities: take_screenshot(),
        "description": "Take a screenshot",
    },
    "play_media": {
        "handler": lambda entities: play_media(entities.get("query", "")),
        "description": "Play music or video",
    },
}
