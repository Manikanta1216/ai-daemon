"""
JARVIS AI — Universal Task Executor (Upgraded)
Dynamic task dispatch engine. No hardcoded if-else chains.
Modules register their capabilities; executor routes intents to handlers.

NEW in v2:
  - Uses app_resolver for intelligent app opening
  - All outputs guaranteed to be clean strings (never dict/JSON)
  - Better offline chat with expanded knowledge base
  - Improved error recovery
"""

import logging
import importlib

logger = logging.getLogger("jarvis.executor")


class TaskExecutor:
    """
    Dynamic task execution engine.
    Modules register capabilities as {intent: handler} dictionaries.
    The executor routes classified intents to the correct handler.
    """

    def __init__(self):
        self._handlers = {}  # intent -> {"handler": callable, "description": str, "dangerous": bool}
        self._loaded = False

    def _load_modules(self):
        """Auto-discover and load all modules with CAPABILITIES."""
        if self._loaded:
            return

        module_names = [
            "modules.browser",
            "modules.system_module",
            "modules.media_module",
            "modules.email_module",
            "modules.whatsapp_module",
            "modules.automation_module",
        ]

        for mod_name in module_names:
            try:
                mod = importlib.import_module(mod_name)
                capabilities = getattr(mod, "CAPABILITIES", {})
                for intent, config in capabilities.items():
                    self.register(intent, config)
                logger.debug(f"Loaded module: {mod_name} ({len(capabilities)} capabilities)")
            except ImportError as e:
                logger.warning(f"Could not load module {mod_name}: {e}")
            except Exception as e:
                logger.error(f"Error loading module {mod_name}: {e}")

        self._loaded = True
        logger.info(f"Executor ready: {len(self._handlers)} intents registered")

    def register(self, intent: str, config: dict):
        """
        Register a handler for an intent.
        config: {"handler": callable, "description": str, "dangerous": bool}
        """
        self._handlers[intent] = config
        logger.debug(f"Registered: {intent} → {config.get('description', 'N/A')}")

    def execute(self, intent_data: dict) -> str:
        """
        Execute a task based on classified intent data.

        Args:
            intent_data: {
                "intent": str,
                "entities": dict,
                "confidence": float,
                "task_plan": list
            }

        Returns:
            Clean string result — NEVER a dict or JSON.
        """
        self._load_modules()

        intent = intent_data.get("intent", "unknown")
        entities = intent_data.get("entities", {})
        confidence = intent_data.get("confidence", 0)

        logger.info(f"Executing: intent={intent}, confidence={confidence}")
        logger.debug(f"Entities: {entities}")

        # Resolve app name through app_resolver for open_app intents
        if intent == "open_app":
            entities = self._resolve_app_entity(entities)

        # Check if we have a handler
        if intent in self._handlers:
            handler_config = self._handlers[intent]
            handler = handler_config["handler"]

            # Check if dangerous action requires confirmation
            if handler_config.get("dangerous", False):
                from config import REQUIRE_CONFIRMATION_FOR_DANGEROUS
                if REQUIRE_CONFIRMATION_FOR_DANGEROUS:
                    return self._request_confirmation(intent, entities, handler)

            try:
                result = handler(entities)
                return self._ensure_string(result)
            except Exception as e:
                logger.error(f"Handler error for {intent}: {e}")
                return f"Sorry, I encountered an error: {e}"

        # Intent not found — try LLM chat response
        if intent == "chat":
            return self._handle_chat(entities)

        # Exit intent
        if intent == "exit":
            return "__EXIT__"

        # Unknown intent
        logger.warning(f"No handler for intent: {intent}")
        return self._handle_unknown(intent, entities)

    def _resolve_app_entity(self, entities: dict) -> dict:
        """Resolve app names through app_resolver for better matching."""
        app_name = entities.get("app", "")
        if not app_name:
            return entities

        from core.app_resolver import resolve_app
        resolved = resolve_app(app_name)
        if resolved:
            entities["app"] = resolved["name"]
            entities["_command"] = resolved["command"]

        return entities

    def _ensure_string(self, result) -> str:
        """
        CRITICAL: Ensure any result is a clean, speakable string.
        This is the last line of defense against JSON/dict leaks.
        """
        if result is None:
            return "Done."

        if isinstance(result, str):
            text = result.strip()
            if not text:
                return "Done."
            # Block raw JSON strings
            if text.startswith("{") and text.endswith("}"):
                try:
                    import json
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        return self._extract_from_dict(parsed)
                except (ValueError, TypeError):
                    pass
            return text

        if isinstance(result, dict):
            return self._extract_from_dict(result)

        if isinstance(result, list):
            texts = [self._ensure_string(item) for item in result if item]
            return ". ".join(texts) if texts else "Done."

        return str(result)

    def _extract_from_dict(self, d: dict) -> str:
        """Extract human-readable text from a dict result."""
        for key in ("text", "answer", "response", "message", "result", "output"):
            value = d.get(key)
            if value and isinstance(value, str) and value.strip():
                return value.strip()
        # Build readable summary, skipping internal keys
        internal = {"intent", "confidence", "task_plan", "entities", "raw_response"}
        parts = []
        for k, v in d.items():
            if k in internal:
                continue
            if v is not None and str(v).strip():
                parts.append(f"{k}: {v}")
        return ". ".join(parts) if parts else "Done."

    def _request_confirmation(self, intent: str, entities: dict, handler) -> str:
        """Ask for confirmation before executing dangerous commands."""
        from core.speech import speak, listen

        desc = self._handlers[intent].get("description", intent)
        speak(f"This is a potentially dangerous action: {desc}. Are you sure?")
        response = listen()

        if response and any(w in response for w in ["yes", "yeah", "sure", "confirm", "do it"]):
            try:
                result = handler(entities)
                return self._ensure_string(result)
            except Exception as e:
                return f"Error: {e}"
        else:
            return "Action cancelled."

    def _handle_chat(self, entities: dict) -> str:
        """Handle conversational chat via LLM or offline fallback."""
        query = entities.get("query", entities.get("raw_response", ""))
        if not query:
            return "I'm here. How can I help?"

        try:
            from ai.llm_client import get_llm_client
            client = get_llm_client()
            response = client.chat_response(query)
            return self._ensure_string(response)
        except Exception as e:
            logger.error(f"Chat error: {e}")
            try:
                from ai.llm_client import get_llm_client
                client = get_llm_client()
                return client._offline_chat_response(query)
            except Exception:
                return self._basic_offline_response(query)

    def _handle_unknown(self, intent: str, entities: dict) -> str:
        """Handle unknown intents — try LLM, then offline fallback."""
        query = entities.get("query", "")
        if not query:
            return "I didn't understand that. Could you rephrase?"

        try:
            from ai.llm_client import get_llm_client
            client = get_llm_client()
            response = client.chat_response(
                f"The user said: '{query}'. Respond helpfully."
            )
            return self._ensure_string(response)
        except Exception:
            return self._basic_offline_response(query)

    def _basic_offline_response(self, query: str) -> str:
        """Ultra-basic offline response when everything else fails."""
        query_lower = query.lower()

        # Try to provide SOMETHING useful
        if any(w in query_lower for w in ["hello", "hi", "hey"]):
            return "Hello! How can I help you?"
        if "time" in query_lower:
            import datetime
            return f"The time is {datetime.datetime.now().strftime('%I:%M %p')}"
        if "date" in query_lower:
            import datetime
            return f"Today is {datetime.datetime.now().strftime('%B %d, %Y')}"
        if "how are you" in query_lower:
            return "I'm doing great, thank you for asking!"
        if "thank" in query_lower:
            return "You're welcome! Let me know if you need anything else."

        return (
            "I'm not sure about that right now. "
            "Try asking me to open apps, play music, or search the web."
        )

    def list_capabilities(self) -> list:
        """List all registered capabilities."""
        self._load_modules()
        return [
            {"intent": intent, "description": config.get("description", "N/A")}
            for intent, config in self._handlers.items()
        ]


# ============================================
# SINGLETON
# ============================================
_executor = None


def get_executor() -> TaskExecutor:
    """Get or create global task executor."""
    global _executor
    if _executor is None:
        _executor = TaskExecutor()
    return _executor
