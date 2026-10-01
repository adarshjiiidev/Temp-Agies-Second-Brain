"""Real hardware camera tests. No synthetic frames. Skips cleanly without /dev/video*."""
import os
import subprocess
import pytest

HAS_VIDEO = any(os.path.exists(f"/dev/video{i}") for i in range(4))
needs_hw = pytest.mark.skipif(not HAS_VIDEO, reason="no /dev/video* — HARDWARE UNAVAILABLE")


def test_v4l2_lists_real_devices():
    r = subprocess.run("v4l2-ctl --list-devices", shell=True, capture_output=True, text=True, timeout=10)
    assert r.returncode == 0
    devs = [l.strip() for l in r.stdout.splitlines() if l.strip().startswith("/dev/video")]
    assert devs, "v4l2 reports no devices"


@needs_hw
def test_ffmpeg_captures_real_jpeg(tmp_path):
    out = str(tmp_path / "frame.jpg")
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "v4l2",
                        "-i", "/dev/video0", "-frames:v", "1", "-y", out],
                       capture_output=True, text=True, timeout=15)
    assert r.returncode == 0, r.stderr[:200]
    assert os.path.getsize(out) > 1000
    with open(out, "rb") as f:
        assert f.read(2) == b"\xff\xd8"


@needs_hw
def test_cv2_opens_real_device():
    cv2 = pytest.importorskip("cv2")
    cap = cv2.VideoCapture("/dev/video0")
    try:
        assert cap.isOpened()
        ok, frame = cap.read()
        assert ok and frame is not None and frame.ndim == 3
    finally:
        cap.release()


def test_bogus_device_fails_cleanly():
    cv2 = pytest.importorskip("cv2")
    cap = cv2.VideoCapture("/dev/video99")
    try:
        assert not cap.isOpened()
    finally:
        cap.release()
