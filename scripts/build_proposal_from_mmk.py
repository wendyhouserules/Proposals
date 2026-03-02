#!/usr/bin/env python3
"""
Build a SailScanner proposal payload from MMK Booking Manager HTML export(s).
Outputs JSON suitable for proposal_import.py (or uploads directly with --upload).

Usage:
  python scripts/build_proposal_from_mmk.py --input examples/mmk-nik-2.html --type skippered
  python scripts/build_proposal_from_mmk.py --input examples/mmk-nik-2.html --type bareboat --upload

Requires: beautifulsoup4 (for parser). With --upload: requests, python-dotenv.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

# Add project root and examples to path so we can import the email block parsers
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
_examples = _project_root / "examples"
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
if str(_examples) not in sys.path:
    sys.path.insert(0, str(_examples))
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))


def _format_money(m: Any) -> str:
    """Format Money-like object (has .format()) for display; else return empty string."""
    if m is None:
        return ""
    if hasattr(m, "format") and callable(getattr(m, "format")):
        return m.format()
    return str(m).strip() or ""


def _upsize_mmk_url(url: str, target_width: int = 1200) -> str:
    """
    Replace the width= parameter in an MMK CDN image URL to get a larger version.
    e.g. ...image.jpg?name=FILE&width=310 → ...image.jpg?name=FILE&width=1200
    Non-MMK URLs are returned unchanged.
    """
    if not url or "booking-manager.com" not in url or "image.jpg" not in url:
        return url
    return re.sub(r"([?&]width=)\d+", rf"\g<1>{target_width}", url)


def _fetch_yacht_gallery(more_info_url: str, max_images: int = 20) -> list[str]:
    """
    Fetch the MMK YachtDetails page for a yacht and return all full-resolution image URLs.

    Constructs the YachtDetails URL from the company ID and yacht ID embedded in the
    price-quote more-info URL (view=Event&companyid=N&priceQuoteReservationId=YACHTID_...).

    Requires: requests, beautifulsoup4.
    Returns empty list on any error so the caller falls back gracefully.
    """
    if not more_info_url:
        return []
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        print("  Warning: requests/beautifulsoup4 not installed; cannot fetch gallery.", file=sys.stderr)
        return []

    try:
        parsed = urlparse(more_info_url)
        qs = parse_qs(parsed.query)
        company_id = (qs.get("companyid") or [""])[0]

        # Yacht ID is the first segment of priceQuoteReservationId  (e.g. "4692431734603380_...")
        pqrid = (qs.get("priceQuoteReservationId") or [""])[0]
        yacht_id = pqrid.split("_")[0] if pqrid else ""

        # Also try to get dateFrom/dateTo so the details page shows the right prices
        date_from = (qs.get("dateFrom") or [""])[0]
        date_to   = (qs.get("dateTo") or [""])[0]

        if not company_id or not yacht_id:
            print(f"  Warning: could not extract company/yacht ID from: {more_info_url}", file=sys.stderr)
            return []

        details_url = (
            f"https://www.booking-manager.com/wbm2/page.html"
            f"?view=YachtDetails&addMargins=true&templateType=responsive"
            f"&companyid={company_id}&yachtId={yacht_id}&setlang=en"
        )
        if date_from:
            details_url += f"&dateFrom={date_from}"
        if date_to:
            details_url += f"&dateTo={date_to}"

        print(f"  Fetching gallery: {details_url}", file=sys.stderr)
        resp = requests.get(
            details_url,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SailScanner/1.0)"},
        )
        resp.raise_for_status()
    except Exception as exc:
        print(f"  Warning: could not fetch yacht details page: {exc}", file=sys.stderr)
        return []

    # Base for building absolute URLs from relative bmdoc/ paths.
    wbm2_base = "https://www.booking-manager.com/wbm2/"

    soup = BeautifulSoup(resp.text, "html.parser")
    seen: set[str] = set()
    images: list[str] = []
    layout_url: str = ""
    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src:
            continue

        # Normalise to absolute URL.
        if src.startswith("bmdoc/"):
            src = wbm2_base + src
        elif "booking-manager.com" not in src:
            continue  # unrelated image (icons, logos, etc.)

        # Upsize to 1200px wide (works for both bmdoc/*.webp and legacy image.jpg CDN).
        src = re.sub(r"([?&]width=)\d+", r"\g<1>1200", src)

        # Detect boat-drawing / deck-plan images — keep first as layout, skip rest.
        alt = (img.get("alt") or "").lower()
        fname = src.split("?")[0].rsplit("/", 1)[-1].lower()
        is_layout = (
            "layout" in alt or "drawing" in alt
            or "drawing" in fname or "layout" in fname
            or "plano" in fname or fname.startswith("plan")
        )
        if is_layout:
            if not layout_url:
                layout_url = src
            continue  # never add to main photo list

        if src not in seen:
            seen.add(src)
            images.append(src)
        if len(images) >= max_images:
            break

    print(f"  Found {len(images)} gallery images" + (", 1 deck plan." if layout_url else "."), file=sys.stderr)
    return images, layout_url


def yacht_entry_to_ss_data(y: Any, fetched_gallery: list[str] | None = None, layout_image_url: str | None = None) -> dict[str, Any]:
    """Convert a YachtEntry (from build_email_block or build_email_block_skippered) to ss_yacht_data item."""
    # Display name: use model (make) not boat name, to avoid leaking supplier identity
    display_name = (y.model or y.name or "Yacht").strip()
    if not display_name:
        display_name = "Yacht"

    # Images: prefer fetched full-resolution gallery; otherwise upsize email thumbnails.
    if fetched_gallery:
        images_json = fetched_gallery
    else:
        # Upsize the small email thumbnails (width=310) to a presentable size (width=1200).
        images_json = [_upsize_mmk_url(u, 1200) for u in (list(y.image_urls)[:10] if y.image_urls else [])]

    # Highlights from equipment tags
    highlights_json = list(y.equipment_tags) if getattr(y, "equipment_tags", None) else []

    # Parse base_location into base_name / country / region if possible (e.g. "Italy, Sardinia / Portisco / Cala dei Sardi")
    base_name = getattr(y, "base_location", None) or ""
    country = ""
    region = ""
    if base_name:
        parts = [p.strip() for p in base_name.split(",")]
        if len(parts) >= 1:
            country = parts[0]
        if len(parts) >= 2:
            # Second part might be "Sardinia / Portisco / Cala dei Sardi"
            rest = parts[1]
            if " / " in rest:
                region = rest.split(" / ")[0].strip()
                base_name = rest.split(" / ", 1)[1].strip() if " / " in rest else rest
            else:
                region = rest

    def safe_int(v: Any) -> int:
        if v is None:
            return 0
        if isinstance(v, int):
            return v
        s = str(v).strip()
        m = re.search(r"\d+", s)
        return int(m.group(0)) if m else 0

    def safe_float(v: Any) -> float:
        if v is None:
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        m = re.search(r"[\d.]+", s.replace(",", "."))
        return float(m.group(0)) if m else 0.0

    # Specs for proposal-yacht page (label/value pairs)
    specs_json: list[dict[str, str]] = []
    for label, val in [
        ("Year", getattr(y, "year", None)),
        ("Length", getattr(y, "length", None)),
        ("Berths", getattr(y, "berths", None)),
        ("Cabins", getattr(y, "cabins", None)),
        ("WC / Shower", getattr(y, "wc_shower", None)),
        ("Mainsail", getattr(y, "mainsail", None)),
        ("Base", getattr(y, "base_location", None)),
    ]:
        if val is not None and str(val).strip():
            specs_json.append({"label": label, "value": str(val).strip()})

    # Prices: full breakdown for JSON (front-end can show base + discounts + key optionals only if desired)
    prices_json: dict[str, Any] = {}
    charter_net = getattr(y, "charter_price_net", None)
    if charter_net:
        prices_json["charter_price"] = _format_money(charter_net)
    base_price = getattr(y, "base_price", None)
    if base_price:
        prices_json["base_price"] = _format_money(base_price)
    # Discounts with labels (e.g. Early booking, Out of season) so we know where the discount came from
    discount_list = getattr(y, "discount_items", None) or []
    if discount_list:
        prices_json["discounts"] = [
            {"label": str(lbl).strip() or "Discount", "amount": _format_money(amt)}
            for lbl, amt in discount_list
        ]
    # Mandatory extras (advance + base) — full list in JSON
    mand_adv = getattr(y, "mandatory_advance_items", None) or []
    mand_base = getattr(y, "mandatory_base_items", None) or []
    if mand_adv:
        prices_json["mandatory_advance"] = [
            {"label": str(lbl).strip(), "amount": _format_money(amt)}
            for lbl, amt in mand_adv
        ]
    if mand_base:
        prices_json["mandatory_base"] = [
            {"label": str(lbl).strip(), "amount": _format_money(amt)}
            for lbl, amt in mand_base
        ]
    # Optional extras (full list; front-end can highlight skipper, chef, etc.)
    optional_list = getattr(y, "optional_items", None) or getattr(y, "optional_extra_items", []) or []
    if optional_list:
        prices_json["optional_extras"] = [
            {"label": str(lbl).strip(), "amount": _format_money(amt)}
            for lbl, amt in optional_list
        ]

    # Charter details: base, dates, check-in/out times (from email parser when available)
    charter_json: dict[str, Any] = {}
    raw_base = getattr(y, "base_location", None)
    if raw_base:
        charter_json["base"] = str(raw_base).strip()
    date_from = getattr(y, "date_from_str", None)
    if date_from:
        charter_json["date_from"] = str(date_from).strip()
    date_to = getattr(y, "date_to_str", None)
    if date_to:
        charter_json["date_to"] = str(date_to).strip()
    checkin = getattr(y, "check_in_time", None)
    if checkin:
        charter_json["checkin"] = str(checkin).strip()
    checkout = getattr(y, "check_out_time", None)
    if checkout:
        charter_json["checkout"] = str(checkout).strip()

    out: dict[str, Any] = {
        "display_name": display_name,
        "model": (y.model or "").strip() or None,
        "year": safe_int(getattr(y, "year", None)),
        "length_m": safe_float(getattr(y, "length", None)) if getattr(y, "length", None) else None,
        "cabins": safe_int(getattr(y, "cabins", None)),
        "berths": safe_int(getattr(y, "berths", None)),
        "base_name": base_name or None,
        "country": country or None,
        "region": region or None,
        "images_json": images_json,
        "highlights_json": highlights_json,
    }
    if specs_json:
        out["specs_json"] = specs_json
    if prices_json:
        out["prices_json"] = prices_json
    if charter_json:
        out["charter_json"] = charter_json
    if layout_image_url:
        out["layout_image_url"] = layout_image_url
    return out


def parse_mmk_file(path: Path, for_skippered: bool) -> list[Any]:
    """Parse MMK HTML file and return list of YachtEntry."""
    try:
        if for_skippered:
            from build_email_block_skippered import parse_file
        else:
            from build_email_block import parse_file
    except ModuleNotFoundError as e:
        if "bs4" in str(e):
            print("Install beautifulsoup4: pip install beautifulsoup4", file=sys.stderr)
        raise
    return parse_file(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build SailScanner proposal JSON from MMK HTML export(s)."
    )
    parser.add_argument(
        "--input",
        "-i",
        dest="inputs",
        action="append",
        required=True,
        help="Path to MMK HTML file(s). Can be repeated.",
    )
    parser.add_argument(
        "--type",
        "-t",
        choices=("bareboat", "skippered"),
        default="bareboat",
        help="Charter type: bareboat or skippered (affects parsing).",
    )
    parser.add_argument(
        "--intro",
        help="Path to HTML file for intro_html, or leave default.",
    )
    parser.add_argument(
        "--itinerary",
        help="Path to HTML file for itinerary_html.",
    )
    parser.add_argument(
        "--notes",
        help="Path to HTML file for notes_html.",
    )
    parser.add_argument(
        "--lead",
        "-l",
        help="Path to lead JSON file (answers, contact, etc.) for intro and Your Requirements. Optional.",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Write proposal JSON to this path. Default: stdout or proposal_from_mmk.json if --upload.",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="After building JSON, POST to WordPress (same as proposal_import.py) and print proposal URL.",
    )
    parser.add_argument(
        "--fetch-images",
        action="store_true",
        dest="fetch_images",
        help=(
            "Fetch the full gallery from each yacht's MMK details page (up to 20 photos at 1200px). "
            "Requires internet access and requests+beautifulsoup4. "
            "Without this flag, the 2 email thumbnails are still upsized to 1200px."
        ),
    )
    args = parser.parse_args()

    for_skippered = args.type == "skippered"
    all_yachts: list[Any] = []
    for inp in args.inputs:
        path = Path(inp).expanduser()
        if not path.is_absolute():
            path = _project_root / path
        if not path.exists():
            print(f"Warning: {path} not found, skipping.", file=sys.stderr)
            continue
        all_yachts.extend(parse_mmk_file(path, for_skippered))

    if not all_yachts:
        print("No yachts parsed. Check input HTML.", file=sys.stderr)
        sys.exit(1)

    yacht_data = []
    for y in all_yachts:
        fetched_photos: list[str] = []
        fetched_layout: str = ""
        if args.fetch_images and getattr(y, "more_info_url", None):
            print(f"Fetching gallery for: {y.model or y.name}", file=sys.stderr)
            fetched_photos, fetched_layout = _fetch_yacht_gallery(y.more_info_url)
        yacht_data.append(yacht_entry_to_ss_data(
            y,
            fetched_gallery=fetched_photos or None,
            layout_image_url=fetched_layout or None,
        ))
    yacht_data = [y for y in yacht_data if y.get("display_name")]

    def read_optional(path_arg: str | None) -> str:
        if not path_arg:
            return ""
        p = Path(path_arg).expanduser()
        if not p.is_absolute():
            p = _project_root / p
        if p.exists():
            return p.read_text(encoding="utf-8", errors="ignore").strip()
        return ""

    intro_html = read_optional(args.intro)
    if not intro_html:
        intro_html = (
            "<p>Hi, here are your charter options for the dates and area you requested. "
            "We've selected yachts that match your requirements.</p>"
            "<p>Click <strong>View details</strong> on any yacht to see the full specification and gallery.</p>"
        )
    itinerary_html = read_optional(args.itinerary)
    notes_html = read_optional(args.notes)
    if not notes_html:
        notes_html = (
            "<p>This proposal is valid for 14 days. Contact us to confirm availability and secure your booking.</p>"
        )

    lead_data: dict[str, Any] = {}
    if args.lead:
        lead_path = Path(args.lead).expanduser()
        if not lead_path.is_absolute():
            lead_path = _project_root / lead_path
        if lead_path.exists():
            try:
                lead_data = json.loads(lead_path.read_text(encoding="utf-8"))
                if not isinstance(lead_data, dict):
                    lead_data = {}
            except (json.JSONDecodeError, OSError) as e:
                print(f"Warning: could not read lead file: {e}", file=sys.stderr)
        else:
            print(f"Warning: lead file not found: {lead_path}", file=sys.stderr)

    payload: dict[str, Any] = {
        "yachts": yacht_data,
        "intro_html": intro_html,
        "itinerary_html": itinerary_html,
        "notes_html": notes_html,
        "contact_whatsapp": "",
        "contact_email": "",
        "requirements": {},
    }
    if lead_data:
        payload["lead"] = lead_data

    out_path = args.output
    if args.upload:
        if not out_path:
            out_path = _project_root / "output_files" / "proposal_from_mmk.json"
        out_path = Path(out_path).expanduser()
        if not out_path.is_absolute():
            out_path = _project_root / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            from dotenv import load_dotenv
            load_dotenv(_project_root / ".env")
        except ImportError:
            pass
        import os
        os.chdir(_project_root)
        os.environ["SAILSCANNER_PROPOSAL_JSON"] = str(out_path)
        from proposal_import import main as run_import
        run_import()
        return

    json_str = json.dumps(payload, indent=2, ensure_ascii=False)
    if out_path:
        out_path = Path(out_path).expanduser()
        if not out_path.is_absolute():
            out_path = _project_root / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_str, encoding="utf-8")
        print(f"Wrote {out_path}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
