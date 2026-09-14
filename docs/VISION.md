# AEGIS Computer Vision & Camera Subsystem

**Engine Implementation:** `backend/vision_engine.py`  
**Physical Devices:** `/dev/video0`, `/dev/video1` (Integrated Camera)  
**Screen Display:** Wayland (`wayland-1`) via `grim`  
**OCR Engine:** `/usr/bin/tesseract` (Tesseract 5.5+)  
**Multimodal Model:** `gemini/gemini-3.8-flash` (9Router)  

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
            (Gemini 3.8 Flash Vision Model)
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
   - Any attempt to access `/dev/video0` without explicit activation results in an immediate `Permission Denied` error.
2. **Zero Permanent Video Storage:**
   - The engine never captures continuous raw video.
   - All captures are single-frame transient buffers stored in memory or tempfs, processed immediately, and deleted.
3. **Deterministic First-Pass Processing:**
   - Tesseract OCR extracts text deterministically before invoking heavy multimodal neural models.
