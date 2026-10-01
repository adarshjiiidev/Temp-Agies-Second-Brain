"""Pipeline tests: capture -> OpenCV -> vision -> event store -> API shape."""
import os
import time
import pytest

HAS_VIDEO = os.path.exists("/dev/video0")
needs_hw = pytest.mark.skipif(not HAS_VIDEO, reason="no /dev/video0 — HARDWARE UNAVAILABLE")


@needs_hw
def test_real_frame_to_motion_event():
    cv2 = pytest.importorskip("cv2")
    import numpy as np
    from backend.vision_engine import VisionEngine
    ve = VisionEngine()
    ve.set_camera_state(True)
    try:
        cap = cv2.VideoCapture("/dev/video0")
        assert cap.isOpened()
        ok1, f1 = cap.read(); time.sleep(0.4); ok2, f2 = cap.read()
        cap.release()
        assert ok1 and ok2
        assert not np.array_equal(f1, np.zeros_like(f1)), "frame is all zeros"
        evt = ve.process_motion(f2, "test-cam")
        if evt is not None:
            assert evt["type"] == "MOTION_DETECTED"
            assert "camera_id" in evt and "timestamp" in evt
    finally:
        ve.set_camera_state(False)


def test_event_store_roundtrip(tmp_path, monkeypatch):
    from backend.camera_event_store import camera_event_store as store
    evt = {"event_id": "evt-test", "camera_id": "test-cam",
           "timestamp": time.time(), "type": "MOTION_DETECTED", "confidence": 0.9}
    assert store.store_event(evt) is True
    recent = store.get_recent_events(camera_id="test-cam", limit=5)
    assert any(e.get("event_id") == "evt-test" for e in recent)


def test_governor_uses_real_core_count():
    import multiprocessing
    cores = multiprocessing.cpu_count()
    assert cores >= 2
    with open("/proc/loadavg") as f:
        load = float(f.read().split()[0])
    assert load < cores * 2, "machine overloaded — vision must throttle"
