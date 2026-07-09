import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from leadradar.tools.screenshot import capture_screenshot

DEFAULT_TIMEOUT_MS = 10_000

VIEWPORT_CHECK_JS = """
() => {
    const meta = document.querySelector('meta[name="viewport"]');
    return meta !== null;
}
"""


def audit_website(url: str, timeout_ms: int = DEFAULT_TIMEOUT_MS, name: str | None = None) -> dict:
    result = {
        "loaded": False,
        "load_time_ms": None,
        "has_ssl": False,
        "has_mobile_viewport": False,
        "screenshot_path": None,
        "error": None,
    }

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                start = time.perf_counter()
                try:
                    page.goto(url, timeout=timeout_ms, wait_until="load")
                except PlaywrightTimeoutError:
                    result["error"] = "timeout"
                    return result

                result["loaded"] = True
                result["load_time_ms"] = int((time.perf_counter() - start) * 1000)
                result["has_ssl"] = page.url.startswith("https://")
                result["has_mobile_viewport"] = page.evaluate(VIEWPORT_CHECK_JS)
                result["screenshot_path"] = capture_screenshot(page, url, name)
            finally:
                browser.close()
    except Exception as exc:
        result["error"] = str(exc)

    return result
