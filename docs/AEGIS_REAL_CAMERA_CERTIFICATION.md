# AEGIS Real Camera Certification (2026-09-27, by agies)

Venue: user-authorized test of the integrated camera only. Local scope. No credential guessing, no net scan, no recording.
Evidence: `/tmp/agies_camera_evidence.json` + `scripts/camera_certify.py` + `tests/test_camera_{hardware,authorization,pipeline}.py` (10 passed).

## Hardware found
- `/dev/video0` + `/dev/video1` — Integrated Camera (USB, v4l2). video0 = 1280x720 (ffmpeg) / 640x480@30fps (cv2).

## Final table

| Capability | Mock tested | Real tested | Status | Evidence |
|---|---|---|---|---|
| Discovery | yes (prior) | yes | REAL HARDWARE VERIFIED | v4l2 lists video0+video1; registry registered both UNAUTHORIZED |
| Classification | — | yes | REAL HARDWARE VERIFIED | both LOCAL_USB/v4l2/DISCOVERED |
| Authorization boundary | — | yes | REAL HARDWARE VERIFIED | capture denied pre-auth (cv2 None + ffmpeg denied); permitted post-auth |
| USB capture | — | yes | REAL HARDWARE VERIFIED | ffmpeg 41KB jpeg 1280x720; cv2 640x480@30fps uint8, mean 49.7 |
| RTSP | — | no target | NOT CONFIGURED | no authorized URI; no guessing attempted |
| ONVIF | — | no target | NOT CONFIGURED | local-scope only |
| OpenCV pipeline | yes (prior) | yes | REAL HARDWARE VERIFIED | real frames through MOG2 pipeline |
| Motion | — | partial | REAL HARDWARE PARTIAL | MOTION_DETECTED from real frames (delta 2.03, static scene, sensitive threshold); no controlled scene-change performed |
| Events | yes (prior) | yes | REAL HARDWARE VERIFIED | real event stored, 2 recent events retrievable |
| Dashboard provenance | — | partial | LOGIC VERIFIED | sources mapped (registry/store/engine/OS); live UI render not re-verified this run |
| Failure handling | — | yes | REAL HARDWARE VERIFIED | /dev/video99 refused; disabled engine denies |
| Resource governor | — | yes | REAL HARDWARE VERIFIED | 8 cores, load 4.46 < 16 → no throttle; old `load>8` rule flagged for fix (vision_engine.py:70) |
| Privacy boundary | — | yes | REAL HARDWARE VERIFIED | OFF→deny on both paths; recording never enabled |
| Recording | — | — | NOT CONFIGURED | deliberately untested |
| TurboQuant | — | — | NOT CONFIGURED | local keyword fallback ACTIVE (no rename) |
| Tesseract OCR | — | — | NOT CONFIGURED | binary absent |

## Bugs found + fixed this run
1. `backend/server.py:1236` called `get_recent_events(cam_id=...)` — real kwarg is `camera_id` → endpoint would 500. FIXED + compile-checked.
2. `vision_engine.py:70` governor uses absolute `load > 8.0` — meaningless across core counts. FLAGGED (fix pending).

## Test results
`pytest tests/test_camera_hardware.py tests/test_camera_authorization.py tests/test_camera_pipeline.py` → **10 passed**.
