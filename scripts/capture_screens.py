"""scripts/capture_screens.py - Automated Headless Screenshot Capturing

Captures clinical web client UI states at both desktop (1440x900) and mobile (390x844):
- empty
- running
- completed (light and dark)
- escalated
- validation_error
"""

import os
import subprocess
import time
import urllib.request
from pathlib import Path

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUTPUT_DIR = os.path.abspath("docs/screens")
BASE_URL = "http://localhost:8000"

STATES = [
    ("empty", "?state=empty&theme=light"),
    ("running", "?state=running&theme=light"),
    ("completed", "?state=completed&theme=light"),
    ("completed_light", "?state=completed&theme=light"),
    ("completed_dark", "?state=completed&theme=dark"),
    ("escalated", "?state=escalated&theme=light"),
    ("validation_error", "?state=validation_error&theme=light"),
]

VIEWPORTS = [
    ("1440", "1440,900"),
    ("390", "390,844"),
]


def resolve_base_url() -> str:
    """Determine whether to use live localhost server or direct file URL."""
    try:
        req = urllib.request.Request(BASE_URL, headers={"User-Agent": "ScreenshotCapture/1.0"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            if resp.status == 200:
                print(f"Connecting to live server at {BASE_URL}")
                return BASE_URL
    except Exception:
        pass

    local_html = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
    file_url = local_html.as_uri()
    print(f"Server not running on {BASE_URL}. Using local file URL: {file_url}")
    return file_url


def capture_all():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base = resolve_base_url()

    for state_name, query in STATES:
        for vp_name, vp_dims in VIEWPORTS:
            out_file = os.path.join(OUTPUT_DIR, f"{state_name}_{vp_name}.png")
            # If using file://, query string is appended
            url = f"{base}{query}"
            cmd = [
                CHROME_PATH,
                "--headless=new",
                f"--window-size={vp_dims}",
                f"--screenshot={out_file}",
                "--hide-scrollbars",
                "--virtual-time-budget=2000",
                url,
            ]
            print(f"Capturing {state_name} at {vp_name}px -> {out_file}...")
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and os.path.exists(out_file):
                size_kb = os.path.getsize(out_file) / 1024
                print(f"  OK ({size_kb:.1f} KB)")
            else:
                print(f"  FAILED (exit code {res.returncode}): {res.stderr[:200]}")
            time.sleep(0.3)


if __name__ == "__main__":
    capture_all()
