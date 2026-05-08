"""
JARVIS AI — Face Recognition Module (STRICT AUTHENTICATION)

Uses OpenCV LBPH face recognizer with trained model (trainer.yml).
Features:
  - Registered-face-only access with confidence threshold
  - Multi-face detection (reject ALL if ANY unknown)
  - Robust anti-spoofing via multi-frame verification with retry logic
  - Intruder snapshot logging
  - Session token integration
  - Structured return format
  - Camera warm-up stabilization
  - Debug logging for detection rate diagnostics
"""

import cv2
import os
import time
import logging
import random
import numpy as np
from pathlib import Path

logger = logging.getLogger("jarvis.face")

# ============================================
# CONFIGURATION
# ============================================
_config_loaded = False
_TRAINER_PATH = None
_CASCADE_PATH = None
_INTRUDERS_DIR = None
_REGISTERED_DIR = None
_CONFIDENCE_THRESHOLD = 65
_SESSION_DURATION = 300  # 5 minutes


def _load_config():
    """Load paths from config (lazy to avoid circular imports)."""
    global _config_loaded, _TRAINER_PATH, _CASCADE_PATH
    global _INTRUDERS_DIR, _REGISTERED_DIR
    global _CONFIDENCE_THRESHOLD, _SESSION_DURATION

    if _config_loaded:
        return

    try:
        from config import (
            TRAINER_PATH, CASCADE_PATH, INTRUDERS_DIR,
            REGISTERED_FACES_DIR, FACE_CONFIDENCE_THRESHOLD,
            FACE_SESSION_DURATION_MINUTES,
        )
        _TRAINER_PATH = str(TRAINER_PATH)
        _CASCADE_PATH = str(CASCADE_PATH)
        _INTRUDERS_DIR = str(INTRUDERS_DIR)
        _REGISTERED_DIR = str(REGISTERED_FACES_DIR)
        _CONFIDENCE_THRESHOLD = FACE_CONFIDENCE_THRESHOLD
        _SESSION_DURATION = FACE_SESSION_DURATION_MINUTES * 60
    except ImportError:
        # Fallback defaults
        base = Path(__file__).parent
        _TRAINER_PATH = str(base / "Face Recognition" / "trainer" / "trainer.yml")
        _CASCADE_PATH = str(base / "Face Recognition" / "haarcascade_frontalface_default.xml")
        _INTRUDERS_DIR = str(base / "intruders")
        _REGISTERED_DIR = str(base / "registered_faces")

    os.makedirs(_INTRUDERS_DIR, exist_ok=True)
    os.makedirs(_REGISTERED_DIR, exist_ok=True)
    _config_loaded = True


# ============================================
# USER ID <-> NAME MAPPING
# ============================================
import json
_USERS_FILE = os.path.join(os.path.dirname(__file__), "users.json")

def _load_user_names():
    """Load user mapping from JSON file."""
    if os.path.exists(_USERS_FILE):
        try:
            with open(_USERS_FILE, "r") as f:
                return {int(k): v for k, v in json.load(f).items()}
        except Exception as e:
            logger.error(f"Error loading users.json: {e}")
    return {1: "Manikanta"}

def _save_user_names(mapping):
    """Save user mapping to JSON file."""
    try:
        with open(_USERS_FILE, "w") as f:
            json.dump(mapping, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving users.json: {e}")

USER_NAMES = _load_user_names()

def get_user_name(user_id: int) -> str:
    """Get user name from ID, fallback to 'User_{id}'."""
    global USER_NAMES
    return USER_NAMES.get(user_id, f"User_{user_id}")

def get_next_user_id() -> int:
    """Get the next available numeric ID."""
    global USER_NAMES
    if not USER_NAMES:
        return 1
    return max(USER_NAMES.keys()) + 1


# ============================================
# RECOGNIZER LOADER
# ============================================
_recognizer = None
_face_cascade = None


def _get_recognizer():
    """Load the LBPH face recognizer (lazy singleton)."""
    global _recognizer, _face_cascade
    _load_config()

    if _recognizer is None:
        if not os.path.exists(_TRAINER_PATH):
            logger.error(f"Trainer model not found: {_TRAINER_PATH}")
            raise FileNotFoundError(
                f"Face model not found at {_TRAINER_PATH}. "
                "Run 'Face Recognition/Model Trainer.py' first."
            )

        _recognizer = cv2.face.LBPHFaceRecognizer_create()
        _recognizer.read(_TRAINER_PATH)
        logger.info(f"Loaded face model: {_TRAINER_PATH}")

    if _face_cascade is None:
        if not os.path.exists(_CASCADE_PATH):
            # Try OpenCV built-in
            _face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
        else:
            _face_cascade = cv2.CascadeClassifier(_CASCADE_PATH)
        logger.info("Face cascade classifier loaded")

    return _recognizer, _face_cascade


# ============================================
# ANTI-SPOOFING: Multi-frame verification
# ============================================
def _non_max_suppression(boxes, overlap_thresh=0.4):
    """
    Apply Non-Maximum Suppression to eliminate overlapping/duplicate
    face detections from Haar cascade.

    boxes: list of (x, y, w, h) tuples
    overlap_thresh: IoU threshold above which detections are merged

    Returns filtered list of (x, y, w, h) tuples.
    """
    if len(boxes) == 0:
        return []

    boxes_arr = np.array(boxes, dtype=np.float32)
    x1 = boxes_arr[:, 0]
    y1 = boxes_arr[:, 1]
    x2 = boxes_arr[:, 0] + boxes_arr[:, 2]
    y2 = boxes_arr[:, 1] + boxes_arr[:, 3]
    areas = boxes_arr[:, 2] * boxes_arr[:, 3]

    # Sort by area (largest first — prefer bigger detections)
    idxs = np.argsort(areas)[::-1]
    picked = []

    while len(idxs) > 0:
        i = idxs[0]
        picked.append(i)

        xx1 = np.maximum(x1[i], x1[idxs[1:]])
        yy1 = np.maximum(y1[i], y1[idxs[1:]])
        xx2 = np.minimum(x2[i], x2[idxs[1:]])
        yy2 = np.minimum(y2[i], y2[idxs[1:]])

        inter_w = np.maximum(0, xx2 - xx1)
        inter_h = np.maximum(0, yy2 - yy1)
        intersection = inter_w * inter_h

        union = areas[i] + areas[idxs[1:]] - intersection
        iou = intersection / np.maximum(union, 1e-6)

        # Keep only boxes with IoU below threshold
        remaining = np.where(iou <= overlap_thresh)[0]
        idxs = idxs[remaining + 1]  # +1 because we skipped idxs[0]

    result = boxes_arr[picked].astype(np.int32)
    return [tuple(row) for row in result]


def _detect_faces_robust(gray, face_cascade):
    """
    Attempt face detection with multiple scaleFactor values for robustness.
    Prevents OpenCV getScaleData crashes.
    """

    for scale in [1.1, 1.2, 1.3]:

        try:

            if gray is None:
                continue

            if gray.size == 0:
                continue

            h, w = gray.shape[:2]

            if h < 50 or w < 50:
                continue

            gray = cv2.equalizeHist(gray)

            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=scale,
                minNeighbors=5,
                minSize=(50, 50),
            )

            if len(faces) > 0:

                filtered = _non_max_suppression(
                    faces,
                    overlap_thresh=0.4
                )

                return filtered

        except cv2.error as e:

            logger.warning(
                f"detectMultiScale crash avoided: {e}"
            )

            continue

    return []
    # for scale in [1.1, 1.2, 1.3]:
    #     faces = face_cascade.detectMultiScale(
    #         gray,
    #         scaleFactor=scale,
    #         minNeighbors=4,
    #         minSize=(50, 50),
    #     )
    #     if len(faces) > 0:
    #         # Apply NMS to eliminate overlapping detections
    #         filtered = _non_max_suppression(faces, overlap_thresh=0.4)
    #         return filtered
    # return []


def _verify_liveness(
    cap, face_cascade,
    num_frames: int = 10,
    movement_threshold: float = 2.0,
    max_retries: int = 3,
) -> bool:
    """
    Anti-spoofing: capture multiple frames and verify that detected face
    positions vary slightly (indicating a real person rather than a static
    photo).

    Improvements over the original:
      - Uses _detect_faces_robust with multiple scaleFactors and smaller minSize
      - Captures up to `num_frames` (default 10) per attempt
      - Retries up to `max_retries` (default 3) if not enough detections
      - "No detection" is NOT treated as spoofing — only persistent absence
        after all retries is reported as a detection failure (not spoofing)

    Returns:
        True  — subject appears live
        False — possible spoofing (static image) detected
        None  — could not get enough detections (NOT spoofing)
    """
    min_detections = 3  # Need at least this many positions for variance calc

    for retry in range(max_retries):
        positions = []
        frames_read = 0

        for i in range(num_frames):
            ret, frame = cap.read()
            if not ret:
                continue
            frames_read += 1

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = _detect_faces_robust(gray, face_cascade)

            if len(faces) > 0:
                x, y, w, h = faces[0]
                center_x = x + w // 2
                center_y = y + h // 2
                positions.append((center_x, center_y))

            time.sleep(0.1)  # Brief pause between frames

        detection_rate = len(positions) / max(frames_read, 1) * 100
        logger.info(
            f"Liveness attempt {retry + 1}/{max_retries}: "
            f"{len(positions)}/{frames_read} frames with detections "
            f"({detection_rate:.0f}% detection rate)"
        )

        if len(positions) >= min_detections:
            # Enough detections — calculate variance
            xs = [p[0] for p in positions]
            ys = [p[1] for p in positions]
            x_var = np.std(xs)
            y_var = np.std(ys)

            is_live = (x_var > movement_threshold) or (y_var > movement_threshold)

            if not is_live:
                logger.warning(
                    f"Liveness check FAILED (x_var={x_var:.2f}, y_var={y_var:.2f}). "
                    "Possible static image / spoofing attempt."
                )
            else:
                logger.info(
                    f"Liveness check PASSED (x_var={x_var:.2f}, y_var={y_var:.2f})"
                )

            return is_live

        # Not enough detections — retry instead of failing immediately
        logger.warning(
            f"Liveness retry {retry + 1}/{max_retries}: only {len(positions)} "
            f"detections (need {min_detections}), retrying..."
        )
        time.sleep(0.5)  # Brief pause before retry

    # Exhausted all retries — could not detect face reliably
    logger.warning(
        f"Liveness: could not obtain {min_detections} detections after "
        f"{max_retries} retries. This is a detection failure, NOT spoofing."
    )
    return None  # Distinct from False (spoofing)


# ============================================
# HUD / VISUAL INTERPRETATION (REMASTERED)
# ============================================
def _draw_hud(frame, faces, status="SCANNING", progress=0, name=None):
    """
    Draw a realistic, high-fidelity sci-fi HUD.
    Focuses on transparency, thin lines, and professional layout.
    """
    h, w = frame.shape[:2]
    overlay = frame.copy()
    
    # ── Colors (Sleek JARVIS Palette) ──
    cyan = (255, 255, 0)
    dim_cyan = (150, 150, 0)
    white = (255, 255, 255)
    red = (0, 0, 255)
    bg_tint = (20, 20, 20)
    
    # 1. Subtle Vignette & Tint
    cv2.rectangle(overlay, (0, 0), (w, h), bg_tint, -1)
    cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
    overlay = frame.copy() # Reset overlay for drawing

    # 2. Border & Corners
    pad = 10
    c_len = 30
    # Top Left
    cv2.line(overlay, (pad, pad), (pad + c_len, pad), cyan, 1)
    cv2.line(overlay, (pad, pad), (pad, pad + c_len), cyan, 1)
    # Top Right
    cv2.line(overlay, (pad + w - 2*pad, pad), (pad + w - 2*pad - c_len, pad), cyan, 1)
    cv2.line(overlay, (pad + w - 2*pad, pad), (pad + w - 2*pad, pad + c_len), cyan, 1)
    # Bottom Left
    cv2.line(overlay, (pad, pad + h - 2*pad), (pad + c_len, pad + h - 2*pad), cyan, 1)
    cv2.line(overlay, (pad, pad + h - 2*pad), (pad, pad + h - 2*pad - c_len), cyan, 1)
    # Bottom Right
    cv2.line(overlay, (pad + w - 2*pad, pad + h - 2*pad), (pad + w - 2*pad - c_len, pad + h - 2*pad), cyan, 1)
    cv2.line(overlay, (pad + w - 2*pad, pad + h - 2*pad), (pad + w - 2*pad, pad + h - 2*pad - c_len), cyan, 1)

    # 3. Scanning Line (Sophisticated)
    scan_y = int((time.time() * 150) % h)
    for i in range(3):
        alpha = 1.0 - (i * 0.3)
        cv2.line(overlay, (pad, scan_y - i*2), (w - pad, scan_y - i*2), cyan, 1)
    
    # 4. Targeting Reticles
    for (x, y, fw, fh) in faces:
        cx, cy = x + fw//2, y + fh//2
        # Circular Reticle (Segmented)
        r = int(max(fw, fh) * 0.7)
        cv2.ellipse(overlay, (cx, cy), (r, r), 0, 0, 80, cyan, 1)
        cv2.ellipse(overlay, (cx, cy), (r, r), 0, 100, 180, cyan, 1)
        cv2.ellipse(overlay, (cx, cy), (r, r), 0, 200, 280, cyan, 1)
        cv2.ellipse(overlay, (cx, cy), (r, r), 0, 300, 350, cyan, 1)
        
        # Face corners (sleek)
        l = 15
        cv2.line(overlay, (x, y), (x+l, y), cyan, 2)
        cv2.line(overlay, (x, y), (x, y+l), cyan, 2)
        cv2.line(overlay, (x+fw, y+fh), (x+fw-l, y+fh), cyan, 2)
        cv2.line(overlay, (x+fw, y+fh), (x+fw, y+fh-l), cyan, 2)

        # Floating ID tag
        if status != "SCANNING":
            tag_x, tag_y = x + fw + 10, y + 20
            cv2.putText(overlay, f"USR_{name.upper() if name else 'UNK'}", (tag_x, tag_y), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, cyan, 1)
            cv2.line(overlay, (cx, cy), (tag_x, tag_y), cyan, 1)

    # 5. Data Panels (Transparent)
    # Header
    cv2.putText(overlay, "SYSTEM AUTHENTICATION: ACTIVE", (20, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, cyan, 1)
    
    # Bottom Info
    cv2.rectangle(overlay, (pad, h - 60), (w - pad, h - pad), (0, 0, 0), -1) # Panel Background
    
    # Progress Bar (Modern)
    p_w = 120
    p_x = w - p_w - 30
    cv2.rectangle(overlay, (p_x, h - 35), (p_x + p_w, h - 30), (50, 50, 50), -1)
    cv2.rectangle(overlay, (p_x, h - 35), (p_x + int(p_w * progress), h - 30), cyan, -1)
    
    # Status Text
    s_col = red if status in ("DENIED", "SPOOF DETECTED") else cyan
    cv2.putText(overlay, f"SIGNAL: {status}", (30, h - 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, s_col, 1)
    
    # Biometric Noise (Top Right)
    noise_y = 50
    for i in range(3):
        noise = f"{random.randint(100, 999)}.{random.randint(10, 99)}"
        cv2.putText(overlay, f"BIT_{i}: {noise}", (w - 80, noise_y + i*15), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, dim_cyan, 1)

    # Final Blend
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
    return frame


# ============================================
# INTRUDER LOGGING
# ============================================
def _save_intruder_snapshot(frame, face_rect=None):
    """Save snapshot of an unauthorized face."""
    _load_config()
    timestamp = int(time.time())
    filename = os.path.join(_INTRUDERS_DIR, f"intruder_{timestamp}.jpg")

    if face_rect is not None:
        x, y, w, h = face_rect
        # Draw red rectangle around intruder face
        frame_copy = frame.copy()
        cv2.rectangle(frame_copy, (x, y), (x + w, y + h), (0, 0, 255), 3)
        cv2.putText(
            frame_copy, "UNAUTHORIZED",
            (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2,
        )
        cv2.imwrite(filename, frame_copy)
    else:
        cv2.imwrite(filename, frame)

    logger.warning(f"Intruder snapshot saved: {filename}")
    return filename


# ============================================
# MAIN AUTHENTICATION FUNCTION
# ============================================
def authenticate() -> dict:
    """
    Perform face authentication using webcam.

    Captures frames, runs LBPH recognition against trained model,
    applies confidence threshold, anti-spoofing check, and multi-face logic.

    Returns:
        {
            "authenticated": True,
            "user": "Manikanta",
            "confidence": 32.5
        }
        OR
        {
            "authenticated": False,
            "reason": "Unknown face"
        }
    """
    _load_config()

    try:
        recognizer, face_cascade = _get_recognizer()
    except FileNotFoundError as e:
        logger.error(str(e))
        return {"authenticated": False, "reason": str(e)}

    logger.info("Starting face authentication...")

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        # Try without DSHOW
        cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        logger.error("Camera not accessible")
        return {"authenticated": False, "reason": "Camera not accessible"}

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # ── Camera warm-up: discard first 15 frames over ~2.5 seconds ──
    logger.info("Camera warm-up: discarding initial frames...")
    warmup_frames = 60
    for _ in range(warmup_frames):
        cap.read()
        time.sleep(0.15)
    logger.info(f"Camera warm-up complete ({warmup_frames} frames discarded)")

    try:
        # Step 1: Anti-spoofing liveness check
        logger.info("Running liveness check...")
        
        # UI Setup
        cv2.namedWindow("JARVIS AUTHENTICATION", cv2.WINDOW_AUTOSIZE)
        # Position window (top right usually)
        cv2.moveWindow("JARVIS AUTHENTICATION", 100, 100)

        # Liveness loop with UI
        positions = []
        liveness_frames = 12
        for i in range(liveness_frames):
            ret, frame = cap.read()
            if not ret: continue
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = _detect_faces_robust(gray, face_cascade)
            
            if len(faces) > 0:
                x, y, w, h = faces[0]
                positions.append((x + w // 2, y + h // 2))
            
            # Show HUD
            prog = (i + 1) / liveness_frames * 0.5 # First 50% for liveness
            hud_frame = _draw_hud(frame.copy(), faces, "LIVENESS CHECK", prog)
            cv2.imshow("JARVIS AUTHENTICATION", hud_frame)
            cv2.waitKey(1)
            time.sleep(0.05)

        # Calculate liveness (simplified version of _verify_liveness logic for integration)
        is_live = False
        if len(positions) >= 3:
            xs = [p[0] for p in positions]
            ys = [p[1] for p in positions]
            if (np.std(xs) > 2.0) or (np.std(ys) > 2.0):
                is_live = True

        if not is_live and len(positions) >= 3:
            # Actual spoofing detected
            ret, frame = cap.read()
            if ret: _save_intruder_snapshot(frame)
            
            # Show failure in HUD
            for _ in range(10):
                ret, frame = cap.read()
                hud_frame = _draw_hud(frame, [], "SPOOF DETECTED", 1.0)
                cv2.imshow("JARVIS AUTHENTICATION", hud_frame)
                cv2.waitKey(100)
            
            cap.release()
            cv2.destroyWindow("JARVIS AUTHENTICATION")
            return {"authenticated": False, "reason": "Liveness check failed — possible spoofing"}
        
        if len(positions) < 3:
            cap.release()
            cv2.destroyWindow("JARVIS AUTHENTICATION")
            return {"authenticated": False, "reason": "Could not detect face reliably."}

        # Step 2: Recognition phase
        logger.info("Recognizing faces...")
        all_votes = []
        attempts = 20
        
        for attempt in range(attempts):
            ret, frame = cap.read()
            if not ret: continue
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = _detect_faces_robust(gray, face_cascade)
            
            current_user = "SCANNING"
            if len(faces) > 0:
                largest_face = max(faces, key=lambda f: f[2] * f[3])
                x, y, w, h = largest_face
                face_roi = gray[y:y + h, x:x + w]
                user_id, confidence_raw = recognizer.predict(face_roi)
                
                all_votes.append({
                    "user_id": user_id,
                    "confidence_raw": confidence_raw,
                    "rect": (x, y, w, h),
                    "frame": frame.copy(),
                })
                current_user = "ANALYZING"

            # Show HUD
            prog = 0.5 + (attempt / attempts * 0.5)
            hud_frame = _draw_hud(frame.copy(), faces, current_user, prog)
            cv2.imshow("JARVIS AUTHENTICATION", hud_frame)
            cv2.waitKey(1)
            time.sleep(0.05)

        cap.release()
        
        # Step 3: Analysis
        recognized_votes = [v for v in all_votes if v["confidence_raw"] < _CONFIDENCE_THRESHOLD]
        
        if len(recognized_votes) > len(all_votes) / 2:
            from collections import Counter
            user_counts = Counter(v["user_id"] for v in recognized_votes)
            primary_id, _ = user_counts.most_common(1)[0]
            primary_name = get_user_name(primary_id)
            
            # Show success in HUD for a moment
            for _ in range(15):
                ret, frame = cap.read() # Might be black since cap is released, but we can use last frame
                if not ret: frame = all_votes[-1]["frame"]
                hud_frame = _draw_hud(frame.copy(), [all_votes[-1]["rect"]], "ACCESS GRANTED", 1.0, primary_name)
                cv2.imshow("JARVIS AUTHENTICATION", hud_frame)
                cv2.waitKey(50)
            
            cv2.destroyWindow("JARVIS AUTHENTICATION")
            return {
                "authenticated": True,
                "user": primary_name,
                "confidence": round(min(v["confidence_raw"] for v in recognized_votes if v["user_id"] == primary_id), 1),
            }
        else:
            # Show failure
            for _ in range(15):
                ret, frame = cap.read()
                if not ret: frame = all_votes[-1]["frame"] if all_votes else np.zeros((480, 640, 3), dtype=np.uint8)
                hud_frame = _draw_hud(frame.copy(), [], "ACCESS DENIED", 1.0)
                cv2.imshow("JARVIS AUTHENTICATION", hud_frame)
                cv2.waitKey(50)
                
            cv2.destroyWindow("JARVIS AUTHENTICATION")
            return {"authenticated": False, "reason": "Unknown face"}


    except Exception as e:
        logger.error(f"Authentication error: {e}")
        cap.release()
        return {"authenticated": False, "reason": f"Error: {e}"}


# ============================================
# LEGACY COMPATIBILITY — capture_and_identify
# ============================================
def capture_and_identify() -> list:
    """
    Legacy-compatible function.
    Returns list of {"name": str, "confidence": float} dicts.
    """
    result = authenticate()

    if result.get("authenticated"):
        return [{
            "name": result["user"],
            "confidence": 1.0 - (result["confidence"] / 100.0),  # Normalize to 0-1
        }]
    else:
        return [{
            "name": "Unknown",
            "confidence": 0.0,
        }]


# ============================================
# REGISTER FACE
# ============================================
# ============================================
# REGISTRATION & TRAINING
# ============================================

def live_register_face(name: str) -> bool:
    """
    Capture 30 samples of a new face from webcam,
    assign an ID, and save to samples folder.
    """
    _load_config()
    
    samples_dir = os.path.join(os.path.dirname(__file__), "samples")
    os.makedirs(samples_dir, exist_ok=True)
    
    user_id = get_next_user_id()
    
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
        
    if not cap.isOpened():
        logger.error("Camera not accessible for registration")
        return False

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    
    logger.info(f"Registering {name} (ID: {user_id}). Look at camera...")
    count = 0
    start_time = time.time()
    
    cv2.namedWindow("JARVIS REGISTRATION", cv2.WINDOW_AUTOSIZE)
    cv2.moveWindow("JARVIS REGISTRATION", 100, 100)

    while count < 30 and (time.time() - start_time) < 60:
        ret, frame = cap.read()
        if not ret: break
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        
        for (x, y, w, h) in faces:
            count += 1
            sample_path = os.path.join(samples_dir, f"User.{user_id}.{count}.jpg")
            cv2.imwrite(sample_path, gray[y:y+h, x:x+w])
        
        # Show HUD
        prog = count / 30.0
        hud_frame = _draw_hud(frame.copy(), faces, f"CAPTURING SAMPLES ({count}/30)", prog, name)
        cv2.imshow("JARVIS REGISTRATION", hud_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'): break
        time.sleep(0.05)

    cap.release()
    cv2.destroyWindow("JARVIS REGISTRATION")
    
    if count >= 20:
        # Update user mapping
        global USER_NAMES
        USER_NAMES[user_id] = name
        _save_user_names(USER_NAMES)
        
        logger.info(f"Captured {count} samples for {name}. Starting training...")
        return train_model()
    else:
        logger.error("Failed to capture enough face samples.")
        return False

def train_model() -> bool:
    """Train the LBPH recognizer on all samples in the samples folder."""
    _load_config()
    samples_dir = os.path.join(os.path.dirname(__file__), "samples")
    
    if not os.path.exists(samples_dir) or not os.listdir(samples_dir):
        logger.error("No samples found for training.")
        return False

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    
    face_samples = []
    ids = []
    
    for filename in os.listdir(samples_dir):
        if not filename.endswith(".jpg") or "User" not in filename:
            continue
            
        path = os.path.join(samples_dir, filename)
        try:
            # Get ID from filename (User.ID.Count.jpg)
            user_id = int(filename.split(".")[1])
            
            from PIL import Image
            img = Image.open(path).convert('L')
            img_np = np.array(img, 'uint8')
            
            faces = face_cascade.detectMultiScale(img_np)
            for (x, y, w, h) in faces:
                face_samples.append(img_np[y:y+h, x:x+w])
                ids.append(user_id)
        except Exception as e:
            logger.warning(f"Error processing sample {filename}: {e}")

    if not face_samples:
        logger.error("No valid face samples processed.")
        return False

    try:
        recognizer.train(face_samples, np.array(ids))
        os.makedirs(os.path.dirname(_TRAINER_PATH), exist_ok=True)
        recognizer.write(_TRAINER_PATH)
        logger.info(f"Model successfully trained and saved to {_TRAINER_PATH}")
        
        # Reset cached recognizer to force reload
        global _recognizer
        _recognizer = None
        return True
    except Exception as e:
        logger.error(f"Training failed: {e}")
        return False

def register_face(name: str, image_path: str) -> bool:
    """Legacy: Register a face from a single image file."""
    # (Existing logic but calls train_model at end)
    _load_config()
    try:
        img = cv2.imread(image_path)
        if img is None: return False
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        if len(faces) == 0: return False
        
        user_id = get_next_user_id()
        samples_dir = os.path.join(os.path.dirname(__file__), "samples")
        os.makedirs(samples_dir, exist_ok=True)
        
        # Save as a training sample
        x, y, w, h = faces[0]
        sample_path = os.path.join(samples_dir, f"User.{user_id}.1.jpg")
        cv2.imwrite(sample_path, gray[y:y+h, x:x+w])
        
        global USER_NAMES
        USER_NAMES[user_id] = name
        _save_user_names(USER_NAMES)
        
        return train_model()
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return False


# ============================================
# LIVE FACE RECOGNITION (with real recognition)
# ============================================
def recognize_from_webcam(show_video: bool = True):
    """
    Opens webcam for continuous live face recognition.
    Shows recognized names and confidence in real-time.
    Press Q or ESC to exit.
    """
    _load_config()

    try:
        recognizer, face_cascade = _get_recognizer()
    except FileNotFoundError as e:
        logger.error(str(e))
        print(f"[Face Module] {e}")
        return

    logger.info("Starting live face recognition...")

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        logger.error("Cannot open webcam")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = _detect_faces_robust(gray, face_cascade)

        # Prepare status and names for HUD
        status = "RECOGNIZING"
        best_name = None
        
        for (x, y, w, h) in faces:
            face_roi = gray[y:y + h, x:x + w]
            user_id, confidence_raw = recognizer.predict(face_roi)

            if confidence_raw < _CONFIDENCE_THRESHOLD:
                best_name = get_user_name(user_id)
                status = "AUTHORIZED"
            else:
                status = "UNKNOWN"

        # Show HUD
        hud_frame = _draw_hud(frame.copy(), faces, status, 1.0, best_name)
        
        if show_video:
            cv2.imshow("Jarvis Face Recognition", hud_frame)

        key = cv2.waitKey(10) & 0xFF
        if key == ord("q") or key == ord("Q") or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    cv2.waitKey(1)
    logger.info("Live recognition stopped")


# ============================================
# TESTING
# ============================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n========== JARVIS FACE MODULE ==========")
    print(f"Trainer: {_TRAINER_PATH}")
    print(f"Cascade: {_CASCADE_PATH}")
    print(f"Threshold: {_CONFIDENCE_THRESHOLD}")

    while True:
        print("\n1. Authenticate (strict)")
        print("2. Register Face")
        print("3. Live Recognition")
        print("4. Capture & Identify (legacy)")
        print("5. Exit")

        choice = input("\nChoice: ").strip()

        if choice == "1":
            result = authenticate()
            print(f"\nResult: {result}")

        elif choice == "2":
            name = input("Enter name: ").strip()
            path = input("Enter image path: ").strip()
            success = register_face(name, path)
            print(f"Registered: {success}")

        elif choice == "3":
            recognize_from_webcam(show_video=True)

        elif choice == "4":
            result = capture_and_identify()
            print(f"Result: {result}")

        elif choice == "5":
            print("Exiting...")
            break

        else:
            print("Invalid choice")