import hashlib
from pathlib import Path

SCREENSHOTS_DIR = Path("screenshots")


def screenshot_path_for(url: str) -> Path:
    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    digest = hashlib.md5(url.encode()).hexdigest()
    return SCREENSHOTS_DIR / f"{digest}.png"


def capture_screenshot(page, url: str) -> str:
    path = screenshot_path_for(url)
    page.screenshot(path=str(path), full_page=True)
    return str(path)
