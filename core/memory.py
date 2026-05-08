"""
JARVIS AI — Memory System (Upgraded)
Short-term (session) and long-term (persistent) memory backed by JSON files.

NEW in v2:
  - Conversation context tracking (last contact, last app, last action)
  - Follow-up support ("send again", "reply him", "open that app")
  - Last 20 interaction window for LLM context injection
  - Contact/user tracking across sessions
"""

import json
import logging
import time
from pathlib import Path
from collections import deque

logger = logging.getLogger("jarvis.memory")


class Memory:
    """
    Dual-layer memory system with conversation context:
    - Short-term: recent commands, conversation context (session only, max 50 items)
    - Long-term: user preferences, frequent apps, names (persisted to disk)
    - Context: last contact, last app, last action for follow-up commands
    """

    def __init__(self):
        from config import MEMORY_DIR
        self.memory_dir = Path(MEMORY_DIR)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.short_term_path = self.memory_dir / "short_term.json"
        self.long_term_path = self.memory_dir / "long_term.json"

        # Short-term: recent commands and context
        self.short_term = deque(maxlen=50)

        # Conversation context for follow-up resolution
        self._context = {
            "contact": None,     # last contacted person
            "message": None,     # last message sent
            "app": None,         # last opened app
            "media": None,       # last played media
            "last_command": None, # last raw command for "do it again"
            "last_intent": None,  # last classified intent
        }

        # Long-term: persistent data
        self.long_term = self._load_long_term()

        # Load any previous short-term data
        self._load_short_term()

        logger.info("Memory system initialized (v2 — with context tracking)")

    # ====================================================
    # CONVERSATION CONTEXT (for follow-up commands)
    # ====================================================

    def set_context(self, key: str, value):
        """Store a context value for follow-up resolution."""
        if key and value:
            self._context[key] = value
            logger.debug(f"Context set: {key} = {value}")

    def get_last_context(self, key: str):
        """Retrieve a context value."""
        return self._context.get(key)

    def get_full_context(self) -> dict:
        """Get all current context."""
        return {k: v for k, v in self._context.items() if v is not None}

    # ====================================================
    # SHORT-TERM MEMORY
    # ====================================================

    def remember_command(self, command: str, intent: str, result: str = None):
        """Store a command in short-term memory."""
        entry = {
            "command": command,
            "intent": intent,
            "result": result,
            "timestamp": time.time(),
        }
        self.short_term.append(entry)
        self._save_short_term()

        # Update context
        self._context["last_command"] = command
        self._context["last_intent"] = intent

        # Track frequently used intents in long-term
        freq = self.long_term.get("intent_frequency", {})
        freq[intent] = freq.get(intent, 0) + 1
        self.long_term["intent_frequency"] = freq

        # Track frequently used apps
        if intent in ("open_app", "open_website"):
            apps = self.long_term.get("frequent_apps", {})
            app_name = command.replace("open ", "").strip()
            apps[app_name] = apps.get(app_name, 0) + 1
            self.long_term["frequent_apps"] = apps

        self._save_long_term()

    def get_recent_commands(self, n: int = 10) -> list:
        """Get the last N commands."""
        return list(self.short_term)[-n:]

    def get_context(self) -> str:
        """Get recent conversation context as a string for LLM prompts."""
        recent = self.get_recent_commands(5)
        if not recent:
            return "No recent conversation history."
        lines = []
        for entry in recent:
            lines.append(f"User: {entry['command']}")
            if entry.get("result"):
                lines.append(f"Jarvis: {entry['result']}")
        return "\n".join(lines)

    def get_conversation_window(self, n: int = 20) -> list[dict]:
        """
        Get last N interactions for LLM context injection.
        Returns list of {role: "user"/"assistant", content: str}
        """
        recent = self.get_recent_commands(n)
        messages = []
        for entry in recent:
            messages.append({"role": "user", "content": entry["command"]})
            if entry.get("result") and entry["result"] != "__EXIT__":
                messages.append({"role": "assistant", "content": entry["result"]})
        return messages

    # ====================================================
    # LONG-TERM MEMORY
    # ====================================================

    def set_preference(self, key: str, value):
        """Store a user preference."""
        prefs = self.long_term.get("preferences", {})
        prefs[key] = value
        self.long_term["preferences"] = prefs
        self._save_long_term()
        logger.info(f"Preference saved: {key}={value}")

    def get_preference(self, key: str, default=None):
        """Retrieve a user preference."""
        return self.long_term.get("preferences", {}).get(key, default)

    def remember_name(self, name: str):
        """Store a recognized user name."""
        self.long_term["last_user"] = name
        names = self.long_term.get("known_users", [])
        if name not in names:
            names.append(name)
            self.long_term["known_users"] = names
        self._save_long_term()

    def get_last_user(self) -> str:
        """Get the last recognized user."""
        return self.long_term.get("last_user", "User")

    def remember_fact(self, fact: str):
        """Store a general fact the user asked Jarvis to remember."""
        facts = self.long_term.get("facts", [])
        facts.append({"fact": fact, "timestamp": time.time()})
        self.long_term["facts"] = facts
        self._save_long_term()

    def recall_facts(self) -> list:
        """Recall all stored facts."""
        return self.long_term.get("facts", [])

    # ====================================================
    # CONTACT MEMORY
    # ====================================================

    def remember_contact(self, name: str, phone: str = None, email: str = None):
        """Store a contact for future reference."""
        contacts = self.long_term.get("contacts", {})
        name_lower = name.lower()
        if name_lower not in contacts:
            contacts[name_lower] = {}
        if phone:
            contacts[name_lower]["phone"] = phone
        if email:
            contacts[name_lower]["email"] = email
        contacts[name_lower]["name"] = name
        self.long_term["contacts"] = contacts
        self._save_long_term()
        logger.info(f"Contact saved: {name}")

    def get_contact(self, name: str) -> dict | None:
        """Retrieve a contact by name."""
        contacts = self.long_term.get("contacts", {})
        return contacts.get(name.lower())

    def list_contacts(self) -> list[str]:
        """List all known contact names."""
        contacts = self.long_term.get("contacts", {})
        return [c.get("name", k) for k, c in contacts.items()]

    # ====================================================
    # STATS
    # ====================================================

    def get_frequent_apps(self, n: int = 5) -> list:
        """Get top N most frequently used apps."""
        apps = self.long_term.get("frequent_apps", {})
        sorted_apps = sorted(apps.items(), key=lambda x: x[1], reverse=True)
        return [app for app, count in sorted_apps[:n]]

    def get_stats(self) -> dict:
        """Get memory statistics."""
        return {
            "short_term_entries": len(self.short_term),
            "known_users": len(self.long_term.get("known_users", [])),
            "stored_facts": len(self.long_term.get("facts", [])),
            "contacts": len(self.long_term.get("contacts", {})),
            "frequent_apps": self.get_frequent_apps(),
            "total_commands": sum(
                self.long_term.get("intent_frequency", {}).values()
            ),
        }

    # ====================================================
    # PERSISTENCE
    # ====================================================

    def _load_short_term(self):
        """Load short-term memory from disk."""
        try:
            if self.short_term_path.exists():
                with open(self.short_term_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for entry in data[-50:]:
                        self.short_term.append(entry)
        except Exception as e:
            logger.warning(f"Failed to load short-term memory: {e}")

    def _save_short_term(self):
        """Save short-term memory to disk."""
        try:
            with open(self.short_term_path, "w", encoding="utf-8") as f:
                json.dump(list(self.short_term), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save short-term memory: {e}")

    def _load_long_term(self) -> dict:
        """Load long-term memory from disk."""
        try:
            if self.long_term_path.exists():
                with open(self.long_term_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Ensure new keys exist
                    data.setdefault("contacts", {})
                    return data
        except Exception as e:
            logger.warning(f"Failed to load long-term memory: {e}")
        return {
            "preferences": {},
            "known_users": [],
            "facts": [],
            "contacts": {},
            "frequent_apps": {},
            "intent_frequency": {},
        }

    def _save_long_term(self):
        """Save long-term memory to disk."""
        try:
            with open(self.long_term_path, "w", encoding="utf-8") as f:
                json.dump(self.long_term, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save long-term memory: {e}")

    def clear_short_term(self):
        """Clear session memory."""
        self.short_term.clear()
        self._context = {k: None for k in self._context}
        self._save_short_term()

    def clear_all(self):
        """Clear all memory (use with caution)."""
        self.short_term.clear()
        self._context = {k: None for k in self._context}
        self.long_term = {
            "preferences": {},
            "known_users": [],
            "facts": [],
            "contacts": {},
            "frequent_apps": {},
            "intent_frequency": {},
        }
        self._save_short_term()
        self._save_long_term()


# ============================================
# SINGLETON
# ============================================
_memory = None


def get_memory() -> Memory:
    """Get or create the global memory singleton."""
    global _memory
    if _memory is None:
        _memory = Memory()
    return _memory
