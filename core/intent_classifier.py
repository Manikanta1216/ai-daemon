"""
JARVIS AI — Intent Classifier (Upgraded)
Uses LLM to analyze user commands and extract structured intents/entities.
Falls back to keyword matching when LLM is unavailable.

NEW in v2:
  - Uses app_resolver for fuzzy app/website matching
  - Better compound command awareness (delegates to agent for multi-task)
  - Context-aware classification using memory
  - Dynamic entity extraction
"""

import logging
import re

logger = logging.getLogger("jarvis.intent")


class IntentClassifier:
    """Classifies user commands into structured intents with entities."""

    def __init__(self):
        self._llm = None

    @property
    def llm(self):
        """Lazy-load LLM client."""
        if self._llm is None:
            try:
                from ai.llm_client import get_llm_client
                self._llm = get_llm_client()
            except Exception as e:
                logger.warning(f"LLM client unavailable: {e}")
        return self._llm

    def classify(self, command: str) -> dict:
        """
        Classify a user command.
        Returns: {
            "intent": str,
            "entities": dict,
            "confidence": float,
            "task_plan": list[str]
        }
        """
        if not command or not command.strip():
            return {
                "intent": "unknown",
                "entities": {},
                "confidence": 0.0,
                "task_plan": [],
            }

        command_lower = command.lower().strip()

        # First: try keyword/pattern classification (fast path)
        keyword_result = self._keyword_classify(command_lower)
        if keyword_result and keyword_result["confidence"] >= 0.8:
            logger.info(
                f"Keyword match: intent={keyword_result['intent']} "
                f"confidence={keyword_result['confidence']}"
            )
            return keyword_result

        # Second: try LLM classification
        if self.llm:
            try:
                llm_result = self.llm.analyze_intent(command)
                if llm_result.get("intent") and llm_result["intent"] != "unknown":
                    # Resolve app names through app_resolver
                    llm_result = self._resolve_entities(llm_result)
                    logger.info(
                        f"LLM match: intent={llm_result['intent']} "
                        f"confidence={llm_result.get('confidence', 0)}"
                    )
                    return llm_result
            except Exception as e:
                logger.error(f"LLM classification error: {e}")

        # Third: fall back to keyword with lower threshold
        if keyword_result:
            return keyword_result

        # Final: treat as chat
        return {
            "intent": "chat",
            "entities": {"query": command},
            "confidence": 0.3,
            "task_plan": [f"Respond conversationally to: {command}"],
        }

    def _resolve_entities(self, intent_data: dict) -> dict:
        """Resolve app/website names in entities using app_resolver."""
        entities = intent_data.get("entities", {})
        intent = intent_data.get("intent", "")

        if intent in ("open_app", "open_website") and entities.get("app"):
            from core.app_resolver import resolve_target
            resolved = resolve_target(entities["app"])
            if resolved["type"] == "website":
                intent_data["intent"] = "open_website"
                entities["url"] = resolved["url"]
                entities["app"] = resolved["name"]
            elif resolved["type"] == "app":
                intent_data["intent"] = "open_app"
                entities["app"] = resolved["name"]

        return intent_data

    def _keyword_classify(self, command: str) -> dict | None:
        """Fast keyword-based intent classification with dynamic resolution."""

        # === EXIT ===
        if any(w in command for w in ["bye", "exit", "stop", "quit", "goodbye"]):
            return {
                "intent": "exit",
                "entities": {},
                "confidence": 0.95,
                "task_plan": ["Shutdown JARVIS"],
            }

        # === GREETINGS ===
        if any(w in command for w in [
            "hello", "hi jarvis", "hey jarvis", "hi ", "hey ",
            "good morning", "good night", "good afternoon", "good evening",
            "how are you", "what's up", "sup",
        ]):
            return {
                "intent": "chat",
                "entities": {"query": command},
                "confidence": 0.85,
                "task_plan": ["Respond with greeting"],
            }

        # === SYSTEM CONTROL ===
        for word, action in [
            ("shutdown", "shutdown"), ("shut down", "shutdown"),
            ("restart", "restart"), ("reboot", "restart"),
            ("lock", "lock"), ("lock system", "lock"),
            ("sleep", "sleep"), ("hibernate", "sleep"),
        ]:
            if word in command:
                return {
                    "intent": "system_control",
                    "entities": {"action": action},
                    "confidence": 0.9,
                    "task_plan": [f"System {action}"],
                }

        # === VOLUME ===
        if "volume up" in command or "increase volume" in command or "louder" in command:
            return {
                "intent": "volume_control",
                "entities": {"action": "volume_up"},
                "confidence": 0.9,
                "task_plan": ["Volume up"],
            }
        if "volume down" in command or "decrease volume" in command or "quieter" in command:
            return {
                "intent": "volume_control",
                "entities": {"action": "volume_down"},
                "confidence": 0.9,
                "task_plan": ["Volume down"],
            }
        if "mute" in command or "unmute" in command:
            return {
                "intent": "volume_control",
                "entities": {"action": "mute"},
                "confidence": 0.9,
                "task_plan": ["Toggle mute"],
            }

        # === SCREENSHOT ===
        if "screenshot" in command or "screen capture" in command:
            return {
                "intent": "screenshot",
                "entities": {},
                "confidence": 0.95,
                "task_plan": ["Take screenshot"],
            }

        # === WEATHER ===
        if "weather" in command:
            # Try to extract city
            m = re.search(r"weather (?:in|for|at) (.+)", command)
            city = m.group(1).strip() if m else ""
            return {
                "intent": "weather",
                "entities": {"city": city},
                "confidence": 0.9,
                "task_plan": [f"Get weather{' for ' + city if city else ''}"],
            }

        # === INFO QUERIES ===
        for word, query in [
            ("what time", "time"), ("current time", "time"), ("the time", "time"),
            ("today's date", "date"), ("what date", "date"), ("the date", "date"),
            ("battery", "battery"), ("battery level", "battery"),
            ("system info", "system_info"), ("system information", "system_info"),
            ("check internet", "internet"), ("internet status", "internet"),
            ("tell me a joke", "joke"), ("joke", "joke"),
        ]:
            if word in command:
                return {
                    "intent": "get_info",
                    "entities": {"query": query},
                    "confidence": 0.9,
                    "task_plan": [f"Get {query}"],
                }

        # === SEARCH ===
        m = re.match(r"search (?:google|web|the web) (?:for )?(.+)", command)
        if m:
            return {
                "intent": "search",
                "entities": {"query": m.group(1).strip(), "engine": "google"},
                "confidence": 0.85,
                "task_plan": [f"Search Google for: {m.group(1).strip()}"],
            }

        m = re.match(r"search youtube (?:for )?(.+)", command)
        if m:
            return {
                "intent": "search",
                "entities": {"query": m.group(1).strip(), "engine": "youtube"},
                "confidence": 0.85,
                "task_plan": [f"Search YouTube for: {m.group(1).strip()}"],
            }

        m = re.match(r"(?:google|search for) (.+)", command)
        if m:
            return {
                "intent": "search",
                "entities": {"query": m.group(1).strip(), "engine": "google"},
                "confidence": 0.8,
                "task_plan": [f"Search for: {m.group(1).strip()}"],
            }

        # === PLAY MEDIA ===
        m = re.match(r"play (?:music |song |video )?(.+)", command)
        if m:
            return {
                "intent": "play_media",
                "entities": {"query": m.group(1).strip()},
                "confidence": 0.8,
                "task_plan": [f"Play: {m.group(1).strip()}"],
            }

        # === SEND EMAIL ===
        m = re.match(
            r"send (?:an? )?email to (.+?)(?:saying|with message|body) (.+)",
            command,
        )
        if m:
            return {
                "intent": "send_email",
                "entities": {
                    "recipient": m.group(1).strip(),
                    "body": m.group(2).strip(),
                },
                "confidence": 0.85,
                "task_plan": [f"Send email to {m.group(1).strip()}"],
            }

        # === SEND WHATSAPP ===
        m = re.match(
            r"(?:send (?:a )?whatsapp (?:message )?to|message|whatsapp) "
            r"(\w+)\s+(.+)",
            command,
        )
        if m:
            return {
                "intent": "send_whatsapp",
                "entities": {
                    "recipient": m.group(1).strip(),
                    "body": m.group(2).strip(),
                },
                "confidence": 0.85,
                "task_plan": [f"Send WhatsApp to {m.group(1).strip()}"],
            }

        # === FILE OPERATIONS ===
        m = re.match(r"create (?:a )?folder (.+)", command)
        if m:
            return {
                "intent": "file_operation",
                "entities": {"action": "create_folder", "filename": m.group(1).strip()},
                "confidence": 0.9,
                "task_plan": [f"Create folder: {m.group(1).strip()}"],
            }

        m = re.match(r"create (?:a )?file (.+)", command)
        if m:
            return {
                "intent": "file_operation",
                "entities": {"action": "create_file", "filename": m.group(1).strip()},
                "confidence": 0.9,
                "task_plan": [f"Create file: {m.group(1).strip()}"],
            }

        # === OPEN (dynamic — uses app_resolver) ===
        m = re.match(r"open (.+)", command)
        if m:
            target = m.group(1).strip()
            from core.app_resolver import resolve_target
            resolved = resolve_target(target)

            if resolved["type"] == "website":
                return {
                    "intent": "open_website",
                    "entities": {"url": resolved["url"], "app": resolved["name"]},
                    "confidence": 0.85,
                    "task_plan": [f"Open website: {resolved['name']}"],
                }
            elif resolved["type"] == "app":
                return {
                    "intent": "open_app",
                    "entities": {"app": resolved["name"]},
                    "confidence": 0.85,
                    "task_plan": [f"Open application: {resolved['name']}"],
                }
            else:
                # Unknown — still try
                return {
                    "intent": "open_app",
                    "entities": {"app": target},
                    "confidence": 0.6,
                    "task_plan": [f"Try to open: {target}"],
                }

        return None


# ============================================
# SINGLETON
# ============================================
_classifier = None


def get_classifier() -> IntentClassifier:
    """Get or create global intent classifier."""
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier
