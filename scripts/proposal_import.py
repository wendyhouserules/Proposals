#!/usr/bin/env python3
"""
SailScanner Proposal Importer (v1) — uses WordPress core REST (wp/v2) with Basic auth only.

Proposal yacht picks are sent as ss_yacht_data; the server creates ss_proposal_yacht posts and links them to the proposal.

Usage:
  1. Parse MMK/NauSYS email HTML (extend build_email_block_*.py to output JSON).
  2. Create proposal via POST wp/v2/ss_proposal with ss_yacht_data (and optional intro, itinerary, etc.).
  3. Print proposal URL for WhatsApp/email.

Requires: requests. Auth: Application Password (Basic auth). No HMAC.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Load .env from project root (parent of scripts/)
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if load_dotenv is not None:
    load_dotenv(os.path.join(_project_root, ".env"))

# -----------------------------------------------------------------------------
# Config (env or override)
# -----------------------------------------------------------------------------
WP_BASE = os.environ.get("SAILSCANNER_WP_URL", "https://sailscanner.ai").rstrip("/")
if "/wp-json" in WP_BASE:
    parsed = urlparse(WP_BASE)
    WP_BASE = f"{parsed.scheme}://{parsed.netloc}"
WP_USER = os.environ.get("SAILSCANNER_WP_USER", "").strip().strip('"')
WP_APP_PASSWORD = os.environ.get("SAILSCANNER_WP_APP_PASSWORD", "").strip().strip('"')


def _basic_auth(user: str, password: str) -> str:
    import base64
    creds = f"{user}:{password}"
    return "Basic " + base64.b64encode(creds.encode()).decode()


# Avoid WAF blocks on default python-requests User-Agent
USER_AGENT = "Mozilla/5.0 (compatible; SailScanner-Proposals/1.0)"


def _headers(auth: tuple[str, str]) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
        "Authorization": _basic_auth(auth[0], auth[1]),
    }


def _post(path: str, payload: dict[str, Any], auth: tuple[str, str], timeout: int = 120) -> requests.Response:
    url = f"{WP_BASE}/wp-json/wp/v2{path}"
    # Use ensure_ascii=False so real UTF-8 chars (€, accented letters, etc.) are sent
    # directly in the body rather than as \uXXXX escape sequences, which can be
    # silently stripped by WAFs or server-side request sanitization.
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return requests.post(url, data=body, headers=_headers(auth), timeout=timeout)


_MAX_IMAGES_PER_YACHT = 12  # Keep payload lean; 12 photos is plenty for the gallery.


def _yacht_to_display_data(yacht: dict[str, Any]) -> dict[str, Any]:
    """Build yacht object for ss_yacht_data (server creates ss_proposal_yacht posts from this)."""
    keys = (
        "display_name", "model", "year", "length_m", "cabins", "berths",
        "base_name", "country", "region",
        "images_json", "highlights_json", "specs_json", "prices_json", "charter_json",
        "layout_image_url",
    )
    out = {k: yacht[k] for k in keys if k in yacht and yacht[k] is not None}
    # Trim the image list so large proposals don't balloon the payload.
    if "images_json" in out and isinstance(out["images_json"], list):
        out["images_json"] = out["images_json"][:_MAX_IMAGES_PER_YACHT]
    return out


def create_proposal(
    yacht_data: list[dict[str, Any]],
    *,
    auth: tuple[str, str],
    intro_html: str = "",
    itinerary_html: str = "",
    notes_html: str = "",
    contact_whatsapp: str = "",
    contact_email: str = "",
    requirements: dict[str, Any] | None = None,
    lead: dict[str, Any] | None = None,
    group_by_base: bool = False,
) -> dict[str, Any]:
    """Create ss_proposal via wp/v2 with ss_yacht_data (server creates ss_proposal_yacht posts)."""
    body: dict[str, Any] = {
        "status": "publish",
        "ss_yacht_data": yacht_data,
        "ss_intro_html": intro_html,
        "ss_itinerary_html": itinerary_html,
        "ss_notes_html": notes_html,
        "ss_contact_whatsapp": contact_whatsapp,
        "ss_contact_email": contact_email,
    }
    if requirements is not None:
        body["ss_requirements_json"] = (
            requirements if isinstance(requirements, dict) else json.loads(str(requirements))
        )
    if lead is not None and isinstance(lead, dict) and lead:
        body["ss_lead_json"] = lead
    if group_by_base:
        body["ss_group_by_base"] = True
    r = _post("/ss_proposal", body, auth)
    r.raise_for_status()
    return r.json()


def main() -> None:
    if not WP_USER or not WP_APP_PASSWORD:
        print("Set SAILSCANNER_WP_USER and SAILSCANNER_WP_APP_PASSWORD.", file=sys.stderr)
        sys.exit(1)

    auth = (WP_USER, WP_APP_PASSWORD)

    input_file = os.environ.get("SAILSCANNER_PROPOSAL_JSON")
    if not input_file or not os.path.isfile(input_file):
        print("No SAILSCANNER_PROPOSAL_JSON file. Example usage:", file=sys.stderr)
        print('  export SAILSCANNER_PROPOSAL_JSON=./scripts/proposal_payload_example.json', file=sys.stderr)
        print('  python scripts/proposal_import.py', file=sys.stderr)
        sys.exit(0)

    with open(input_file, encoding="utf-8") as f:
        data = json.load(f)

    yachts_list = data.get("yachts", [])
    if not yachts_list:
        print("No yachts in payload.", file=sys.stderr)
        sys.exit(1)

    # Build yacht data for proposal (server creates ss_proposal_yacht posts)
    yacht_data = [_yacht_to_display_data(y) for y in yachts_list]
    yacht_data = [y for y in yacht_data if y]

    if not yacht_data:
        print("No yacht data to include.", file=sys.stderr)
        sys.exit(1)

    # Create proposal with ss_yacht_data (and optional lead for intro/requirements)
    proposal_payload = {
        "intro_html": data.get("intro_html", ""),
        "itinerary_html": data.get("itinerary_html", ""),
        "notes_html": data.get("notes_html", ""),
        "contact_whatsapp": data.get("contact_whatsapp", ""),
        "contact_email": data.get("contact_email", ""),
        "requirements": data.get("requirements"),
        "lead": data.get("lead"),
        "group_by_base": bool(data.get("group_by_base", False)),
    }
    try:
        out = create_proposal(
            yacht_data,
            auth=auth,
            **{k: v for k, v in proposal_payload.items() if v is not None},
        )
    except requests.RequestException as e:
        print(f"Proposal create failed: {e}", file=sys.stderr)
        if hasattr(e, "response") and e.response is not None:
            resp = e.response
            print(f"  URL: {resp.url}", file=sys.stderr)
            print(f"  Status: {resp.status_code}", file=sys.stderr)
            print(resp.text[:500], file=sys.stderr)
        sys.exit(1)

    url = out.get("proposal_url", "")
    if not url and out.get("ss_token"):
        url = f"{WP_BASE}/proposals/{out['ss_token']}/"
    print(url)


if __name__ == "__main__":
    main()
