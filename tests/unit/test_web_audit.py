import http.server
import threading
import time
from pathlib import Path

import pytest

from leadradar.tools.web_audit import audit_website

VIEWPORT_HTML = (
    "data:text/html,<html><head>"
    "<meta name='viewport' content='width=device-width, initial-scale=1'>"
    "</head><body>Hello</body></html>"
)

NO_VIEWPORT_HTML = "data:text/html,<html><head></head><body>Hello</body></html>"


class _SlowHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        time.sleep(2)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body>slow</body></html>")

    def log_message(self, format, *args) -> None:
        pass


@pytest.fixture
def slow_server():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _SlowHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}/"
    server.shutdown()
    thread.join()


def test_audit_website_success_detects_viewport(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = audit_website(VIEWPORT_HTML)

    assert result["loaded"] is True
    assert result["error"] is None
    assert result["has_ssl"] is False
    assert result["has_mobile_viewport"] is True
    assert isinstance(result["load_time_ms"], int)
    assert result["screenshot_path"] is not None
    assert Path(result["screenshot_path"]).exists()


def test_audit_website_reports_missing_viewport_meta(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = audit_website(NO_VIEWPORT_HTML)

    assert result["loaded"] is True
    assert result["has_mobile_viewport"] is False


def test_audit_website_handles_connection_error():
    result = audit_website("http://127.0.0.1:1")

    assert result["loaded"] is False
    assert result["error"] is not None
    assert result["screenshot_path"] is None


def test_audit_website_times_out(slow_server):
    result = audit_website(slow_server, timeout_ms=500)

    assert result["loaded"] is False
    assert result["error"] == "timeout"
    assert result["screenshot_path"] is None
