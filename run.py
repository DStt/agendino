"""Convenience entrypoint so the app can be started from the repository root.

Development:  fastapi dev run.py
Production:   fastapi run run.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from main import app  # noqa: E402,F401
