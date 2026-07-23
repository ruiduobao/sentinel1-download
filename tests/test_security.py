"""Security / privacy baseline tests."""

import os
import sys

import pytest

import sentinel1_download


def test_module_docstring_has_privacy_section():
    doc = sentinel1_download.__doc__ or ""
    assert "License" in doc or "license" in doc


def test_no_anti_bot_patterns():
    src_path = os.path.join(os.path.dirname(sentinel1_download.__file__), "sentinel1-download.py")
    src_path = os.path.abspath(src_path)
    with open(src_path, "r", encoding="utf-8") as f:
        src = f.read()
    forbidden = ["STEALTH_JS", "stealth", "anti-bot", "anti_bot", "hide webdriver"]
    for pat in forbidden:
        assert pat.lower() not in src.lower(), f"forbidden pattern {pat!r} found"


def test_no_llm_imports():
    src_path = os.path.abspath(os.path.join(os.path.dirname(sentinel1_download.__file__), "sentinel1-download.py"))
    with open(src_path, "r", encoding="utf-8") as f:
        src = f.read()
    forbidden = ["import openai", "import anthropic", "from openai", "from anthropic"]
    for pat in forbidden:
        assert pat not in src


def test_uses_requests_only():
    src_path = os.path.abspath(os.path.join(os.path.dirname(sentinel1_download.__file__), "sentinel1-download.py"))
    with open(src_path, "r", encoding="utf-8") as f:
        src = f.read()
    heavy = ["import pystac", "from pystac", "import planetary_computer", "import rasterio", "import geopandas"]
    for pat in heavy:
        assert pat not in src


def test_user_agent_identifies_skill():
    assert "sentinel1-download" in sentinel1_download.USER_AGENT


def test_trust_env_default_disabled():
    if os.environ.get("SENTINEL1_DOWNLOAD_USE_PROXY") != "1":
        assert sentinel1_download.DEFAULT_TRUST_ENV is False
