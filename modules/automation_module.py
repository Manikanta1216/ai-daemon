"""
JARVIS AI — Automation Module
Handles file operations, clipboard, and workflow automation.
"""

import logging
import os
import shutil
from modules.face_monitor_module import start_face_monitor, stop_face_monitor

logger = logging.getLogger("jarvis.modules.automation")


def create_folder(folder_name: str) -> str:
    """Create a new folder."""
    if not folder_name:
        return "Please specify a folder name."
    try:
        os.makedirs(folder_name, exist_ok=True)
        logger.info(f"Created folder: {folder_name}")
        return f"Folder '{folder_name}' created successfully"
    except Exception as e:
        return f"Failed to create folder: {e}"


def create_file(filename: str) -> str:
    """Create a new empty file."""
    if not filename:
        return "Please specify a file name."
    try:
        with open(filename, "w") as f:
            pass
        logger.info(f"Created file: {filename}")
        return f"File '{filename}' created successfully"
    except Exception as e:
        return f"Failed to create file: {e}"


def delete_file(filename: str) -> str:
    """Delete a file (requires confirmation at executor level)."""
    if not filename:
        return "Please specify a file name."
    try:
        if os.path.isfile(filename):
            os.remove(filename)
            return f"File '{filename}' deleted"
        elif os.path.isdir(filename):
            shutil.rmtree(filename)
            return f"Folder '{filename}' deleted"
        else:
            return f"'{filename}' not found"
    except Exception as e:
        return f"Failed to delete: {e}"


def copy_to_clipboard(text: str) -> str:
    """Copy text to clipboard."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return "Copied to clipboard"
    except ImportError:
        return "pyperclip not installed for clipboard operations"


def get_clipboard() -> str:
    """Get text from clipboard."""
    try:
        import pyperclip
        text = pyperclip.paste()
        return f"Clipboard contains: {text[:200]}"
    except ImportError:
        return "pyperclip not installed"


def file_operation(action: str, filename: str = "", **kwargs) -> str:
    """Route file operations."""
    actions = {
        "create_folder": create_folder,
        "create_file": create_file,
        "delete": delete_file,
    }
    func = actions.get(action)
    if func:
        return func(filename)
    return f"Unknown file operation: {action}"


def type_text(text: str) -> str:
    """Type text using keyboard simulation."""
    if not text:
        return "Nothing to type."
    try:
        import pyautogui
        pyautogui.write(text, interval=0.05)
        return f"Typed: {text[:20]}..."
    except Exception as e:
        return f"Typing failed: {e}"


def press_key(key: str) -> str:
    """Press a specific key or hotkey."""
    if not key:
        return "No key specified."
    try:
        import pyautogui
        # Handle hotkeys like "ctrl+c"
        if "+" in key:
            keys = [k.strip() for k in key.split("+")]
            pyautogui.hotkey(*keys)
        else:
            pyautogui.press(key)
        return f"Pressed: {key}"
    except Exception as e:
        return f"Key press failed: {e}"


def click_mouse(x: int = None, y: int = None) -> str:
    """Click mouse at current position or specified coordinates."""
    try:
        import pyautogui
        if x is not None and y is not None:
            pyautogui.click(x, y)
            return f"Clicked at {x}, {y}"
        else:
            pyautogui.click()
            return "Clicked at current position"
    except Exception as e:
        return f"Click failed: {e}"


def window_control(action: str, window_title: str = "") -> str:
    """Minimize, maximize, or close windows."""
    try:
        import pygetwindow as gw
        if not window_title:
            # Target active window
            win = gw.getActiveWindow()
        else:
            wins = gw.getWindowsWithTitle(window_title)
            win = wins[0] if wins else None

        if not win:
            return f"Window '{window_title}' not found."

        if action == "minimize":
            win.minimize()
        elif action == "maximize":
            win.maximize()
        elif action == "close":
            win.close()
        return f"Window {action} successful"
    except Exception as e:
        return f"Window control failed: {e}"


def wait(seconds: str) -> str:
    """Pause execution for a specified number of seconds."""
    try:
        import time
        s = float(seconds)
        time.sleep(s)
        return f"Waited {s} seconds"
    except Exception:
        return "Invalid wait duration"


def focus_window(title: str) -> str:
    """Bring a window to the front."""
    try:
        import pygetwindow as gw
        wins = gw.getWindowsWithTitle(title)
        if wins:
            wins[0].activate()
            return f"Focused window: {title}"
        return f"Window '{title}' not found"
    except Exception as e:
        return f"Focus failed: {e}"


def gui_automation(action: str, value: str = "", **kwargs) -> str:
    """Route GUI automation tasks."""
    actions = {
        "type_text": type_text,
        "press_key": press_key,
        "click": lambda val: click_mouse(),
        "minimize": lambda val: window_control("minimize", val),
        "maximize": lambda val: window_control("maximize", val),
        "wait": wait,
        "focus": focus_window,
    }
    func = actions.get(action)
    if func:
        return func(value)
    return f"Unknown automation action: {action}"


# Module capabilities
CAPABILITIES = {
    "file_operation": {
        "handler": lambda entities: file_operation(
            action=entities.get("action", ""),
            filename=entities.get("filename", ""),
        ),
        "description": "File and folder operations",
        "dangerous": True,
    },
    "automation": {
        "handler": lambda entities: gui_automation(
            action=entities.get("type", ""),
            value=entities.get("value", ""),
        ),
        "description": "GUI and keyboard automation",
        "dangerous": True,
    },
    "face_monitor": {
        "handler": lambda entities: start_face_monitor() if entities.get("state", "start").lower() == "start" else stop_face_monitor(),
        "description": "Continuous live face‑recognition side‑car monitor",
        "dangerous": False,
    },
}
