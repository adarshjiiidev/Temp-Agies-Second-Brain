#!/usr/bin/env python3
"""
AEGIS Vision & Camera Subsystem
Provides safe, permission-gated camera capture, screen capture, OCR, and multimodal visual reasoning.
Adheres strictly to privacy controls:
- Camera OFF = hard deny by default.
- No continuous raw video retention; transient frame analysis only.
- Support for privacy masking / zones before model transmission.
"""

import os
import sys
import json
import time
import base64
import tempfile
import subprocess
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.logger import get_logger
from backend.linux_intelligence import linux_intelligence

log = get_logger("vision_engine")

class VisionEngine:
    def __init__(self):
        self.camera_device = "/dev/video0"
        self.camera_enabled = False  # Hard killswitch: default disabled
        self.privacy_mask_regions = []
        self.tesseract_bin = "/usr/bin/tesseract"
        self.grim_bin = "/usr/bin/grim"
        self.ffmpeg_bin = "/usr/bin/ffmpeg"
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=False)

    def capture_frame(self, camera_uri: str) -> Optional[np.ndarray]:
        """Capture a single frame using OpenCV."""
        if not self.camera_enabled:
            log.warning("Vision engine disabled. Capture denied.")
            return None
        
        cap = cv2.VideoCapture(camera_uri)
        if not cap.isOpened():
            log.error(f"Failed to open camera: {camera_uri}")
            return None
            
        ret, frame = cap.read()
        cap.release()
        
        if ret:
            return frame
        return None

    def process_motion(self, frame: np.ndarray, camera_id: str) -> Optional[Dict[str, Any]]:
        """Run basic motion detection and generate an event if motion is found."""
        if frame is None:
            return None
            
        # Resource Governor Check (core-aware: throttle only when 1m load > 2x cores)
        metrics = linux_intelligence.get_system_metrics()
        try:
            import os as _os
            cores = _os.cpu_count() or 4
            load = float(metrics.get("load_average", "0 0 0").split()[0])
            if load > cores * 2:
                log.warning(f"Resource Governor: High load ({load} on {cores} cores). Throttling vision engine.")
                return None
        except Exception:
            pass
            
        # Optional: Apply privacy mask before processing
        for region in self.privacy_mask_regions:
            x, y, w, h = region
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 0), -1)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        fgmask = self.background_subtractor.apply(gray)
        contours, _ = cv2.findContours(fgmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        motion_detected = False
        for contour in contours:
            if cv2.contourArea(contour) > 1000:  # Minimum area threshold
                motion_detected = True
                break
                
        if motion_detected:
            # Generate event
            return {
                "event_id": f"evt-{int(time.time())}",
                "camera_id": camera_id,
                "timestamp": time.time(),
                "type": "MOTION_DETECTED",
                "confidence": 0.85
            }
        return None

    def set_camera_state(self, enabled: bool) -> dict:
        """Explicit user toggle for camera hardware access."""
        self.camera_enabled = enabled
        return {
            "camera_enabled": self.camera_enabled,
            "device": self.camera_device,
            "timestamp": time.time(),
            "policy": "TRANSIENT_ANALYSIS_ONLY"
        }

    def get_camera_status(self) -> dict:
        """Query camera hardware presence and permission state."""
        dev_exists = os.path.exists(self.camera_device)
        return {
            "camera_available": dev_exists,
            "device": self.camera_device,
            "camera_enabled": self.camera_enabled,
            "privacy_state": "HARD_DENY" if not self.camera_enabled else "ACTIVE_PERMITTED"
        }

    def capture_camera_frame(self) -> tuple[Optional[bytes], Optional[str]]:
        """
        Capture a single transient frame from the camera.
        Enforces explicit authorization. Returns (image_bytes, error_message).
        """
        if not self.camera_enabled:
            return None, "Permission Denied: Camera is disabled (CAMERA OFF = HARD DENY). Call set_camera_state(True) with user authorization."

        if not os.path.exists(self.camera_device):
            return None, f"Hardware Error: Camera device {self.camera_device} not found."

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Capture 1 frame with ffmpeg
            cmd = [
                self.ffmpeg_bin,
                "-hide_banner", "-loglevel", "error",
                "-f", "v4l2",
                "-i", self.camera_device,
                "-frames:v", "1",
                "-y", tmp_path
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                with open(tmp_path, "rb") as f:
                    data = f.read()
                return data, None
            return None, f"Capture failed: {res.stderr}"
        except Exception as e:
            return None, str(e)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def capture_screen(self, region: Optional[str] = None) -> tuple[Optional[bytes], Optional[str]]:
        """
        Capture current desktop screen on Wayland using grim.
        Returns (png_bytes, error_message).
        """
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            cmd = [self.grim_bin]
            if region:
                cmd.extend(["-g", region])
            cmd.append(tmp_path)

            env = {**os.environ, "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", "wayland-1")}
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, env=env)
            if res.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                with open(tmp_path, "rb") as f:
                    data = f.read()
                return data, None
            return None, f"Screenshot failed: {res.stderr}"
        except Exception as e:
            return None, str(e)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def run_ocr(self, image_bytes: bytes) -> tuple[str, Optional[str]]:
        """
        Run deterministic Tesseract OCR on image bytes.
        Returns (extracted_text, error_message).
        """
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_in:
            tmp_in.write(image_bytes)
            tmp_in_path = tmp_in.name

        tmp_out_base = tmp_in_path + "_ocr"
        try:
            cmd = [self.tesseract_bin, tmp_in_path, tmp_out_base, "--oem", "1", "-l", "eng"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            txt_path = tmp_out_base + ".txt"
            if os.path.exists(txt_path):
                text = Path(txt_path).read_text(errors="replace").strip()
                os.unlink(txt_path)
                return text, None
            return "", f"OCR failed: {res.stderr}"
        except Exception as e:
            return "", str(e)
        finally:
            if os.path.exists(tmp_in_path):
                os.unlink(tmp_in_path)

    def analyze_image_with_model(self, image_bytes: bytes, prompt: str, model: str = "gemini/gemini-3.8-flash") -> tuple[str, str]:
        """
        Send image frame to 9Router multimodal model for reasoning.
        """
        import urllib.request
        b64_img = base64.b64encode(image_bytes).decode("utf-8")
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are AEGIS Vision Intelligence. Analyze the provided image, UI layout, or scene accurately. State observations directly and note key details."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64_img}"
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.3,
            "stream": False
        }

        from backend.free_router import resolve_keys
        keys = resolve_keys()
        o_key = keys.get("OPENROUTER_API_KEY", "")
        if not o_key:
            return "Vision reasoning requires OPENROUTER_API_KEY.", "vision/offline"

        headers = {
            "Authorization": f"Bearer {o_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:2981",
            "X-Title": "AEGIS Vision Subsystem",
        }

        try:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers
            )
            with urllib.request.urlopen(req, timeout=35) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    d = json.loads(raw)
                    return d.get("choices", [{}])[0].get("message", {}).get("content", "").strip(), model
                except:
                    return raw.strip(), model
        except Exception as e:
            return f"Multimodal Vision Error: {e}", model


vision_engine = VisionEngine()

if __name__ == "__main__":
    print("Testing Vision Subsystem...")
    status = vision_engine.get_camera_status()
    print("Camera Status:", json.dumps(status, indent=2))
    
    print("\nTesting Screen Capture...")
    img, err = vision_engine.capture_screen()
    if img:
        print(f"Screen captured: {len(img)} bytes")
        print("\nRunning OCR on screen capture...")
        text, ocr_err = vision_engine.run_ocr(img)
        print("OCR Text Excerpt:\n", text[:300] if text else "(No text)")
    else:
        print(f"Screen capture failed: {err}")
