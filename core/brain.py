"""
JARVIS AI — Brain (Main Orchestrator) — Upgraded
The central nervous system that ties everything together.
Handles: face auth → greeting → daemon loop → command processing.

NEW in v2:
  - Self-control logic: detects incomplete commands, asks clarification
  - Multi-task natural language status announcements
  - Absolute JSON/dict blocking at every layer
  - Conversation continuity through memory context
"""

import asyncio
import datetime
import json
import logging
import threading
import time

logger = logging.getLogger("jarvis.brain")


# ====================================================
# RESPONSE NORMALIZER — ensures only plain text is spoken
# ====================================================

# Keys that indicate structured/internal data — never speak these raw
_STRUCTURED_KEYS = {"intent", "confidence", "task_plan", "entities", "raw_response"}


def normalize_response(result) -> str:
    """
    Convert ANY executor output into a clean, speakable string.

    Handles:
      - None → generic fallback
      - dict with text/answer/response keys → extract the value
      - dict with only structured keys (intent, confidence) → ignore metadata
      - JSON strings → parse and extract
      - Everything else → str()
    """
    if result is None:
        return "I didn't understand that."

    # Already a clean string
    if isinstance(result, str):
        text = result.strip()
        if not text:
            return "Done."

        # Guard: detect raw JSON strings and extract meaningful content
        if text.startswith("{") and text.endswith("}"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return _extract_text_from_dict(parsed)
            except (json.JSONDecodeError, ValueError):
                pass  # Not valid JSON — treat as normal text

        # Guard: detect JSON arrays
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    texts = [normalize_response(item) for item in parsed if item]
                    return ". ".join(texts) if texts else "Done."
            except (json.JSONDecodeError, ValueError):
                pass

        return text

    # Dict output from executor/handler
    if isinstance(result, dict):
        return _extract_text_from_dict(result)

    # List output
    if isinstance(result, list):
        texts = [normalize_response(item) for item in result if item]
        return ". ".join(texts) if texts else "Done."

    return str(result)


def _extract_text_from_dict(d: dict) -> str:
    """
    Extract a human-readable string from a dict.
    Tries common text keys first, then falls back to a sentence.
    """
    # Try well-known text keys
    for key in ("text", "answer", "response", "message", "result", "output"):
        value = d.get(key)
        if value and isinstance(value, str) and value.strip():
            return value.strip()

    # If dict only has structured/internal keys, don't speak it
    if set(d.keys()).issubset(_STRUCTURED_KEYS):
        return "I processed your request."

    # Build a readable sentence from non-internal key-value pairs
    parts = []
    for k, v in d.items():
        if k in _STRUCTURED_KEYS:
            continue
        if v is not None and str(v).strip():
            parts.append(f"{k}: {v}")

    if parts:
        return ". ".join(parts)

    return "Done."


class JarvisBrain:
    """
    Main orchestrator for the JARVIS AI assistant.
    Coordinates face auth, speech, intent classification, and task execution.
    Implements self-control logic for incomplete commands.
    """

    def __init__(self):
        from core.speech import speak, listen
        from core.ai_router import get_router
        from core.memory import get_memory
        from security.auth import get_auth
        from modules.face_monitor_module import start_face_monitor, stop_face_monitor

        self.speak = speak
        self.listen = listen
        self.router = get_router()
        self.memory = get_memory()
        self.auth = get_auth()
        self.start_monitor = start_face_monitor
        self.stop_monitor = stop_face_monitor
        self._running = False
        self._pending_clarification = None  # For self-control logic

        logger.info("JARVIS Brain initialized (v2 — autonomous agent mode)")

    # ====================================================
    # FACE AUTHENTICATION
    # ====================================================

    def authenticate_user(self) -> bool:
        """
        Perform face authentication.
        Returns True if authenticated (or if auth is disabled).
        """
        from config import FACE_AUTH_ENABLED

        if not FACE_AUTH_ENABLED:
            logger.info("Face auth disabled — skipping")
            return True

        # Check existing session
        if self.auth.is_active:
            remaining = self.auth.session_remaining
            logger.info(
                f"Active session for {self.auth.current_user} "
                f"({remaining}s remaining)"
            )
            return True

        # Perform face recognition
        self.speak("Initiating face authentication. Please look at the camera.")

        # Stop monitor during active auth to avoid camera/classifier contention
        self.stop_monitor()
        time.sleep(0.5)  # Allow camera to release

        try:
            from face_recognition_module import authenticate
            result = authenticate()
        except Exception as e:
            logger.error(f"Face auth error: {e}")
            self.speak("Face recognition system error. Access denied.")
            self.start_monitor() # Resume monitor
            return False

        # Restart monitor
        self.start_monitor()

        if result.get("authenticated"):
            user = result["user"]
            confidence = result["confidence"]

            # Create session
            self.auth.create_session(user, confidence)
            self.memory.remember_name(user)

            self.speak(f"Welcome, {user}. Authentication successful.")
            logger.info(f"Authenticated: {user} (confidence={confidence})")
            return True
        else:
            reason = result.get("reason", "Unknown")
            logger.warning(f"Authentication failed: {reason}")
            
            self.speak(f"I couldn't recognize your face. Would you like to re-authenticate or register fresh?")
            choice = self.listen()
            
            if choice and ("register" in choice.lower() or "fresh" in choice.lower()):
                self.speak("Understood. Let's start a fresh registration. What is your name?")
                name = self.listen()
                if name:
                    # Clean existing data first to ensure "no cache issues"
                    try:
                        from reset_face_data import reset_all_face_data
                        reset_all_face_data()
                    except ImportError:
                        pass
                    
                    self.speak(f"Registering {name}. Please look at the camera.")
                    from face_recognition_module import live_register_face
                    if live_register_face(name):
                        self.speak(f"Perfect. You are now registered as {name}.")
                        return self.authenticate_user() # Try again now that registered
                return False
            
            elif choice and ("re-authenticate" in choice.lower() or "try again" in choice.lower() or "recognize" in choice.lower()):
                self.speak("Understood. Retrying recognition.")
                return self.authenticate_user()
            
            self.speak(f"Access denied. {reason}")
            return False


    # ====================================================
    # GREETING
    # ====================================================

    def greet(self):
        """Greet the user based on time of day. Only use name if authenticated."""
        hour = datetime.datetime.now().hour
        
        # Use authenticated name, or 'Guest' if not verified
        if self.auth.is_active:
            user = self.auth.current_user
        else:
            user = "Guest"

        if hour < 12:
            greeting = "Good morning"
        elif hour < 17:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"

        self.speak(f"{greeting}, {user}. How can I help you today?")

    # ====================================================
    # COMMAND PROCESSING (with self-control logic)
    # ====================================================

    def process_command(self, command: str) -> bool:
        """
        Process a single command through the AI pipeline.
        Returns False if Jarvis should exit.
        """
        if not command or not command.strip():
            return True

        # Log command
        self.auth.log_command(command)

        # 1. Handle special face/auth commands FIRST (they bypass session check)
        # This allows new users to say "register my face"
        if self._handle_face_commands(command):
            return True

        # 2. Check session validity for all other commands
        if not self.auth.is_active:
            from config import FACE_AUTH_ENABLED
            if FACE_AUTH_ENABLED:
                from face_recognition_module import is_trained
                if not is_trained():
                    self.speak("I don't have any faces registered yet. Please say 'register my face' to get started.")
                    return True

                self.speak("Session expired. Re-authenticating...")

                if not self.authenticate_user():
                    return True  # Don't exit, but don't execute

        # Handle pending clarification (self-control follow-up)
        if self._pending_clarification:
            return self._handle_clarification_response(command)

        # Handle memory commands
        if self._handle_memory_commands(command):
            return True

        # Route through AI pipeline
        result = self.router.process(command)

        # Handle clarification requests from router
        if isinstance(result, str) and result.startswith("__CLARIFY__:"):
            question = result[len("__CLARIFY__:"):]
            self._pending_clarification = {
                "original_command": command,
                "question": question,
                "timestamp": time.time(),
            }
            self.speak(question)
            return True

        if result == "__EXIT__":
            self.speak("Goodbye! Shutting down.")
            return False

        if result:
            # CRITICAL: always normalize before speaking — never speak raw JSON/dict
            clean_text = normalize_response(result)
            self.speak(clean_text)

        return True

    def _handle_clarification_response(self, response: str) -> bool:
        """
        Handle the user's response to a clarification question.
        Reconstructs the command with the missing information.
        """
        clarification = self._pending_clarification
        self._pending_clarification = None

        original = clarification["original_command"].lower()

        # Reconstruct the full command
        if "send message" in original or "message" in original:
            # User provided the contact name
            full_command = f"send whatsapp message to {response}"
            # If the original had a body, append it
            if " saying " in original:
                body = original.split(" saying ", 1)[1]
                full_command += f" saying {body}"
        elif "send email" in original or "email" in original:
            full_command = f"send email to {response}"
        elif original == "open":
            full_command = f"open {response}"
        elif original == "play":
            full_command = f"play {response}"
        elif original in ("search", "search for", "look up"):
            full_command = f"search for {response}"
        else:
            full_command = f"{original} {response}"

        logger.info(f"Clarification resolved: '{original}' + '{response}' → '{full_command}'")

        # Process the reconstructed command
        result = self.router.process(full_command)

        if result == "__EXIT__":
            self.speak("Goodbye! Shutting down.")
            return False

        if result:
            clean_text = normalize_response(result)
            self.speak(clean_text)

        return True

    def _handle_face_commands(self, command: str) -> bool:
        """Handle face-related voice commands."""
        cmd = command.lower()

        if any(phrase in cmd for phrase in ["who am i", "recognize me", "identify me"]):
            self.speak("Let me take a look.")
            try:
                from face_recognition_module import capture_and_identify
                results = capture_and_identify()
                if results and results[0].get("name") != "Unknown":
                    name = results[0]["name"]
                    conf = int(results[0]["confidence"] * 100)
                    self.speak(f"I see {name} with {conf} percent confidence.")
                else:
                    self.speak("I see someone, but I don't recognize them.")
            except Exception as e:
                self.speak("Face recognition failed.")
                logger.error(f"Face command error: {e}")
            return True

        if "register" in cmd and ("face" in cmd or "my face" in cmd):
            self.speak("What name should I register?")
            name = self.listen()
            if not name:
                self.speak("No name received.")
                return True

            self.speak(f"Starting registration for {name}. Please look at the camera for a few seconds.")
            try:
                from face_recognition_module import live_register_face
                if live_register_face(name):
                    self.speak(f"Success! I have registered your face as {name} and updated my memory. You can now use the system.")
                else:
                    self.speak("Registration failed. Please ensure you are in a well lit area and try again.")
            except Exception as e:
                self.speak("An error occurred during registration.")
                logger.error(f"Registration error: {e}")
            return True

        if "live face" in cmd or "start recognition" in cmd:
            self.speak("Starting live face recognition. Press Q to stop.")
            try:
                from face_recognition_module import recognize_from_webcam
                recognize_from_webcam(show_video=True)
                self.speak("Stopped live recognition.")
            except Exception as e:
                self.speak("Live recognition failed.")
                logger.error(f"Live recognition error: {e}")
            return True

        return False

    def _handle_memory_commands(self, command: str) -> bool:
        """Handle memory-related commands."""
        cmd = command.lower()

        if "remember that" in cmd or "remember this" in cmd:
            self.speak("What should I remember?")
            fact = self.listen()
            if fact:
                self.memory.remember_fact(fact)
                self.speak(f"I'll remember: {fact}")
            else:
                self.speak("I didn't catch that.")
            return True

        if "do you remember" in cmd or "what do you remember" in cmd:
            facts = self.memory.recall_facts()
            if facts:
                self.speak(f"I remember {len(facts)} things.")
                for f in facts[-3:]:  # Last 3
                    self.speak(f["fact"])
            else:
                self.speak("I don't have anything stored in memory yet.")
            return True

        # "save contact X phone Y"
        if "save contact" in cmd or "add contact" in cmd:
            self.speak("What's the contact name?")
            name = self.listen()
            if not name:
                self.speak("I didn't catch the name.")
                return True
            self.speak("What's their phone number?")
            phone = self.listen()
            if phone:
                # Clean up phone number
                phone_clean = phone.replace(" ", "").replace("-", "")
                self.memory.remember_contact(name, phone=phone_clean)
                self.speak(f"Contact saved: {name}")
            else:
                self.speak("I didn't catch the number.")
            return True

        # "list contacts"
        if "list contacts" in cmd or "show contacts" in cmd or "my contacts" in cmd:
            contacts = self.memory.list_contacts()
            if contacts:
                self.speak(f"You have {len(contacts)} contacts: {', '.join(contacts)}")
            else:
                self.speak("You don't have any saved contacts yet.")
            return True

        return False

    # ====================================================
    # DAEMON MODE
    # ====================================================

    def run_daemon(self):
        """
        Run Jarvis as a continuous daemon.
        Listens for commands in a loop with wake word support.
        """
        self._running = True
        logger.info("JARVIS daemon started")

        # Start continuous monitoring
        logger.info("Starting continuous biometric monitoring...")
        self.start_monitor()

        # Initial Authentication/Validation
        from face_recognition_module import is_trained
        if is_trained():
            logger.info("Face model found. Validating user...")
            if not self.authenticate_user():
                logger.warning("Initial validation failed.")
                # self.authenticate_user already handles the 'register or retry' prompt
        else:
            logger.info("No face data found. Prompting for registration.")
            self.speak("System initialized. I don't have any faces registered yet. Would you like to register now?")
            choice = self.listen()
            if choice and ("yes" in choice.lower() or "register" in choice.lower()):
                self._handle_face_commands("register my face")
            else:
                self.speak("Proceeding in Guest mode. Security restricted.")

        # Greet (now uses self.auth.is_active inside)
        self.greet()

        # Main loop
        while self._running:
            try:
                command = self.listen()

                if not command:
                    continue

                # Wake word check (optional — if wake word enabled)
                from config import WAKE_WORD
                if WAKE_WORD and not command.startswith(WAKE_WORD):
                    # Check if command contains wake word
                    if WAKE_WORD in command:
                        # Strip wake word
                        command = command.replace(WAKE_WORD, "").strip()
                    else:
                        # No wake word — still process (more natural)
                        pass

                # Process command
                should_continue = self.process_command(command)
                if not should_continue:
                    self._running = False
                    break

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                self.speak("Shutting down. Goodbye!")
                self._running = False
                break

            except Exception as e:
                logger.error(f"Daemon loop error: {e}")
                continue

        # Stop monitoring on exit
        self.stop_monitor()
        logger.info("JARVIS daemon stopped")


    def stop(self):
        """Stop the daemon."""
        self._running = False
        self.stop_monitor()
        logger.info("Stop signal received")
