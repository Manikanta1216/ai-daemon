"""
JARVIS AI — Security: Face Auth Session Manager
Manages authentication sessions with time-based expiry.
"""

import logging
import time
import uuid

logger = logging.getLogger("jarvis.security")


class AuthSession:
    """
    Manages face authentication sessions.
    Once authenticated, creates a session token valid for N minutes.
    """

    def __init__(self):
        from config import FACE_SESSION_DURATION_MINUTES
        self.session_duration = FACE_SESSION_DURATION_MINUTES * 60  # seconds
        self._session_token = None
        self._session_user = None
        self._session_start = 0
        self._command_history = []  # All commands logged

    @property
    def is_active(self) -> bool:
        """Check if current session is still valid."""
        if self._session_token is None:
            return False
        elapsed = time.time() - self._session_start
        if elapsed > self.session_duration:
            logger.info("Session expired")
            self._session_token = None
            self._session_user = None
            return False
        return True

    @property
    def current_user(self) -> str:
        """Get the currently authenticated user."""
        return self._session_user if self.is_active else None

    @property
    def session_remaining(self) -> int:
        """Seconds remaining in current session."""
        if not self.is_active:
            return 0
        return max(0, int(self.session_duration - (time.time() - self._session_start)))

    def create_session(self, user: str, confidence: float) -> dict:
        """
        Create a new auth session after successful face recognition.

        Returns session info dict.
        """
        self._session_token = str(uuid.uuid4())
        self._session_user = user
        self._session_start = time.time()

        session_info = {
            "token": self._session_token,
            "user": user,
            "confidence": confidence,
            "expires_in": self.session_duration,
            "created_at": self._session_start,
        }

        logger.info(
            f"Session created for {user} "
            f"(confidence={confidence:.1f}, expires={self.session_duration}s)"
        )

        return session_info

    def invalidate(self):
        """Invalidate the current session."""
        if self._session_user:
            logger.info(f"Session invalidated for {self._session_user}")
        self._session_token = None
        self._session_user = None
        self._session_start = 0

    def log_command(self, command: str, intent: str = None):
        """Log a command to history."""
        entry = {
            "command": command,
            "intent": intent,
            "user": self._session_user,
            "timestamp": time.time(),
        }
        self._command_history.append(entry)

        from config import LOG_ALL_COMMANDS
        if LOG_ALL_COMMANDS:
            logger.info(f"CMD [{self._session_user}]: {command}")

    def get_command_history(self, n: int = 20) -> list:
        """Get the last N commands."""
        return self._command_history[-n:]

    def is_dangerous_command(self, command: str) -> bool:
        """Check if a command contains dangerous keywords."""
        from config import DANGEROUS_KEYWORDS
        command_lower = command.lower()
        return any(kw in command_lower for kw in DANGEROUS_KEYWORDS)


# ============================================
# SINGLETON
# ============================================
_auth = None


def get_auth() -> AuthSession:
    """Get or create global auth session."""
    global _auth
    if _auth is None:
        _auth = AuthSession()
    return _auth
