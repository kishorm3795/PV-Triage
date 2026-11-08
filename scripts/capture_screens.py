"""scripts/capture_screens.py - Automated Headless Screenshot Capturing

Captures clinical web client UI states at both desktop (1440x900) and mobile (390x844):
- empty
- running
- completed
- escalated
- validation_error
"""

import os
import subprocess
import time

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUTPUT_DIR = os.path.abspath("docs/screens")
BASE_URL = "http://localhost:8000"

STATES = [
    ("empty", "?state=empty"),
    ("running", "?state=running"),
    ("completed", "?state=completed"),
    ("escalated", "?state=escalated"),
    ("validation_error", "?state=validation_error"),
]

VIEWPORTS = [
    ("1440", "1440,900"),
    ("390", "390,844"),
]

def capture_all():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for state_name, query in STATES:
        for vp_name, vp_dims in VIEWPORTS:
            out_file = os.path.join(OUTPUT_DIR, f"{state_name}_{vp_name}.png")
            url = f"{BASE_URL}/{query}"
            cmd = [
                CHROME_PATH,
                "--headless=new",
                f"--window-size={vp_dims}",
                f"--screenshot={out_file}",
                "--hide-scrollbars",
                "--virtual-time-budget=2000",
                url
            ]
            print(f"Capturing {state_name} at {vp_name}px -> {out_file}...")
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and os.path.exists(out_file):
                size_kb = os.path.getsize(out_file) / 1024
                print(f"  OK ({size_kb:.1f} KB)")
            else:
                print(f"  FAILED (exit code {res.returncode}): {res.stderr[:200]}")
            time.sleep(0.5)

if __name__ == "__main__":
    capture_all()
