#!/usr/bin/env python3
"""
Create a single ss_proposal_yacht post via the WordPress REST API.
Edit the YACHT dict below and run:
  python scripts/create_standalone_yacht.py

Authentication uses the same Application Password credentials from .env.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_script_dir   = Path(__file__).resolve().parent
_project_root = _script_dir.parent

try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")
except ImportError:
    pass

import base64
import os

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

USER_AGENT = "Mozilla/5.0 (compatible; SailScanner-Proposals/1.0)"

# ── Yacht data to create ──────────────────────────────────────────────────────
# Edit this dict with the yacht details.

YACHT: dict = {
    # Post title (shown in WP admin list)
    "title": "Bali 4.2",

    # display_name shown on proposal cards and detail page
    "display_name": "Bali 4.2",

    # Specs
    "specs_json": [
        {"label": "Year",        "value": "2023"},
        {"label": "Type",        "value": "Catamaran (Bali 4.2)"},
        {"label": "Length",      "value": "12.85 m"},
        {"label": "Berths",      "value": "9"},
        {"label": "Cabins",      "value": "4"},
        {"label": "WC / Shower", "value": "5 (Electric Toilets)"},
    ],

    # Shortcut meta used by the template for header pills
    "year":     2023,
    "length_m": 12.85,
    "cabins":   4,
    "berths":   9,
    "country":  "Italy",
    "region":   "Sardinia",
    "base_name": "Italy, Sardinia / Marina di Portisco",

    # Charter details
    "charter_json": {
        "base":     "Italy, Sardinia / Marina di Portisco",
        "date_from": "15 August 2026",
        "date_to":   "19 August 2026",
        "checkin":   "18:00",
        "checkout":  "08:00",
    },

    # Pricing
    "prices_json": {
        "base_price":    "15,000.00 €",
        "charter_price": "6,360.00 €",
        "discounts": [
            {"label": "Discount (58%)", "amount": "- 8,640.00 €"},
        ],
        "mandatory_base": [
            {"label": "Starter Pack (welcome kit, bed linen, towels, gas, final cleaning)",
             "amount": "875.00 €"},
            {"label": "La Maddalena National Park Permit (compulsory if sailing north)",
             "amount": "0.00 €"},
            {"label": "Security Deposit (refundable, credit card only — VISA/MASTERCARD)",
             "amount": "4,500.00 €"},
        ],
        "optional_extras": [
            {"label": "Reduced Security Deposit (non-refundable, replaces full deposit)",
             "amount": "1,000.00 €"},
            {"label": "Security Deposit Reduction Cost",
             "amount": "285.71 €"},
            {"label": "Skipper (+ food allowance)",
             "amount": "1,400.00 €"},
        ],
    },

    # Equipment / feature pills (comma-separated; edit as needed)
    "highlights_json": [],

    # No images yet — user will add via WP admin media library
    "images_json": [],
}

# ─────────────────────────────────────────────────────────────────────────────

def _env(key: str) -> str:
    val = os.environ.get(key, "")
    if not val:
        print(f"ERROR: {key} not set. Check your .env file.", file=sys.stderr)
        sys.exit(1)
    return val


def main() -> None:
    wp_url  = _env("SAILSCANNER_WP_URL").rstrip("/")
    wp_user = _env("SAILSCANNER_WP_USER")
    wp_pass = _env("SAILSCANNER_WP_APP_PASSWORD").replace(" ", "")

    from urllib.parse import urlparse
    parsed   = urlparse(wp_url)
    site_url = f"{parsed.scheme}://{parsed.netloc}"
    endpoint = f"{site_url}/wp-json/wp/v2/ss_proposal_yacht"

    auth    = base64.b64encode(f"{wp_user}:{wp_pass}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type":  "application/json",
        "User-Agent":    USER_AGENT,
    }

    payload: dict = {
        "title":  YACHT["title"],
        "status": "publish",
        "display_name":    YACHT["display_name"],
        "year":            YACHT.get("year", 0),
        "length_m":        YACHT.get("length_m", 0),
        "cabins":          YACHT.get("cabins", 0),
        "berths":          YACHT.get("berths", 0),
        "country":         YACHT.get("country", ""),
        "region":          YACHT.get("region", ""),
        "base_name":       YACHT.get("base_name", ""),
        "specs_json":      YACHT.get("specs_json", []),
        "charter_json":    YACHT.get("charter_json", {}),
        "prices_json":     YACHT.get("prices_json", {}),
        "highlights_json": YACHT.get("highlights_json", []),
        "images_json":     YACHT.get("images_json", []),
    }

    print(f"POST {endpoint}", file=sys.stderr)
    resp = requests.post(endpoint, json=payload, headers=headers, timeout=30)
    if not resp.ok:
        print(f"HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    data      = resp.json()
    post_id   = data.get("id")
    post_link = data.get("link", "")
    print(f"\n✓ Yacht created successfully!")
    print(f"  Post ID : {post_id}")
    print(f"  Edit URL: {site_url}/wp-admin/post.php?post={post_id}&action=edit")
    print(f"  View URL: {post_link}")


if __name__ == "__main__":
    main()
