"""App icon service: disk cache, Google Play CDN, deterministic SVG fallback."""

from __future__ import annotations

import html
import os
import re
import urllib.request

ICON_CACHE_DIR = ".icon_cache"


def _generate_fallback_svg(pkg: str) -> bytes:
    colors = [
        "#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6",
        "#ec4899", "#06b6d4", "#14b8a6", "#f97316", "#6366f1",
    ]
    h = 0
    for ch in pkg:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    bg = colors[h % len(colors)]

    parts = [p for p in pkg.split(".") if p]
    last = parts[-1] if parts else pkg
    if last.lower() in ("app", "android", "mobile", "client", "ui") and len(parts) > 1:
        last = parts[-2]
    initial = (last[0] if last else "?").upper()

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
        f'<rect width="64" height="64" rx="14" fill="{bg}"/>'
        f'<text x="50%" y="54%" dominant-baseline="middle" text-anchor="middle" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif" '
        f'font-size="28" font-weight="700" fill="#ffffff">{html.escape(initial)}</text>'
        f'</svg>'
    )
    return svg.encode("utf-8")


def get_app_icon(pkg: str, out_dir: str) -> tuple[bytes, str]:
    """Retrieve app icon from disk cache or fetch from Google Play CDN.

    Falls back to a deterministic SVG avatar if unavailable or offline.
    """
    cache_dir = os.path.join(out_dir, ICON_CACHE_DIR)
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except OSError:
        pass

    safe_pkg = re.sub(r"[^a-zA-Z0-9_.]", "_", pkg)
    if not safe_pkg or safe_pkg.startswith("."):
        return _generate_fallback_svg(pkg), "image/svg+xml"

    # 1. Check local disk cache
    for ext, ctype in ((".png", "image/png"), (".webp", "image/webp"),
                       (".jpg", "image/jpeg"), (".svg", "image/svg+xml")):
        path = os.path.join(cache_dir, safe_pkg + ext)
        if os.path.exists(path):
            try:
                with open(path, "rb") as fh:
                    return fh.read(), ctype
            except OSError:
                pass

    # 2. Try fetching from Google Play Store CDN
    try:
        url = f"https://play.google.com/store/apps/details?id={safe_pkg}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            page = resp.read().decode("utf-8", errors="ignore")
            m = re.search(r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', page)
            if m:
                img_url = m.group(1)
                img_req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(img_req, timeout=4.0) as img_resp:
                    img_bytes = img_resp.read()
                    ctype = img_resp.headers.get("Content-Type", "image/png").split(";")[0].strip()
                    ext = ".webp" if "webp" in ctype else ".png" if "png" in ctype else ".jpg"
                    cache_path = os.path.join(cache_dir, safe_pkg + ext)
                    try:
                        with open(cache_path, "wb") as fh:
                            fh.write(img_bytes)
                    except OSError:
                        pass
                    return img_bytes, ctype
    except Exception:
        pass

    # 3. Fallback: generate and cache SVG avatar
    svg_bytes = _generate_fallback_svg(pkg)
    try:
        with open(os.path.join(cache_dir, safe_pkg + ".svg"), "wb") as fh:
            fh.write(svg_bytes)
    except OSError:
        pass
    return svg_bytes, "image/svg+xml"
