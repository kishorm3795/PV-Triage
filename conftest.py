"""conftest.py - Pytest root configuration ensuring backend modules are discoverable."""

import os
import sys

root_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(root_dir, "backend")

for d in (backend_dir, root_dir):
    if d not in sys.path:
        sys.path.insert(0, d)
