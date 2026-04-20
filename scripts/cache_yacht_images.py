#!/usr/bin/env python3
"""
cache_yacht_images.py — Download yacht images from the booking-manager portal
and upload them permanently to the WordPress media library.

Saves scripts/image_cache.json:
  { "YACHT_ID": { "images": ["https://sailscanner.ai/wp-content/..."], "layout": "..." } }

build_proposal_from_csv.py reads this cache automatically — proposals use
WordPress-hosted images instead of private portal URLs that require auth.

How it works:
  1. Logs in to portal.booking-manager.com automatically (credentials from .env)
  2. For each yacht, fetches the live portal detail page to get fresh photo URLs
     (stale bmdoc/ URLs from the CSV are short-lived and expire — must re-fetch)
  3. Downloads each photo using the authenticated session
  4. Converts webp → JPEG (WordPress ImageMagick can't handle webp natively)
  5. Uploads to WordPress media library
  6. Saves mapping to image_cache.json (resumable — skips already-cached yachts)

Usage:
  # Cache all yachts (safe to re-run — skips already-cached entries):
  python scripts/cache_yacht_images.py

  # Cache a single yacht by ID:
  python scripts/cache_yacht_images.py --yacht-id 1341585820000101933

  # Test with first 5 yachts only:
  python scripts/cache_yacht_images.py --limit 5

  # Force re-upload even if already cached:
  python scripts/cache_yacht_images.py --force

  # Preview without downloading or uploading:
  python scripts/cache_yacht_images.py --dry-run --limit 3

Requires in .env:
  BOOKING_MANAGER_EMAIL, BOOKING_MANAGER_PASSWORD
  SAILSCANNER_WP_USER, SAILSCANNER_WP_APP_PASSWORD, SAILSCANNER_WP_URL

Install deps:
  pip install Pillow requests python-dotenv beautifulsoup4
"""
from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import os
import re
import sys
import time
from pathlib import Path

# ── Load .env ─────────────────────────────────────────────────────────────────
_script_dir   = Path(__file__).resolve().parent
_project_root = _script_dir.parent

try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")
except ImportError:
    pass

try:
    import requests
except ImportError:
    print("ERROR: pip install requests", file=sys.stderr)
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
    _BS4 = True
except ImportError:
    _BS4 = False
    print("ERROR: pip install beautifulsoup4", file=sys.stderr)
    sys.exit(1)

try:
    from PIL import Image
    _PILLOW = True
except ImportError:
    _PILLOW = False
    print(
        "WARNING: Pillow not installed — webp images will be uploaded as-is.\n"
        "  WordPress may not generate thumbnails correctly.\n"
        "  Install with: pip install Pillow\n",
        file=sys.stderr,
    )

# ── Config ────────────────────────────────────────────────────────────────────
PORTAL_EMAIL    = os.environ.get("BOOKING_MANAGER_EMAIL", "").strip()
PORTAL_PASSWORD = os.environ.get("BOOKING_MANAGER_PASSWORD", "").strip()
WP_USER         = os.environ.get("SAILSCANNER_WP_USER", "").strip()
WP_PASS         = os.environ.get("SAILSCANNER_WP_APP_PASSWORD", "").strip().replace(" ", "")

_wp_base_raw = os.environ.get("SAILSCANNER_WP_URL", "https://sailscanner.ai").rstrip("/")
if "/wp-json" in _wp_base_raw:
    from urllib.parse import urlparse as _up
    _parsed = _up(_wp_base_raw)
    WP_BASE = f"{_parsed.scheme}://{_parsed.netloc}"
else:
    WP_BASE = _wp_base_raw

_default_csv = _project_root.parent.parent.parent.parent / "Provider Data" / "yacht_database_full.csv"
CSV_PATH     = Path(os.environ.get("SAILSCANNER_CSV_PATH", str(_default_csv)))
CACHE_PATH   = _script_dir / "image_cache.json"

MAX_IMAGES      = 12    # Max gallery images per yacht (deck plan handled separately)
DELAY_BETWEEN   = 0.3   # Seconds between portal requests — be polite but not glacial
REQUEST_TIMEOUT = 25

PORTAL_BASE      = "https://portal.booking-manager.com"
PORTAL_LOGIN_URL = f"{PORTAL_BASE}/wbm2/app/login_register/login_to_continue.jsp"
# Test URL used to verify session — a page that definitely requires auth
PORTAL_TEST_URL  = f"{PORTAL_BASE}/wbm2/app/yachts/index.jsp"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Shared requests.Session — holds the JSESSIONID cookie across all portal calls.
_portal = requests.Session()
_portal.headers.update({
    "User-Agent":       _UA,
    "Accept":           "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language":  "en-GB,en;q=0.9",
    "Referer":          PORTAL_BASE + "/",
})

# Strings that appear in the portal login page — used to detect unauthenticated responses.
_LOGIN_SIGNALS = [
    'name="login_email"',
    'name="login_password"',
    'id="login-box"',
    "login_to_continue",
    "To view this page you need to login",
]


# ── Portal auth ───────────────────────────────────────────────────────────────

def _is_login_page(html: str) -> bool:
    return any(sig in html for sig in _LOGIN_SIGNALS)


def _session_is_valid() -> bool:
    """Return True if the current session cookie is authenticated."""
    try:
        resp = _portal.get(PORTAL_TEST_URL, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if resp.status_code != 200:
            return False
        return not _is_login_page(resp.text)
    except Exception:
        return False


def _login() -> bool:
    """
    Log in to the booking-manager portal.
    Updates _portal session with a valid JSESSIONID.
    Returns True on success.
    """
    if not PORTAL_EMAIL or not PORTAL_PASSWORD:
        print(
            "ERROR: BOOKING_MANAGER_EMAIL / BOOKING_MANAGER_PASSWORD not set in .env",
            file=sys.stderr,
        )
        return False

    print("Logging in to booking-manager portal...", flush=True)
    try:
        # GET the login page first to establish a pre-auth session.
        _portal.get(PORTAL_LOGIN_URL, timeout=REQUEST_TIMEOUT)

        # POST the login form.
        resp = _portal.post(
            PORTAL_LOGIN_URL,
            data={
                "is_post_back":   "1",
                "login_email":    PORTAL_EMAIL,
                "login_password": PORTAL_PASSWORD,
                "referrer":       f"{PORTAL_BASE}/wbm2/app/yachts/index.jsp",
            },
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        # Check the result page isn't still the login form.
        if _is_login_page(resp.text):
            print(
                "ERROR: Login failed — still showing login page.\n"
                "  Check BOOKING_MANAGER_EMAIL and BOOKING_MANAGER_PASSWORD in .env",
                file=sys.stderr,
            )
            return False

        jsid = _portal.cookies.get("JSESSIONID", "")
        print(f"Logged in successfully. Session: {jsid[:8]}...", flush=True)
        return True

    except Exception as exc:
        print(f"ERROR: Login request failed: {exc}", file=sys.stderr)
        return False


def _ensure_session() -> bool:
    """Ensure we have a valid portal session, logging in if needed."""
    if _session_is_valid():
        print("Portal session already valid.", flush=True)
        return True
    return _login()


# ── Photo URL extraction ──────────────────────────────────────────────────────

def fetch_fresh_photo_urls(detail_url: str) -> list[str]:
    """
    Fetch the yacht's live portal detail page and extract current photo URLs.
    Returns a list of absolute bmdoc URLs.
    The stale URLs stored in the CSV expire — we always re-fetch to get fresh ones.
    """
    try:
        resp = _portal.get(detail_url, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            print(f"    ✗ Detail page HTTP {resp.status_code}", file=sys.stderr)
            return []
        if _is_login_page(resp.text):
            print("    ✗ Session expired mid-run — re-logging in...", file=sys.stderr)
            if _login():
                resp = _portal.get(detail_url, timeout=REQUEST_TIMEOUT)
            else:
                return []

        soup = BeautifulSoup(resp.text, "html.parser")
        photos: list[str] = []
        seen: set[str] = set()

        for img in soup.find_all("img"):
            src = (img.get("src") or img.get("data-src") or "").strip()
            if not src:
                continue
            if not re.search(r"\.(jpg|jpeg|webp|png)", src, re.I):
                continue

            # Resolve relative bmdoc/ URLs to absolute.
            # These are relative to the /wbm2/ base, not the portal root.
            if src.startswith("bmdoc/"):
                src = f"{PORTAL_BASE}/wbm2/{src}"
            elif src.startswith("/"):
                src = PORTAL_BASE + src

            if "portal.booking-manager.com" not in src:
                continue

            # Strip the width/defaultToEmpty params — download at full size.
            clean = re.sub(r"[?&]width=\d+", "", src).rstrip("?&")
            clean = re.sub(r"[?&]defaultToEmpty=\w+", "", clean).rstrip("?&")

            if clean not in seen:
                seen.add(clean)
                photos.append(clean)

        return photos

    except Exception as exc:
        print(f"    ✗ Error fetching detail page: {exc}", file=sys.stderr)
        return []


# ── Image helpers ─────────────────────────────────────────────────────────────

def _is_deck_plan(url: str) -> bool:
    fname = url.split("?")[0].rsplit("/", 1)[-1].lower()
    return any(kw in fname for kw in ("layout", "drawing", "plano", "plan_", "deck"))


MAX_UPLOAD_WIDTH = 1920  # Cap before uploading — avoids WP auto-scaling large files


def _to_jpeg(data: bytes) -> bytes | None:
    """
    Convert image bytes to JPEG using Pillow, capping width at MAX_UPLOAD_WIDTH.
    Smaller files upload faster and WordPress won't auto-scale them (no -scaled suffix).
    Returns None if Pillow unavailable.
    """
    if not _PILLOW:
        return None
    try:
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB")
        if img.width > MAX_UPLOAD_WIDTH:
            ratio = MAX_UPLOAD_WIDTH / img.width
            new_h = int(img.height * ratio)
            img = img.resize((MAX_UPLOAD_WIDTH, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85, optimize=True)
        return buf.getvalue()
    except Exception as exc:
        print(f"    ✗ Pillow error: {exc}", file=sys.stderr)
        return None


def _download(url: str) -> bytes | None:
    """Download one image from the portal using the authenticated session."""
    try:
        resp = _portal.get(
            url,
            headers={"Accept": "image/webp,image/png,image/*,*/*;q=0.8"},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200 and len(resp.content) > 500:
            # Sanity: HTML response = login redirect, not an image.
            ct = resp.headers.get("Content-Type", "")
            if "text/html" in ct:
                print(f"    ✗ Got HTML instead of image (session issue?): {url[:80]}", file=sys.stderr)
                return None
            return resp.content
        print(f"    ✗ HTTP {resp.status_code}: {url[:80]}", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"    ✗ Download error: {exc}", file=sys.stderr)
        return None


def _upload_to_wp(img_bytes: bytes, filename: str, mime: str = "image/jpeg") -> str | None:
    """Upload image bytes to WordPress media library. Retries up to 3 times on timeout."""
    endpoint = f"{WP_BASE}/wp-json/wp/v2/media"
    auth      = "Basic " + base64.b64encode(f"{WP_USER}:{WP_PASS}".encode()).decode()
    headers  = {
        "Authorization":       auth,
        "Content-Type":        mime,
        "Content-Disposition": f'attachment; filename="{filename}"',
        "User-Agent":          "Mozilla/5.0 (compatible; SailScanner-ImageCache/1.0)",
    }
    for attempt in range(1, 4):
        try:
            resp = requests.post(endpoint, data=img_bytes, headers=headers, timeout=90)
            if resp.ok:
                data = resp.json()
                src  = data.get("source_url") or (data.get("guid") or {}).get("rendered") or ""
                return src or None
            print(f"    ✗ WP upload {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            return None  # non-timeout HTTP error — no point retrying
        except Exception as exc:
            if attempt < 3:
                wait = attempt * 5
                print(f"    ✗ WP upload timeout (attempt {attempt}/3) — retrying in {wait}s…", file=sys.stderr)
                time.sleep(wait)
            else:
                print(f"    ✗ WP upload failed after 3 attempts: {exc}", file=sys.stderr)
    return None


def _process_one(url: str, yacht_id: str, label: str, dry_run: bool) -> str | None:
    """Download, convert, and upload one image. Returns WP URL or None."""
    if dry_run:
        print(f"    [dry-run] {label}: {url[:80]}")
        return "dry-run-placeholder"

    raw = _download(url)
    if not raw:
        return None

    is_webp = url.lower().endswith(".webp") or b"WEBP" in raw[:12]
    if is_webp:
        img_bytes = _to_jpeg(raw)
        ext, mime = "jpg", "image/jpeg"
        if img_bytes is None:            # Pillow not available — upload raw webp
            img_bytes = raw
            ext, mime = "webp", "image/webp"
    else:
        img_bytes = raw
        raw_ext   = url.split("?")[0].rsplit(".", 1)[-1].lower()
        ext       = raw_ext if raw_ext in ("jpg", "jpeg", "png") else "jpg"
        mime      = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"

    filename = f"ss_yacht_{yacht_id}_{label}.{ext}"
    wp_url   = _upload_to_wp(img_bytes, filename, mime)
    if wp_url:
        print(f"    ✓ {label}: {wp_url}")
    time.sleep(DELAY_BETWEEN)
    return wp_url


# ── Per-yacht processor ───────────────────────────────────────────────────────

def process_yacht(yacht_id: str, detail_url: str, dry_run: bool) -> dict:
    """
    Fetch live photo URLs from the portal, download, convert, and upload.
    Returns {images: [wp_url, ...], layout: wp_url_or_""}.
    """
    print(f"    Fetching fresh photo URLs from portal...", flush=True)
    photo_urls = fetch_fresh_photo_urls(detail_url)

    if not photo_urls:
        print(f"    ✗ No photos found on detail page.", file=sys.stderr)
        return {"images": [], "layout": ""}

    print(f"    Found {len(photo_urls)} photos on live page.")

    gallery: list[str] = []
    layout:  str       = ""

    for url in photo_urls:
        if _is_deck_plan(url):
            if not layout:
                wp_url = _process_one(url, yacht_id, "layout", dry_run)
                if wp_url:
                    layout = wp_url
        else:
            if len(gallery) < MAX_IMAGES:
                idx    = str(len(gallery) + 1).zfill(2)
                wp_url = _process_one(url, yacht_id, idx, dry_run)
                if wp_url:
                    gallery.append(wp_url)

    return {"images": gallery, "layout": layout}


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cache yacht images: portal detail pages → WordPress media library."
    )
    parser.add_argument("--yacht-id", metavar="ID",   help="Process a single yacht by ID.")
    parser.add_argument("--limit",    type=int,        help="Max yachts to process (for testing).")
    parser.add_argument("--force",    action="store_true", help="Re-process even if already cached.")
    parser.add_argument("--dry-run",  action="store_true", help="Preview only — no uploads.")
    args = parser.parse_args()

    # Validate credentials
    if not args.dry_run:
        if not WP_USER or not WP_PASS:
            print("ERROR: SAILSCANNER_WP_USER / SAILSCANNER_WP_APP_PASSWORD missing in .env", file=sys.stderr)
            sys.exit(1)
        if not _ensure_session():
            print("ERROR: Could not log in to the portal. Check credentials in .env.", file=sys.stderr)
            sys.exit(1)

    # Load CSV
    if not CSV_PATH.exists():
        print(f"ERROR: CSV not found: {CSV_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    print(f"Loaded {len(rows)} yachts from CSV.")

    # Load existing cache (for resumability)
    cache: dict[str, dict] = {}
    if CACHE_PATH.exists():
        try:
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            print(f"Cache: {len(cache)} yachts already processed.")
        except Exception:
            cache = {}

    # Filter to a single yacht if requested
    if args.yacht_id:
        rows = [r for r in rows if (r.get("Yacht ID") or "").strip() == args.yacht_id]
        if not rows:
            print(f"ERROR: Yacht ID {args.yacht_id!r} not found in CSV.", file=sys.stderr)
            sys.exit(1)

    total     = len(rows)
    processed = 0
    skipped   = 0

    for row in rows:
        if args.limit and processed >= args.limit:
            break

        yacht_id   = (row.get("Yacht ID") or "").strip()
        model      = (row.get("Model") or row.get("Yacht Name") or "?").strip()
        detail_url = (row.get("Detail Page URL") or "").strip()

        if not yacht_id:
            continue
        if not detail_url:
            print(f"  [{processed+skipped+1}/{total}] {model}: no Detail Page URL — skipping.")
            continue
        if not args.force and yacht_id in cache:
            skipped += 1
            continue

        print(f"\n  [{processed+skipped+1}/{total}] {model} ({yacht_id})", flush=True)
        entry = process_yacht(yacht_id, detail_url, dry_run=args.dry_run)
        print(f"  → {len(entry['images'])} images, deck plan: {'✓' if entry['layout'] else '✗'}")

        if not args.dry_run:
            cache[yacht_id] = entry
            # Save after every yacht so progress is preserved if interrupted.
            CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")

        processed += 1

    print(f"\n{'[dry-run] ' if args.dry_run else ''}Done: {processed} processed, {skipped} skipped.")
    if not args.dry_run:
        print(f"Cache saved → {CACHE_PATH}")


if __name__ == "__main__":
    main()
