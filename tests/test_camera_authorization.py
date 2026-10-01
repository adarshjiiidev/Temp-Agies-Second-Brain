"""Authorization boundary tests: UNAUTHORIZED -> DENIED, authorized -> permitted."""
import pytest


def test_capture_denied_when_engine_off():
    from backend.vision_engine import VisionEngine
    ve = VisionEngine()
    assert ve.camera_enabled is False
    assert ve.capture_frame("/dev/video0") is None
    img, err = ve.capture_camera_frame()
    assert img is None and "denied" in (err or "").lower()


def test_registry_auth_lifecycle(tmp_path, monkeypatch):
    from backend.camera_registry import CameraRegistry
    reg = CameraRegistry()
    monkeypatch.setattr(reg, "registry_file", tmp_path / "cameras.json")
    cid = reg.register_discovered("TestCam", "/dev/video9", "local")
    assert reg.cameras[cid]["authorized"] is False
    assert reg.enable_vision(cid) is False  # vision before auth must fail
    assert reg.authorize_camera(cid) is True
    assert reg.enable_vision(cid) is True
    assert reg.cameras[cid]["authorized"] is True


def test_vision_toggle_roundtrip():
    from backend.vision_engine import VisionEngine
    ve = VisionEngine()
    ve.set_camera_state(True)
    assert ve.get_camera_status()["privacy_state"] == "ACTIVE_PERMITTED"
    ve.set_camera_state(False)
    assert ve.get_camera_status()["privacy_state"] == "HARD_DENY"
