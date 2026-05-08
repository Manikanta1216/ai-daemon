"""
JARVIS AI — Speech Engine (v3 — Multi-Backend)
Handles Text-to-Speech (TTS) and Speech-to-Text (STT).

Supports multiple TTS backends:
  1. pyttsx3 (default)
  2. Windows SAPI via PowerShell (fallback — always works on Windows)

If pyttsx3 produces no audio (known Windows bug), set TTS_ENGINE=sapi in .env
"""

import logging
import os
import subprocess
import threading
import time

logger = logging.getLogger("jarvis.speech")

# ============================================
# TTS BACKEND SELECTION
# ============================================
# Set TTS_ENGINE=sapi in .env to force Windows SAPI
# Set TTS_ENGINE=pyttsx3 to force pyttsx3
# Default: tries pyttsx3 first, auto-falls back to SAPI on failure
_TTS_ENGINE = os.getenv("TTS_ENGINE", "auto").lower()

_tts_lock = threading.Lock()
_pyttsx3_engine = None
_pyttsx3_broken = False  # Set True if pyttsx3 fails at runtime
_engine_call_count = 0


# ============================================
# PYTTSX3 BACKEND
# ============================================

def _pyttsx3_speak(text: str) -> bool:
    """Try speaking with pyttsx3. Returns True on success."""
    global _pyttsx3_engine, _pyttsx3_broken, _engine_call_count

    if _pyttsx3_broken:
        return False

    try:
        import pyttsx3
    except ImportError:
        logger.warning("pyttsx3 not installed")
        _pyttsx3_broken = True
        return False

    for attempt in range(2):
        try:
            # Recreate engine periodically or on first use
            if _pyttsx3_engine is None or _engine_call_count >= 15:
                if _pyttsx3_engine is not None:
                    try:
                        _pyttsx3_engine.stop()
                    except Exception:
                        pass
                _pyttsx3_engine = pyttsx3.init()
                from config import TTS_RATE, TTS_VOLUME
                _pyttsx3_engine.setProperty("rate", TTS_RATE)
                _pyttsx3_engine.setProperty("volume", TTS_VOLUME)
                voices = _pyttsx3_engine.getProperty("voices")
                if voices:
                    _pyttsx3_engine.setProperty("voice", voices[0].id)
                _engine_call_count = 0

            _pyttsx3_engine.say(text)
            _pyttsx3_engine.runAndWait()
            _engine_call_count += 1
            return True

        except RuntimeError as e:
            logger.warning(f"pyttsx3 RuntimeError (attempt {attempt + 1}): {e}")
            _pyttsx3_engine = None
        except Exception as e:
            logger.warning(f"pyttsx3 error (attempt {attempt + 1}): {type(e).__name__}: {e}")
            _pyttsx3_engine = None
            time.sleep(0.2)

    # Both attempts failed — mark as broken for this session
    logger.error("pyttsx3 failed — switching to SAPI fallback")
    _pyttsx3_broken = True
    return False


# ============================================
# WINDOWS SAPI BACKEND (PowerShell — always available)
# ============================================

def _sapi_speak(text: str) -> bool:
    """Speak using Windows SAPI via win32com (direct COM interface)."""
    try:
        import win32com.client
        from config import TTS_RATE
        
        # SAPI voice object
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        
        # SAPI rate is -10 to 10. Default (0) is normal.
        # pyttsx3 170 -> sapi ~0 or 1
        sapi_rate = max(-10, min(10, (TTS_RATE - 170) // 10))
        speaker.Rate = sapi_rate
        speaker.Volume = 100
        
        # Speak synchronously
        speaker.Speak(text)
        return True
    except Exception as e:
        logger.error(f"win32com SAPI error: {e}")
        # Final fallback to PowerShell if win32com fails
        return _powershell_speak(text)


def _powershell_speak(text: str) -> bool:
    """Fallback: Speak using Windows SAPI via PowerShell script."""
    try:
        from config import TTS_RATE
        sapi_rate = max(-10, min(10, (TTS_RATE - 150) // 20))
        
        # Escape text for PowerShell
        safe_text = text.replace("'", "''").replace("\n", " ").replace("\r", " ")
        
        import tempfile
        script_path = os.path.join(tempfile.gettempdir(), "_jarvis_speak.ps1")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write("Add-Type -AssemblyName System.Speech\n")
            f.write("$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer\n")
            f.write(f"$synth.Rate = {sapi_rate}\n")
            f.write("$synth.Volume = 100\n")
            f.write(f"$synth.Speak('{safe_text}')\n")

        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path],
            capture_output=True, text=True, timeout=30
        )
        return True
    except Exception:
        return False
    finally:
        if 'script_path' in locals() and os.path.exists(script_path):
            try: os.remove(script_path)
            except: pass


# ============================================
# MAIN SPEAK FUNCTION
# ============================================

def speak(text: str) -> None:
    """
    Speak text aloud using the best available TTS engine.

    Priority:
      - TTS_ENGINE=pyttsx3 → only pyttsx3
      - TTS_ENGINE=sapi    → only Windows SAPI
      - TTS_ENGINE=auto    → pyttsx3 first, SAPI fallback

    GUARANTEES:
      - Text is ALWAYS printed to console
      - Raw JSON/dict is blocked from TTS
    """
    text = str(text).strip()

    # Final safety net: detect and block raw JSON/dict from being spoken
    if text.startswith("{") and text.endswith("}"):
        try:
            import json
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                for key in ("text", "answer", "response", "message", "result"):
                    if key in parsed and parsed[key]:
                        text = str(parsed[key]).strip()
                        break
                else:
                    text = "Done."
        except (json.JSONDecodeError, ValueError):
            pass

    if not text:
        return

    # ALWAYS print to console — guaranteed output
    logger.info(f"[SPEAK] {text}")
    print(f"[Jarvis] {text}")

    # Speak using the configured backend
    with _tts_lock:
        if _TTS_ENGINE == "sapi":
            # Force SAPI
            if not _sapi_speak(text):
                logger.error(f"SAPI failed for: {text[:80]}")

        elif _TTS_ENGINE == "pyttsx3":
            # Force pyttsx3
            if not _pyttsx3_speak(text):
                logger.error(f"pyttsx3 failed for: {text[:80]}")

        else:
            # Auto mode: try pyttsx3, fall back to SAPI
            if not _pyttsx3_speak(text):
                logger.info("Falling back to SAPI")
                if not _sapi_speak(text):
                    logger.error(f"ALL TTS backends failed for: {text[:80]}")


# ============================================
# LISTEN (Speech-to-Text)
# ============================================

def listen(prompt: str = None) -> str:
    """
    Listen for voice input via microphone.
    Returns lowercase text or empty string on failure.
    """
    import speech_recognition as sr
    from config import LISTEN_TIMEOUT, LISTEN_PHRASE_LIMIT

    if prompt:
        speak(prompt)

    recognizer = sr.Recognizer()

    try:
        with sr.Microphone() as source:
            logger.debug("Listening...")
            print("[Jarvis] Listening...")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(
                source,
                timeout=LISTEN_TIMEOUT,
                phrase_time_limit=LISTEN_PHRASE_LIMIT,
            )
            command = recognizer.recognize_google(audio).lower().strip()
            logger.info(f"[HEARD] {command}")
            print(f"[Jarvis] Heard: {command}")
            return command

    except sr.WaitTimeoutError:
        logger.debug("Listen timeout")
        return ""
    except sr.UnknownValueError:
        logger.debug("Could not understand audio")
        return ""
    except sr.RequestError as e:
        logger.error(f"Speech recognition API error: {e}")
        return ""
    except Exception as e:
        logger.error(f"Microphone error: {e}")
        return ""
