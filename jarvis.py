"""
╔══════════════════════════════════════════════════════╗
║              J.A.R.V.I.S  AI  DAEMON                ║
║    Just A Rather Very Intelligent System             ║
║                                                      ║
║    Autonomous AI Desktop Assistant                   ║
║    Face-Authenticated | LLM-Powered | Modular        ║
╚══════════════════════════════════════════════════════╝

Entry point for the JARVIS AI assistant.
Initializes logging, loads config, and starts the brain daemon.

Usage:
    python jarvis.py                  # Normal mode (face auth + voice)
    python jarvis.py --no-auth        # Skip face authentication
    python jarvis.py --text           # Text input mode (no microphone)
    python jarvis.py --text --no-auth # Text mode without auth
"""

import argparse
import logging
import os
import sys

# Load configuration and environment variables early
import config

# ============================================
# LOGGING SETUP
# ============================================
def setup_logging():
    """Configure logging for the application."""
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "jarvis.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Reduce noise from libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)


# ============================================
# TEXT MODE (for testing without microphone)
# ============================================
def run_text_mode(skip_auth: bool = False):
    """Run JARVIS in text-input mode."""
    from core.brain import JarvisBrain

    logger = logging.getLogger("jarvis")
    logger.info("Starting JARVIS in TEXT mode")

    brain = JarvisBrain()

    # Authentication
    if not skip_auth:
        if not brain.authenticate_user():
            print("[Jarvis] Authentication failed. Running in limited mode.")
    else:
        print("[Jarvis] Face auth skipped.")

    brain.greet()

    print("\n" + "=" * 50)
    print("  JARVIS TEXT MODE — Type commands below")
    print("  Type 'exit' or 'bye' to quit")
    print("=" * 50 + "\n")

    while True:
        try:
            command = input("You: ").strip()
            if not command:
                continue

            should_continue = brain.process_command(command)
            if not should_continue:
                break

        except KeyboardInterrupt:
            brain.speak("Goodbye!")
            break
        except EOFError:
            break


# ============================================
# MAIN
# ============================================
def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="JARVIS AI — Autonomous Desktop Assistant"
    )
    parser.add_argument(
        "--no-auth",
        action="store_true",
        help="Skip face authentication",
    )
    parser.add_argument(
        "--text",
        action="store_true",
        help="Use text input instead of voice",
    )
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger("jarvis")

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║           J.A.R.V.I.S  AI  SYSTEM               ║")
    print("║     Just A Rather Very Intelligent System        ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    # Override face auth if requested
    if args.no_auth:
        os.environ["FACE_AUTH_ENABLED"] = "false"
        logger.info("Face authentication disabled via CLI flag")

    if args.text:
        run_text_mode(skip_auth=args.no_auth)
    else:
        # Normal voice mode
        from core.brain import JarvisBrain
        brain = JarvisBrain()
        brain.run_daemon()


if __name__ == "__main__":
    main()