import hashlib
import re
from pathlib import Path

SCREENSHOTS_DIR = Path("screenshots")


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug[:50] or "site"


def screenshot_path_for(url: str, name: str | None = None) -> Path:
    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    digest = hashlib.md5(url.encode()).hexdigest()[:8]
    if name:
        return SCREENSHOTS_DIR / f"{_slugify(name)}_{digest}.png"
    return SCREENSHOTS_DIR / f"{digest}.png"


def capture_screenshot(page, url: str, name: str | None = None) -> str:
    path = screenshot_path_for(url, name)
    page.screenshot(path=str(path), full_page=True)
    return str(path)
