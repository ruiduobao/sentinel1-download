"""Pytest configuration for sentinel1-download tests."""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SCRIPT_PATH = os.path.join(PROJECT_ROOT, "sentinel1-download.py")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

_spec = importlib.util.spec_from_file_location("sentinel1_download", SCRIPT_PATH)
_module = importlib.util.module_from_spec(_spec)
sys.modules["sentinel1_download"] = _module
_spec.loader.exec_module(_module)
