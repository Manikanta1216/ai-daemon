"""
JARVIS AI — WhatsApp Module
Handles WhatsApp messaging via pywhatkit.
"""

import logging

logger = logging.getLogger("jarvis.modules.whatsapp")


import json
import os
import time

_CONTACTS_FILE = os.path.join(os.path.dirname(__file__), "contacts.json")

def _load_contacts():
    """Load contact mapping from JSON."""
    if os.path.exists(_CONTACTS_FILE):
        try:
            with open(_CONTACTS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"prasad": "+911234567890"}  # Default placeholder

def _resolve_contact(name: str) -> str:
    """Convert name to phone number."""
    contacts = _load_contacts()
    return contacts.get(name.lower(), name)

def send_whatsapp(recipient: str, body: str = "", **kwargs) -> str:
    """
    Send a WhatsApp message with auto-send logic.
    """
    if not recipient:
        return "No recipient specified."

    # Resolve contact name to number
    phone = _resolve_contact(recipient)
    
    if not phone.startswith("+") and not phone.replace(" ", "").isdigit():
        return f"I don't have a phone number for '{recipient}'."

    if not phone.startswith("+"):
        phone = f"+91{phone}"

    try:
        import pywhatkit
        import pyautogui
        
        # Send message
        pywhatkit.sendwhatmsg_instantly(phone, body, wait_time=8, tab_close=True)
        
        # Give it a moment to load and then hit enter (automation)
        time.sleep(2)
        pyautogui.press("enter")
        
        logger.info(f"WhatsApp sent to {phone}")
        return f"WhatsApp message sent to {recipient}"
    except Exception as e:
        logger.error(f"WhatsApp error: {e}")
        return f"Failed to send: {e}"


# Module capabilities
CAPABILITIES = {
    "send_whatsapp": {
        "handler": lambda entities: send_whatsapp(
            recipient=entities.get("recipient", entities.get("contact", "")),
            body=entities.get("body", entities.get("message", "")),
        ),
        "description": "Send an autonomous WhatsApp message",
    },
}
