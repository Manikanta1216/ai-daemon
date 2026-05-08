"""
JARVIS AI — Central Configuration
Loads all settings from .env file with sensible defaults.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Manual fallback if python-dotenv is missing
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

# ============================================
# PATHS
# ============================================
PROJECT_ROOT = Path(__file__).parent.resolve()
FACE_RECOGNITION_DIR = PROJECT_ROOT / "Face Recognition"
TRAINER_PATH = FACE_RECOGNITION_DIR / "trainer" / "trainer.yml"
CASCADE_PATH = FACE_RECOGNITION_DIR / "haarcascade_frontalface_default.xml"
REGISTERED_FACES_DIR = PROJECT_ROOT / "registered_faces"
INTRUDERS_DIR = PROJECT_ROOT / "intruders"
MEMORY_DIR = PROJECT_ROOT / "memory"

# Ensure required directories exist
for d in [REGISTERED_FACES_DIR, INTRUDERS_DIR, MEMORY_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================
# LLM CONFIGURATION
# ============================================
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ============================================
# FACE AUTHENTICATION
# ============================================
FACE_CONFIDENCE_THRESHOLD = int(os.getenv("FACE_CONFIDENCE_THRESHOLD", "65"))
FACE_SESSION_DURATION_MINUTES = int(os.getenv("FACE_SESSION_DURATION_MINUTES", "5"))
FACE_AUTH_ENABLED = os.getenv("FACE_AUTH_ENABLED", "true").lower() == "true"

# ============================================
# USER INFO
# ============================================
USER_NAME = os.getenv("USER_NAME", "User")
USER_CITY = os.getenv("USER_CITY", "Hyderabad")

# ============================================
# EMAIL
# ============================================
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# ============================================
# SPEECH
# ============================================
TTS_RATE = int(os.getenv("TTS_RATE", "170"))
TTS_VOLUME = float(os.getenv("TTS_VOLUME", "1.0"))
LISTEN_TIMEOUT = int(os.getenv("LISTEN_TIMEOUT", "5"))
LISTEN_PHRASE_LIMIT = int(os.getenv("LISTEN_PHRASE_LIMIT", "15"))
# TTS_ENGINE: "auto" (try pyttsx3 → SAPI fallback), "sapi" (Windows built-in), "pyttsx3"
TTS_ENGINE = os.getenv("TTS_ENGINE", "auto")

# ============================================
# WAKE WORD
# ============================================
WAKE_WORD = os.getenv("WAKE_WORD", "jarvis").lower()

# ============================================
# SECURITY
# ============================================
REQUIRE_CONFIRMATION_FOR_DANGEROUS = os.getenv(
    "REQUIRE_CONFIRMATION_FOR_DANGEROUS", "false"
).lower() == "true"
LOG_ALL_COMMANDS = os.getenv("LOG_ALL_COMMANDS", "true").lower() == "true"

# Dangerous command keywords that require confirmation
DANGEROUS_KEYWORDS = [
    "delete", "remove", "format", "shutdown", "restart",
    "kill", "erase", "destroy", "wipe", "uninstall"
]
