"""Tests for download + .part file safety logic."""

import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import sentinel1_download


class _FixtureHandler(BaseHTTPRequestHandler):
    payloads = {
        "/file": (b"hello sar fixture", "text/plain"),
        "/large": (b"x" * (1 * 1024 * 1024), "application/octet-stream"),
    }

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        from urllib.parse import urlparse
        parsed = urlparse(self.path)
        path_only = parsed.path
        if path_only in self.payloads:
            body, ct = self.payloads[path_only]
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def http_server():
    port = _free_port()
    server = HTTPServer(("127.0.0.1", port), _FixtureHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield port
    server.shutdown()
    server.server_close()


def test_human_bytes():
    assert sentinel1_download._human_bytes(0) == "0 B"
    assert sentinel1_download._human_bytes(1024) == "1.0 KB"
    assert sentinel1_download._human_bytes(1024 * 1024) == "1.0 MB"


def test_download_asset_writes_to_part_then_renames(tmp_path, http_server):
    dest = tmp_path / "out.txt"
    ok, msg = sentinel1_download.download_asset(
        url=f"http://127.0.0.1:{http_server}/file",
        dest_path=str(dest), timeout=10, show_progress=False,
    )
    assert ok is True
    assert dest.exists()
    assert dest.read_bytes() == b"hello sar fixture"
    assert not (tmp_path / "out.txt.part").exists()


def test_download_asset_skips_existing_file(tmp_path, http_server):
    dest = tmp_path / "out.txt"
    dest.write_bytes(b"already here")
    ok, msg = sentinel1_download.download_asset(
        url=f"http://127.0.0.1:{http_server}/file",
        dest_path=str(dest), timeout=10, show_progress=False,
    )
    assert ok is True
    assert "skip" in msg.lower()


def test_download_asset_404_does_not_create_file(tmp_path, http_server):
    dest = tmp_path / "out.txt"
    ok, msg = sentinel1_download.download_asset(
        url=f"http://127.0.0.1:{http_server}/nonexistent",
        dest_path=str(dest), timeout=10, show_progress=False,
    )
    assert ok is False
    assert not dest.exists()
    assert not (tmp_path / "out.txt.part").exists()


def test_download_scene_writes_files(tmp_path, http_server):
    item = {
        "id": "S1A_TEST",
        "collection": "sentinel-1-grd",
        "assets": {
            "vh": {"href": f"http://127.0.0.1:{http_server}/file"},
            "vv": {"href": f"http://127.0.0.1:{http_server}/file"},
        },
    }
    sentinel1_download._SAS_CACHE["sentinel-1-grd"] = ("token=abc", time.time() + 600)
    result = sentinel1_download.download_scene(
        item, bands=["vh", "vv"], output_dir=str(tmp_path),
        source="pc", show_progress=False,
    )
    assert result["ok"] is True
    assert len(result["files"]) == 2
    scene_dir = tmp_path / "S1A_TEST"
    assert (scene_dir / "vh.tif").exists()
    assert (scene_dir / "vv.tif").exists()
