import threading
import cv2
import logging
import random
import time
import numpy as np

from face_recognition_module import (
    _get_recognizer,
    USER_NAMES,
    _draw_hud
)

from core.memory import get_memory

logger = logging.getLogger("jarvis.modules.face_monitor")

# Global control variables
_monitor_thread = None
_monitor_stop_event = threading.Event()


def _monitor_loop():
    """
    Continuously capture webcam frames,
    display futuristic HUD,
    and safely monitor faces in real time.
    """

    try:
        recognizer, face_cascade = _get_recognizer()

    except Exception as e:
        logger.error(
            f"Live face monitor: Could not initialize recognizer: {e}"
        )
        return

    # ─────────────────────────────────────
    # CAMERA INIT
    # ─────────────────────────────────────
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        logger.error("Live face monitor: Camera not accessible")
        return

    # Stable camera settings
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    # Warmup camera
    logger.info("Face monitor camera warmup...")

    for _ in range(60):
        cap.read()
        time.sleep(0.03)

    logger.info("Face monitor warmup complete")

    # ─────────────────────────────────────
    # WINDOW SETUP
    # ─────────────────────────────────────
    window_name = "JARVIS MONITOR"

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 320, 480)
    cv2.moveWindow(window_name, 10, 10)

    memory = get_memory()

    # ─────────────────────────────────────
    # MAIN LOOP
    # ─────────────────────────────────────
    while not _monitor_stop_event.is_set():

        try:
            ret, frame = cap.read()

            if not ret or frame is None:
                continue

            if frame.size == 0:
                continue

            # Resize for performance
            small_frame = cv2.resize(frame, (320, 240))

            # Convert safely
            gray = cv2.cvtColor(
                small_frame,
                cv2.COLOR_BGR2GRAY
            )

            if gray is None or gray.size == 0:
                continue

            # Normalize lighting
            gray = cv2.equalizeHist(gray)

            # ─────────────────────────────
            # SAFE FACE DETECTION
            # ─────────────────────────────
            faces = []

            try:

                h, w = gray.shape[:2]

                if h >= 50 and w >= 50:

                    faces = face_cascade.detectMultiScale(
                        gray,
                        scaleFactor=1.1,
                        minNeighbors=5,
                        minSize=(50, 50)
                    )

            except cv2.error as e:

                logger.warning(
                    f"Face monitor detection crash avoided: {e}"
                )

                continue

            # ─────────────────────────────
            # FACE RECOGNITION
            # ─────────────────────────────
            best_name = None
            current_status = "MONITORING"

            if len(faces) > 0:

                largest = max(
                    faces,
                    key=lambda f: f[2] * f[3]
                )

                x, y, w, h = largest

                roi = gray[y:y + h, x:x + w]

                try:

                    if roi is not None and roi.size > 0:

                        user_id, conf = recognizer.predict(roi)

                        if conf < 65:

                            best_name = USER_NAMES.get(
                                user_id,
                                f"User_{user_id}"
                            )

                            current_status = "RECOGNIZED"

                        else:

                            best_name = "UNKNOWN"
                            current_status = "ANALYZING"

                except Exception as e:

                    logger.warning(
                        f"Recognition error: {e}"
                    )

            # ─────────────────────────────
            # HUD RENDERING
            # ─────────────────────────────
            last_command = (
                memory.get_last_context("last_command")
                or "Listening..."
            )

            hud_frame = _draw_hud(
                small_frame.copy(),
                faces,
                current_status,
                1.0,
                best_name
            )

            h, w = hud_frame.shape[:2]

            # Expression simulation
            expressions = [
                "NEUTRAL",
                "ENGAGED",
                "FOCUSED",
                "CALM"
            ]

            exp = (
                expressions[int(time.time() % 4)]
                if len(faces) > 0
                else "ABSENT"
            )

            # Status text
            cv2.putText(
                hud_frame,
                f"EXP: {exp}",
                (10, h - 45),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (0, 255, 255),
                1
            )

            cmd_display = last_command[:20]

            if len(last_command) > 20:
                cmd_display += "..."

            cv2.putText(
                hud_frame,
                f"CMD: {cmd_display}",
                (10, h - 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (255, 255, 255),
                1
            )

            # Pulsing LIVE indicator
            pulse_color = (
                (0, 0, 255)
                if int(time.time() * 2) % 2 == 0
                else (0, 0, 150)
            )

            cv2.circle(
                hud_frame,
                (w - 20, h - 35),
                3,
                pulse_color,
                -1
            )

            cv2.putText(
                hud_frame,
                "LIVE",
                (w - 45, h - 33),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.3,
                (255, 255, 255),
                1
            )

            # ─────────────────────────────
            # SHOW WINDOW
            # ─────────────────────────────
            cv2.imshow(window_name, hud_frame)

            if cv2.waitKey(30) & 0xFF == ord('q'):
                break

        except Exception as e:

            logger.error(
                f"Monitor loop error: {e}"
            )

            time.sleep(0.1)

    # ─────────────────────────────────────
    # CLEANUP
    # ─────────────────────────────────────
    cap.release()

    try:
        cv2.destroyWindow(window_name)
    except:
        pass

    logger.info("Live face monitor stopped")


def start_face_monitor() -> str:
    """
    Start monitor thread.
    """

    global _monitor_thread
    global _monitor_stop_event

    if _monitor_thread and _monitor_thread.is_alive():

        return (
            "Live face monitor is already running."
        )

    _monitor_stop_event.clear()

    _monitor_thread = threading.Thread(
        target=_monitor_loop,
        daemon=True
    )

    _monitor_thread.start()

    logger.info("Live face monitor started")

    return (
        "Live face monitor started on the left side "
        "of the screen."
    )


def stop_face_monitor() -> str:
    """
    Stop monitor thread.
    """

    global _monitor_stop_event

    if not _monitor_thread:

        return (
            "Live face monitor is not running."
        )

    _monitor_stop_event.set()

    return "Stopping live face monitor..."
# import threading
# import cv2
# import logging
# import random
# import time
# from face_recognition_module import _get_recognizer, USER_NAMES, _draw_hud
# from core.memory import get_memory

# logger = logging.getLogger("jarvis.modules.face_monitor")

# # Global control variables
# _monitor_thread = None
# _monitor_stop_event = threading.Event()

# def _monitor_loop():
#     """Continuously capture webcam frames, display a left‑side overlay,
#     and highlight the best‑match face with expression and speech monitoring.
#     """
#     try:
#         recognizer, face_cascade = _get_recognizer()
#     except Exception as e:
#         logger.error(f"Live face monitor: Could not initialize recognizer: {e}")
#         return

#     cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
#     if not cap.isOpened():
#         cap = cv2.VideoCapture(0)
        
#     if not cap.isOpened():
#         logger.error("Live face monitor: Camera not accessible")
#         return

#     window_name = "JARVIS MONITOR"
#     cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
#     cv2.resizeWindow(window_name, 320, 480) # Taller for more info
#     cv2.moveWindow(window_name, 10, 10)  # Left side
    
#     memory = get_memory()
    
#     while not _monitor_stop_event.is_set():
#         ret, frame = cap.read()
#         if not ret:
#             continue
        
#         # Performance: Resize for faster processing in monitor
#         small_frame = cv2.resize(frame, (320, 240))
#         gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
#         # faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5)
        
        
#         best_name = None
#         current_status = "MONITORING"
        
#         if len(faces) > 0:
#             # Predict only for the largest face
#             largest = max(faces, key=lambda f: f[2] * f[3])
#             x, y, w, h = largest
#             roi = gray[y:y + h, x:x + w]
#             try:
#                 user_id, conf = recognizer.predict(roi)
#                 if conf < 65: # Threshold from module
#                     best_name = USER_NAMES.get(user_id, f"User_{user_id}")
#                     current_status = "RECOGNIZED"
#                 else:
#                     best_name = "UNKNOWN"
#                     current_status = "ANALYZING"
#             except:
#                 pass

#         # ── HUD ENHANCEMENTS (REMASTERED) ──
#         # Get last heard speech
#         last_command = memory.get_last_context("last_command") or "Listening..."
        
#         # Draw the remastered HUD
#         hud_frame = _draw_hud(small_frame.copy(), faces, current_status, 1.0, best_name)
        
#         # ── MONITOR DATA OVERLAY (NON-OBTRUSIVE) ──
#         h, w = hud_frame.shape[:2]
        
#         # Expression & Speech (Thin floating tags)
#         expressions = ["NEUTRAL", "ENGAGED", "FOCUSED", "CALM"]
#         exp = expressions[int(time.time() % 4)] if len(faces) > 0 else "ABSENT"
        
#         # Overlay data in corners to avoid face obstruction
#         cv2.putText(hud_frame, f"EXP: {exp}", (10, h - 45), 
#                     cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)
#         cv2.putText(hud_frame, f"CMD: {last_command[:20]}...", (10, h - 35), 
#                     cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
        
#         # Vitals (Small pulsing dot)
#         v_col = (0, 0, 255) if int(time.time()*2)%2 == 0 else (0, 0, 150)
#         cv2.circle(hud_frame, (w - 20, h - 35), 3, v_col, -1)
#         cv2.putText(hud_frame, "LIVE", (w - 45, h - 33), 
#                     cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)

#         cv2.imshow(window_name, hud_frame)
        
#         if cv2.waitKey(30) & 0xFF == ord('q'):
#             break
            
#     cap.release()
#     cv2.destroyWindow(window_name)
#     logger.info("Live face monitor stopped")

# def start_face_monitor() -> str:
#     """Start the live face monitor in a background daemon thread."""
#     global _monitor_thread, _monitor_stop_event
#     if _monitor_thread and _monitor_thread.is_alive():
#         return "Live face monitor is already running."
#     _monitor_stop_event.clear()
#     _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
#     _monitor_thread.start()
#     logger.info("Live face monitor started")
#     return "Live face monitor started on the left side of the screen."

# def stop_face_monitor() -> str:
#     """Signal the monitor thread to stop and wait for termination."""
#     global _monitor_stop_event
#     if not _monitor_thread:
#         return "Live face monitor is not running."
#     _monitor_stop_event.set()
#     return "Stopping live face monitor..."
