"""backend - Top-level backend package for PV-Triage decision support platform."""

import os
import sys

# Ensure backend directory is present on sys.path for direct imports
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
