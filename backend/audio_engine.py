#!/usr/bin/env python3
"""
AEGIS Voice & Audio Subsystem
Provides safe, permission-gated audio capture, STT transcription, and voice command parsing.
Adheres strictly to privacy controls:
- Microphone OFF = hard deny by default (MIC OFF = HARD DENY).
- No continuous audio recording; transient analysis only with immediate buffer cleanup.
"""

import os
import sys
import json
import time
import base64
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

class AudioEngine:
    def __init__(self):
        self.mic_enabled = False  # Hard killswitch default: disabled
        self.arecord_bin = "/usr/bin/arecord"
        self.ffmpeg_bin = "/usr/bin/ffmpeg"
        self.sample_rate = 16000

    def set_mic_state(self, enabled: bool) -> dict:
        """Explicit toggle for microphone hardware access."""
        self.mic_enabled = enabled
        return {
            "mic_enabled": self.mic_enabled,
            "timestamp": time.time(),
            "policy": "TRANSIENT_SNIPPET_ONLY_NO_PERSISTENT_RECORDING"
        }

    def get_audio_status(self) -> dict:
        """Query microphone device presence and privacy state."""
        has_arecord = os.path.exists(self.arecord_bin)
        return {
            "mic_available": has_arecord,
            "mic_enabled": self.mic_enabled,
            "privacy_state": "HARD_DENY" if not self.mic_enabled else "ACTIVE_PERMITTED",
            "backend": "pipewire/pulse/arecord"
        }

    def record_transient_snippet(self, duration_seconds: int = 3) -> tuple[Optional[str], Optional[str]]:
        """
        Records a short audio clip to a temporary WAV file.
        Enforces explicit authorization. Returns (temp_wav_path, error_message).
        """
        if not self.mic_enabled:
            return None, "Permission Denied: Microphone is disabled (MIC OFF = HARD DENY). Call set_mic_state(True) with authorization."

        if not os.path.exists(self.arecord_bin):
            return None, "System Error: /usr/bin/arecord not available on host."

        duration = max(1, min(10, duration_seconds))
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()

        cmd = [
            self.arecord_bin,
            "-q",
            "-d", str(duration),
            "-f", "S16_LE",
            "-r", str(self.sample_rate),
            "-c", "1",
            tmp.name
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 3)
            if res.returncode != 0:
                if os.path.exists(tmp.name):
                    os.unlink(tmp.name)
                return None, f"Capture failed: {res.stderr}"
            return tmp.name, None
        except Exception as e:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
            return None, str(e)

    def transcribe_audio(self, wav_path: str) -> dict:
        """Transcribe audio using 9Router multimodal LLM."""
        if not os.path.exists(wav_path):
            return {"success": False, "error": "Audio file not found."}

        try:
            with open(wav_path, "rb") as f:
                b64_audio = base64.b64encode(f.read()).decode("utf-8")

            # Clean up temporary WAV immediately after reading
            try:
                os.unlink(wav_path)
            except Exception:
                pass

            import urllib.request
            payload = {
                "model": "gemini/gemini-3.7-flash",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Listen to this audio snippet and output exact transcription only. If silence, output '[silence]'."},
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": b64_audio,
                                    "format": "wav"
                                }
                            }
                        ]
                    }
                ],
                "temperature": 0.1
            }

            from backend.free_router import resolve_keys
            keys = resolve_keys()
            o_key = keys.get("OPENROUTER_API_KEY", "")
            if not o_key:
                return {"success": False, "error": "Transcription requires OPENROUTER_API_KEY."}

            headers = {
                "Authorization": f"Bearer {o_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:2981",
                "X-Title": "AEGIS Audio Subsystem",
            }

            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers=headers
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                return {"success": True, "transcription": text}
        except Exception as e:
            return {"success": False, "error": f"Transcription fallback: {str(e)}"}


audio_engine = AudioEngine()

if __name__ == "__main__":
    print("Testing Audio Engine...")
    status = audio_engine.get_audio_status()
    print("Status:", status)
    assert status["privacy_state"] == "HARD_DENY"
    
    # Test permission gate
    path, err = audio_engine.record_transient_snippet(1)
    print("Killswitch test:", err)
    assert "Permission Denied" in err

    # Enable and test safe toggle
    audio_engine.set_mic_state(True)
    status_enabled = audio_engine.get_audio_status()
    print("Enabled Status:", status_enabled)
    assert status_enabled["privacy_state"] == "ACTIVE_PERMITTED"

    # Reset to default safe state
    audio_engine.set_mic_state(False)
    print("Audio Engine: VERIFIED OK")
