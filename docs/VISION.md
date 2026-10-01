# AEGIS Computer Vision & Camera Subsystem

**Engine Implementation:** `backend/vision_engine.py`, `backend/camera_registry.py`, `backend/vision_pipeline.py`  
**Physical Devices:** `/dev/video0`, `/dev/video1` (Integrated Camera)  
**Screen Display:** Wayland (`wayland-1`) via `grim`  
**OCR Engine:** `/usr/bin/tesseract` (Tesseract 5.5+)  
**Multimodal Model:** 9Router vision models (`cl/inclusionai/ling-3.0-flash-vl:free`, Gemini multimodal)  
**API Endpoints:** `GET /api/vision/status`, `POST /api/vision/camera-toggle`, `GET /api/screen/intel`  

---

## 1. Vision Subsystem Architecture

```
                 TRIGGER (User Command)
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
       CAMERA PIPELINE             SCREEN PIPELINE
              │                           │
              ▼                           ▼
      EXPLICIT PERMISSION           WAYLAND GRIM
     (Hard Deny if Disabled)      (Desktop Frame Grab)
              │                           │
              ▼                           ▼
        FFMPEG V4L2               TRANSIENT FRAME BUFFER
     (1 Frame Acquisition)                │
              │                           ▼
              └─────────────┬─────────────┘
                            ▼
                     TESSERACT OCR
              (Deterministic Text Reading)
                            │
                            ▼
                   MULTIMODAL 9ROUTER
            (Vision Language Model Pipeline)
                            │
                            ▼
                 TEMPORARY CONTEXT & ANSWER
                            │
                            ▼
                 AUTOMATIC FRAME CLEANUP
             (Zero Permanent Raw Retention)
```

---

## 2. Privacy & Security Guarantees

1. **Camera OFF = Hard Deny:**
   - Default state is `camera_enabled = False`.
   - Any attempt to access `/dev/video0` or any discovered camera without explicit activation results in an immediate `Permission Denied` error.
2. **Camera Registry (`backend/camera_registry.py`):**
   - Separates *discovery* from *authorization*.
   - Discovered cameras are stored in `~/.temporary-aegis/config/cameras.json` in an unauthorized, disabled state until interactive operator approval.
3. **Vision Pipeline (`backend/vision_pipeline.py`):**
   - Local-first motion/object detection without external video streaming.
   - Structured JSON event summaries recorded to `~/.temporary-aegis/events/vision/`.
4. **Zero Permanent Video Storage:**
   - The engine never captures continuous raw video.
   - All captures are single-frame transient buffers stored in memory or tempfs, processed immediately, and deleted.
5. **Deterministic First-Pass Processing:**
   - Tesseract OCR extracts text deterministically before invoking heavy multimodal neural models.
