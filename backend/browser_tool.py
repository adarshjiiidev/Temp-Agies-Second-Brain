#!/usr/bin/env python3
"""
AEGIS Real Browser Subsystem
=============================
Provides headless Chrome browser automation:
- Web page navigation and DOM extraction
- Text extraction and semantic markdown conversion
- Full-page or viewport screenshots
- Secure URL validation

Uses the system-installed /usr/bin/google-chrome-stable with --headless=new.
"""

import os
import re
import html
import time
import shutil
from pathlib import Path
from urllib.parse import urlparse
import subprocess
from typing import Dict, Any, Optional

import sys
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.config import cfg
from backend.logger import get_logger

log = get_logger("browser")

# Find Chrome binary
_CHROME_CANDIDATES = [
    "/usr/bin/google-chrome-stable",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    shutil.which("google-chrome-stable"),
    shutil.which("google-chrome"),
    shutil.which("chromium"),
]
CHROME_BIN = next((c for c in _CHROME_CANDIDATES if c and Path(c).exists()), None)


def _validate_url(url: str) -> str:
    """Ensure URL is valid and uses http/https scheme."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")
    return url


def html_to_clean_text(raw_html: str) -> str:
    """Extract clean readable text and title from HTML without external heavy libs."""
    clean = re.sub(r"<(script|style|svg|noscript)[^>]*>.*?</\1>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
    title_match = re.search(r"<title[^>]*>(.*?)</title>", clean, flags=re.IGNORECASE)
    title = html.unescape(title_match.group(1)).strip() if title_match else "Untitled"
    clean = re.sub(r"<h[1-6][^>]*>(.*?)</h[1-6]>", r"\n\n## \1\n", clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<(p|div|section|article)[^>]*>", "\n\n", clean, flags=re.IGNORECASE)
    clean = re.sub(r"<li[^>]*>(.*?)</li>", r"\n* \1", clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = html.unescape(clean)
    clean = re.sub(r"[ \t]+", " ", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    lines = [line.strip() for line in clean.splitlines()]
    clean_text = "\n".join(line for line in lines if line)
    return f"# {title}\n\n{clean_text}" if title != "Untitled" else clean_text


class BrowserTool:
    def __init__(self, chrome_path: Optional[str] = None):
        self.chrome_bin = chrome_path or CHROME_BIN
        self.user_agent = (
            "Mozilla/5.0 (X-UA-Compatible; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36 AEGIS/2.0"
        )
        self.screenshots_dir = cfg.AEGIS_DIR / "browser_screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_available(self) -> bool:
        return bool(self.chrome_bin and Path(self.chrome_bin).exists())

    def fetch_dom(self, url: str, timeout: int = 15) -> Dict[str, Any]:
        """Fetch raw DOM of a URL using headless Chrome."""
        if not self.is_available:
            return {"success": False, "error": "Chrome binary not available for headless browsing."}

        try:
            target_url = _validate_url(url)
        except ValueError as e:
            return {"success": False, "error": str(e)}

        cmd = [
            self.chrome_bin,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            f"--user-agent={self.user_agent}",
            "--dump-dom",
            target_url,
        ]

        try:
            log.info("Fetching DOM: %s", target_url)
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if res.returncode == 0:
                raw_html = res.stdout
                return {
                    "success": True,
                    "url": target_url,
                    "dom_bytes": len(raw_html),
                    "dom": raw_html,
                }
            return {
                "success": False,
                "url": target_url,
                "error": res.stderr or f"Chrome exited with code {res.returncode}",
            }
        except subprocess.TimeoutExpired:
            log.warning("Browser timeout fetching %s after %ds", target_url, timeout)
            return {"success": False, "url": target_url, "error": f"Navigation timed out after {timeout}s"}
        except Exception as e:
            log.error("Browser error: %s", e)
            return {"success": False, "url": target_url, "error": str(e)}

    def extract_content(self, url: str, max_chars: int = 8000, timeout: int = 15) -> Dict[str, Any]:
        """Extract readable text content and markdown from a webpage."""
        dom_res = self.fetch_dom(url, timeout=timeout)
        if not dom_res.get("success"):
            return dom_res

        raw_html = dom_res["dom"]
        text = html_to_clean_text(raw_html)
        return {
            "success": True,
            "url": dom_res["url"],
            "title": text.splitlines()[0].lstrip("# ") if text.startswith("# ") else "Extracted Content",
            "content": text[:max_chars],
            "total_chars": len(text),
            "truncated": len(text) > max_chars,
        }

    def capture_screenshot(self, url: str, output_path: Optional[str] = None, timeout: int = 15) -> Dict[str, Any]:
        """Capture a screenshot of a webpage and save to file."""
        if not self.is_available:
            return {"success": False, "error": "Chrome binary not available for headless browsing."}

        try:
            target_url = _validate_url(url)
        except ValueError as e:
            return {"success": False, "error": str(e)}

        if not output_path:
            filename = f"screen_{int(time.time())}.png"
            target_path = self.screenshots_dir / filename
        else:
            target_path = Path(output_path)

        cmd = [
            self.chrome_bin,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--window-size=1280,800",
            f"--screenshot={str(target_path)}",
            target_url,
        ]

        try:
            log.info("Capturing screenshot: %s -> %s", target_url, target_path)
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if target_path.exists() and target_path.stat().st_size > 0:
                return {
                    "success": True,
                    "url": target_url,
                    "screenshot_path": str(target_path),
                    "file_size": target_path.stat().st_size,
                }
            return {
                "success": False,
                "url": target_url,
                "error": res.stderr or "Screenshot file was not generated",
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "url": target_url, "error": f"Screenshot timed out after {timeout}s"}
        except Exception as e:
            return {"success": False, "url": target_url, "error": str(e)}


browser_tool = BrowserTool()

if __name__ == "__main__":
    print(f"Chrome Binary: {browser_tool.chrome_bin}")
    print(f"Browser Tool Available: {browser_tool.is_available}")
    if browser_tool.is_available:
        res = browser_tool.extract_content("https://example.com")
        print("Extract Test Success:", res.get("success"))
        print("Title:", res.get("title"))
        print("Content Preview:\n", res.get("content", "")[:150])
