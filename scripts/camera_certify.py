#!/usr/bin/env python3
"""Real camera hardware certification run. Local scope only. No synthetic frames.
Writes evidence JSON to stdout + /tmp/agies_camera_evidence.json.
Authorization venue: user prompt 2026-09-27 (integrated camera test only)."""
import json, os, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
E = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "steps": {}}

def step(name, fn):
    try:
        E["steps"][name] = {"ok": True, "result": fn()}
    except Exception as e:
        E["steps"][name] = {"ok": False, "error": str(e)[:300]}

from backend.camera_registry import CameraRegistry
from backend.vision_engine import VisionEngine
from backend.camera_event_store import camera_event_store

reg = CameraRegistry()
ve = VisionEngine()

def s_discover():
    out = subprocess.run("v4l2-ctl --list-devices", shell=True, capture_output=True, text=True, timeout=10)
    devs = [l.strip() for l in out.stdout.splitlines() if l.strip().startswith("/dev/video")]
    cams = []
    for d in devs:
        cid = reg.register_discovered("Integrated Camera (cert run)", d, "local")
        c = dict(reg.cameras[cid]); c["cam_id"] = cid
        cams.append(c)
    return {"v4l2_devices": devs, "registered": cams}
step("1_discover", s_discover)
cams = E["steps"]["1_discover"]["result"]["registered"]
cam_id = cams[0]["cam_id"] if cams else None

def s_classify():
    rows = []
    for c in cams:
        typ = "LOCAL_USB" if c["uri"].startswith("/dev/video") else "UNKNOWN"
        rows.append({"cam_id": c["cam_id"], "uri": c["uri"], "class": typ,
                     "authorized": c["authorized"], "ip": None, "mac": None,
                     "vendor": "Integrated", "protocol": "v4l2", "status": "DISCOVERED"})
    rows.append({"note": "network/RTSP/ONVIF scan skipped: local-scope only, no authorized net target"})
    return rows
step("2_classify", s_classify)

def s_auth_deny():
    f = ve.capture_frame("/dev/video0")
    img, err = ve.capture_camera_frame()
    return {"cv2_capture_when_off": f is None, "ffmpeg_capture_when_off": img is None,
            "err": (err or "")[:120]}
step("3_auth_deny_before", s_auth_deny)

def s_authorize():
    assert cam_id, "no camera"
    reg.authorize_camera(cam_id)
    reg.enable_vision(cam_id)
    ve.set_camera_state(True)
    return {"cam_id": cam_id, "registry": reg.cameras[cam_id], "engine": ve.get_camera_status()}
step("4_authorize_test_only", s_authorize)

def s_ffmpeg_frame():
    img, err = ve.capture_camera_frame()
    if img is None:
        return {"captured": False, "error": (err or "")[:200]}
    import struct
    w = h = None
    if img[:2] == b"\xff\xd8":
        for i in range(2, len(img) - 9):
            if img[i] == 0xFF and img[i+1] in (0xC0, 0xC2):
                h, w = struct.unpack(">HH", img[i+5:i+9]); break
    return {"captured": True, "bytes": len(img), "format": "jpeg", "width": w, "height": h}
step("5_ffmpeg_real_frame", s_ffmpeg_frame)

def s_cv2_frame():
    import cv2
    cap = cv2.VideoCapture("/dev/video0")
    opened = cap.isOpened()
    info = {"opened": opened}
    if opened:
        info["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        info["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        info["fps"] = round(float(cap.get(cv2.CAP_PROP_FPS)), 2)
        ok1, f1 = cap.read(); time.sleep(0.4); ok2, f2 = cap.read()
        cap.release()
        info["read1"] = bool(ok1); info["read2"] = bool(ok2)
        if ok1:
            info["shape"] = list(f1.shape); info["dtype"] = str(f1.dtype)
            info["mean_pixel"] = round(float(f1.mean()), 2)
        if ok1 and ok2:
            import numpy as np
            info["frame_delta_mean"] = round(float(np.abs(f1.astype(int) - f2.astype(int)).mean()), 3)
            evt = ve.process_motion(f2, cam_id)
            info["motion_event"] = evt
            if evt:
                camera_event_store.store_event(evt)
                info["event_stored"] = True
    return info
step("6_cv2_real_frames_motion", s_cv2_frame)

def s_provenance():
    evts = camera_event_store.get_recent_events(camera_id=cam_id, limit=5) if cam_id else []
    return {"registry_state": reg.cameras.get(cam_id), "engine_status": ve.get_camera_status(),
            "recent_events": evts, "api_sources": ["camera_registry", "camera_event_store", "vision_engine", "os devices"]}
step("7_provenance", s_provenance)

def s_failure():
    import cv2
    cap = cv2.VideoCapture("/dev/video99")
    opened = cap.isOpened()
    cap.release()
    ve2 = VisionEngine()
    img, err = ve2.capture_camera_frame()
    return {"bogus_device_opened": opened, "disabled_engine_denies": img is None}
step("8_failure_handling", s_failure)

def s_governor():
    import multiprocessing
    with open("/proc/loadavg") as f: load = f.read().split()
    cores = multiprocessing.cpu_count()
    return {"cores": cores, "load_1m": load[0], "governor_rule": "load>cores*2 throttle",
            "would_throttle_now": float(load[0]) > cores * 2}
step("9_resource_governor", s_governor)

def s_privacy_off():
    ve.set_camera_state(False)
    img, err = ve.capture_camera_frame()
    f = ve.capture_frame("/dev/video0")
    return {"camera_off_denies_ffmpeg": img is None, "camera_off_denies_cv2": f is None,
            "recording": "never enabled this run"}
step("10_privacy_off", s_privacy_off)

E["turboquant"] = "NOT_CONFIGURED (local keyword fallback ACTIVE)"
E["tesseract"] = "NOT_CONFIGURED (binary absent)"
E["rtsp"] = "NOT_CONFIGURED (no authorized RTSP target; no credential guessing)"
E["onvif"] = "NOT_CONFIGURED (no authorized target)"
Path("/tmp/agies_camera_evidence.json").write_text(json.dumps(E, indent=1))
print(json.dumps(E, indent=1))
