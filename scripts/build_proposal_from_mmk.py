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
from datetime import date, datetime, timezone
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

from live_proposal_builder import get_itinerary_url


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
    _charter_type_label = (getattr(y, "charter_type", None) or "").strip()
    if _charter_type_label:
        charter_json["charter_type_label"] = _charter_type_label
        if "crewed" in _charter_type_label.lower():
            charter_json["crewed"] = True

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


def _extract_yacht_id(more_info_url: str) -> str:
    """Return the MMK yachtId from a price-quote more_info_url, used for deduplication."""
    if not more_info_url:
        return ""
    _qs = parse_qs(urlparse(more_info_url).query)
    _pqrid = (_qs.get("priceQuoteReservationId") or [""])[0]
    return _pqrid.split("_")[0] if _pqrid else ""


def _build_charter_slot(y: Any) -> dict[str, str]:
    """Extract charter details (base, dates, times) from a YachtEntry as a slot dict."""
    slot: dict[str, str] = {}
    raw_base = getattr(y, "base_location", None)
    if raw_base:
        slot["base"] = str(raw_base).strip()
    date_from = getattr(y, "date_from_str", None)
    if date_from:
        slot["date_from"] = str(date_from).strip()
    date_to = getattr(y, "date_to_str", None)
    if date_to:
        slot["date_to"] = str(date_to).strip()
    checkin = getattr(y, "check_in_time", None)
    if checkin:
        slot["checkin"] = str(checkin).strip()
    checkout = getattr(y, "check_out_time", None)
    if checkout:
        slot["checkout"] = str(checkout).strip()
    return slot


def _yacht_charter_days(more_info_url: str) -> int | None:
    """
    Return the number of days in the yacht's charter period using millisecond timestamps
    embedded in its more_info_url.

    MMK "more info" URLs encode dates in two ways:
      1. Top-level params: &dateFrom=MS&dateTo=MS  (used on YachtDetails pages)
      2. Inside priceQuoteReservationId: YACHTID_DATEFROM_DATETO_...  (used on Event/moreInfo pages)

    Both are tried; the first that yields parseable timestamps wins.
    Uses round() to handle check-in/check-out time-of-day differences gracefully.
    """
    if not more_info_url:
        return None
    qs = parse_qs(urlparse(more_info_url).query)

    # Strategy 1: top-level dateFrom / dateTo params (YachtDetails URLs).
    df_ms = (qs.get("dateFrom") or [""])[0]
    dt_ms = (qs.get("dateTo")   or [""])[0]

    # Strategy 2: extract from priceQuoteReservationId segments (Event/moreInfo URLs).
    # Format: YACHTID_DATEFROM_DATETO_...
    if not df_ms or not dt_ms:
        pqrid = (qs.get("priceQuoteReservationId") or [""])[0]
        if pqrid:
            parts = pqrid.split("_")
            if len(parts) >= 3:
                df_ms = parts[1]
                dt_ms = parts[2]

    if not df_ms or not dt_ms:
        return None
    try:
        dt_from = datetime.fromtimestamp(int(df_ms) / 1000, tz=timezone.utc)
        dt_to   = datetime.fromtimestamp(int(dt_ms) / 1000, tz=timezone.utc)
        return round((dt_to - dt_from).total_seconds() / 86400)
    except (ValueError, OSError, OverflowError):
        return None


def _scale_price_str(price_str: str, lead_days: int, yacht_days: int) -> str:
    """
    Scale a formatted price string (e.g. '3,445.00 €') by lead_days / yacht_days.
    Returns the original string unchanged if parsing fails.
    """
    if not price_str or yacht_days == 0:
        return price_str
    sym_match = re.search(r"[€$£¥]", price_str)
    symbol    = sym_match.group(0) if sym_match else ""
    num_str   = re.sub(r"[^\d.]", "", price_str.replace(",", ""))
    try:
        val = float(num_str)
    except ValueError:
        return price_str
    scaled = val * lead_days / yacht_days
    formatted = f"{scaled:,.2f}"
    return f"{formatted} {symbol}".strip() if symbol else formatted


def _fmt_lead_date(iso: str) -> str:
    """Convert ISO date '2026-07-30' → '30 July 2026'."""
    try:
        d = date.fromisoformat(iso)
        return f"{d.day} {d.strftime('%B %Y')}"
    except (ValueError, AttributeError):
        return iso


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
    parser.add_argument(
        "--group-by-base",
        action="store_true",
        dest="group_by_base",
        help=(
            "Group yacht cards by their charter base in the proposal. "
            "Each base gets its own sub-heading and anchor, with clickable "
            "sub-nav items in the sidebar under 'Yacht Selection'."
        ),
    )
    parser.add_argument(
        "--prorate",
        action="store_true",
        dest="prorate",
        help=(
            "When --lead is provided, override yacht dates to match lead dates AND "
            "scale prices proportionally when the MMK quote is for 7 days and the "
            "lead is for a different duration. Can also be enabled permanently by "
            "setting SAILSCANNER_PRORATE=1 in your .env file."
        ),
    )
    parser.add_argument(
        "--no-prorate",
        action="store_true",
        dest="no_prorate",
        help="Explicitly disable pro-rating and date override even if SAILSCANNER_PRORATE=1 is set.",
    )
    parser.add_argument(
        "--no-date-override",
        action="store_true",
        dest="no_date_override",
        help=(
            "When --lead + --prorate are active, skip overriding yacht dates "
            "but still apply price scaling."
        ),
    )
    args = parser.parse_args()

    # Load .env early so SAILSCANNER_PRORATE can influence behaviour.
    import os
    try:
        from dotenv import load_dotenv
        load_dotenv(_project_root / ".env")
    except ImportError:
        pass

    # Resolve effective prorate flag:
    #   --no-prorate  → always off
    #   --prorate     → always on
    #   neither       → follow SAILSCANNER_PRORATE env var (default: off)
    _env_prorate = os.environ.get("SAILSCANNER_PRORATE", "0").strip() in ("1", "true", "yes")
    if args.no_prorate:
        _effective_prorate = False
    elif args.prorate:
        _effective_prorate = True
    else:
        _effective_prorate = _env_prorate

    # Resolve effective date-override flag:
    #   --no-date-override           → always off for this run
    #   SAILSCANNER_DATE_OVERRIDE=0  → off by default
    #   neither                      → on (default when pro-rating is active)
    _env_date_override = os.environ.get("SAILSCANNER_DATE_OVERRIDE", "1").strip() not in ("0", "false", "no")
    _effective_date_override = False if args.no_date_override else _env_date_override

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

    # ── Load lead data early so date/price adjustments are available in the loop ──
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

    # Compute lead charter duration for date override + price pro-rating.
    lead_days: int | None = None
    lead_from_str: str = ""
    lead_to_str: str = ""
    _answers   = lead_data.get("answers", {}) if lead_data else {}
    _ld_dates  = _answers.get("dates", {}) if isinstance(_answers, dict) else {}
    _start_iso = _ld_dates.get("start", "") if isinstance(_ld_dates, dict) else ""
    _end_iso   = _ld_dates.get("end",   "") if isinstance(_ld_dates, dict) else ""
    if _start_iso and _end_iso:
        try:
            _d_start = date.fromisoformat(_start_iso)
            _d_end   = date.fromisoformat(_end_iso)
            # Inclusive: July 30 → Aug 2 = (3 days diff) + 1 = 4 days
            lead_days = (_d_end - _d_start).days + 1
            lead_from_str = _fmt_lead_date(_start_iso)
            lead_to_str   = _fmt_lead_date(_end_iso)
            print(
                f"  Lead dates: {lead_from_str} → {lead_to_str} ({lead_days} days)",
                file=sys.stderr,
            )
        except ValueError:
            pass

    # Group entries by yachtId so the same physical boat at multiple bases becomes one entry.
    # Entries without a parseable yachtId are treated as unique (keyed by index).
    from collections import OrderedDict
    yacht_groups: OrderedDict[str, list[Any]] = OrderedDict()
    for y in all_yachts:
        more_info = getattr(y, "more_info_url", None) or ""
        yid = _extract_yacht_id(more_info) if more_info else ""
        group_key = yid if yid else f"_noid_{len(yacht_groups)}"
        if group_key not in yacht_groups:
            yacht_groups[group_key] = []
        yacht_groups[group_key].append(y)

    yacht_data = []
    for group_key, group in yacht_groups.items():
        primary = group[0]
        label = primary.model or getattr(primary, "name", "?")
        if len(group) > 1:
            print(f"  Merging {len(group)} slots for: {label} (yachtId={group_key})", file=sys.stderr)

        fetched_photos: list[str] = []
        fetched_layout: str = ""
        if args.fetch_images and getattr(primary, "more_info_url", None):
            print(f"Fetching gallery for: {label}", file=sys.stderr)
            fetched_photos, fetched_layout = _fetch_yacht_gallery(primary.more_info_url)

        entry = yacht_entry_to_ss_data(
            primary,
            fetched_gallery=fetched_photos or None,
            layout_image_url=fetched_layout or None,
        )

        # When the same boat appears multiple times, embed all charter slots so the
        # front-end can show every available base/date without creating duplicate cards.
        if len(group) > 1:
            slots = [_build_charter_slot(y) for y in group]
            slots = [s for s in slots if s]  # drop any empties
            # Deduplicate by (base, date_from, date_to) fingerprint.
            seen_fps: set[str] = set()
            unique_slots = []
            for s in slots:
                fp = f"{s.get('base','')}|{s.get('date_from','')}|{s.get('date_to','')}"
                if fp not in seen_fps:
                    seen_fps.add(fp)
                    unique_slots.append(s)
            slots = unique_slots
            if slots:
                if "charter_json" not in entry:
                    entry["charter_json"] = {}
                entry["charter_json"]["slots"] = slots

        # ── Lead date override + price pro-rating ─────────────────────────────
        # Only runs when --prorate (or SAILSCANNER_PRORATE=1) is active.
        if lead_days is not None and lead_from_str and _effective_prorate:
            # How many days was this yacht's charter originally listed for?
            _more_info = getattr(primary, "more_info_url", None) or ""
            yacht_days = _yacht_charter_days(_more_info) if _more_info else None
            print(
                f"  {label}: yacht_days={yacht_days}, lead_days={lead_days}"
                + (" → pro-rating" if yacht_days == 7 and lead_days != 7 else " → no pro-rating"),
                file=sys.stderr,
            )

            # Override dates in charter_json top-level and every slot.
            # Skipped when SAILSCANNER_DATE_OVERRIDE=0 or --no-date-override is passed.
            if _effective_date_override:
                def _override_dates(c: dict[str, Any]) -> None:
                    c["date_from"] = lead_from_str
                    c["date_to"]   = lead_to_str

                if "charter_json" in entry:
                    _override_dates(entry["charter_json"])
                    if isinstance(entry["charter_json"].get("slots"), list):
                        for _slot in entry["charter_json"]["slots"]:
                            _override_dates(_slot)

            # Pro-rate only when the yacht was priced for exactly 7 days and the lead
            # wants a different duration.
            if yacht_days == 7 and lead_days != 7 and "prices_json" in entry:
                _prices = entry["prices_json"]

                def _scale_field(field: str) -> None:
                    if field in _prices and isinstance(_prices[field], str):
                        _old = _prices[field]
                        _prices[field] = _scale_price_str(_old, lead_days, 7)
                        print(
                            f"  Pro-rated {label} {field}: {_old} → {_prices[field]}"
                            f" ({lead_days}/7)",
                            file=sys.stderr,
                        )

                _scale_field("charter_price")
                _scale_field("base_price")
                # Discount amounts are proportional to the base price.
                if isinstance(_prices.get("discounts"), list):
                    for _item in _prices["discounts"]:
                        if isinstance(_item, dict) and "amount" in _item:
                            _item["amount"] = _scale_price_str(_item["amount"], lead_days, 7)

                # Pro-rate per-day crew costs (skipper, captain, crew, hostess).
                # Fixed one-off costs (cleaning packs, starter kits, damage deposits,
                # park fees, etc.) are intentionally left unscaled.
                _CREW_KEYWORDS = (
                    "skipper", "skiper", "captain", "crew", "hostess",
                    "deckhand", "tour leader",
                )

                def _is_crew_item(item_label: str) -> bool:
                    lo = item_label.lower()
                    return any(kw in lo for kw in _CREW_KEYWORDS)

                for _list_key in ("mandatory_advance", "mandatory_base", "optional_extras"):
                    for _item in _prices.get(_list_key) or []:
                        if not isinstance(_item, dict):
                            continue
                        _item_label = _item.get("label", "")
                        if _is_crew_item(_item_label) and "amount" in _item:
                            _old_amt = _item["amount"]
                            _item["amount"] = _scale_price_str(_old_amt, lead_days, 7)
                            print(
                                f"  Pro-rated {label} [{_list_key}] '{_item_label}': "
                                f"{_old_amt} → {_item['amount']} ({lead_days}/7)",
                                file=sys.stderr,
                            )

                _prices["prorated_note"] = (
                    f"Estimated {lead_days}-day price (pro-rated from 7-day rate)"
                )

        # ── Unified crew-service injection ────────────────────────────────────
        # Handles skipper (auto from charterType), chef, hostess, and other
        # services in a single pass to avoid duplication and coordinate notes.
        #
        # Note values:
        #   "Skippered charter" — skipper implied by charterType == "skippered"
        #   "Requested"         — explicitly in lead's crewServices
        #   "Included"          — service bundled in mandatory pack (crewed charter)
        #
        # (lead_key, display_label, [match keywords], note_override_or_None)
        _crew_service_map: list[tuple[str, str, list[str], str | None]] = [
            ("skipper",         "Skipper",          ["skipper", "skiper", "captain"], "Skippered charter"),
            ("chef",            "Chef",             ["chef", "cook"],                 None),
            ("cook",            "Chef / Cook",      ["chef", "cook"],                 None),
            ("hostess",         "Hostess",          ["hostess", "host"],              None),
            ("provisioning",    "Provisioning",     ["provisioning", "provision"],    None),
            ("airportTransfer", "Airport Transfer", ["airport", "transfer"],          None),
        ]
        _charter_type_str = (
            (lead_data.get("answers") or {}).get("charterType") or ""
        ).strip().lower()
        _lead_services: dict[str, Any] = dict(
            (lead_data.get("answers") or {}).get("crewServices") or {}
        )
        # Skippered charter always implies a skipper is needed, even when crewServices
        # is empty or doesn't include "skipper" explicitly.
        if _charter_type_str == "skippered":
            _lead_services.setdefault("skipper", True)

        _yacht_is_crewed = bool(entry.get("charter_json", {}).get("crewed"))

        if (_lead_services or _charter_type_str == "skippered") and "prices_json" in entry:
            _opt = entry["prices_json"].setdefault("optional_extras", [])
            _mandatory_items = (
                (entry["prices_json"].get("mandatory_advance") or [])
                + (entry["prices_json"].get("mandatory_base") or [])
            )
            # Normalised mandatory labels for keyword matching.
            _mandatory_label_norms = [
                (item.get("label") or "").lower()
                for item in _mandatory_items
                if isinstance(item, dict)
            ]
            # Track display labels already handled to avoid duplicate placeholders
            # (e.g. both "chef" and "cook" keys mapping to the same optional item).
            _handled_labels: set[str] = set()

            for _svc_key, _svc_label, _match_kws, _note_override in _crew_service_map:
                if not _lead_services.get(_svc_key):
                    continue
                if _svc_label in _handled_labels:
                    continue

                # Determine the appropriate note for this service.
                _note = _note_override if _note_override else "Requested"

                # ── Mandatory check ──────────────────────────────────────────
                _in_mandatory = any(
                    kw in lbl
                    for lbl in _mandatory_label_norms
                    for kw in _match_kws
                )
                if _in_mandatory:
                    if _yacht_is_crewed:
                        # Service is bundled in the crewed service pack — add an
                        # explicit "Included" line so the client can see each
                        # requested service is covered.
                        _opt.append({
                            "label":  _svc_label,
                            "amount": "",
                            "note":   "Included",
                        })
                        _handled_labels.add(_svc_label)
                        print(
                            f"  Added '{_svc_label}' as 'Included' (crewed) for {label}",
                            file=sys.stderr,
                        )
                    else:
                        _handled_labels.add(_svc_label)
                        print(
                            f"  Skipping '{_svc_label}' for {label} — already mandatory",
                            file=sys.stderr,
                        )
                    continue

                # ── Optional extras check ────────────────────────────────────
                _matched_opt = next(
                    (item for item in _opt
                     if isinstance(item, dict)
                     and any(kw in (item.get("label") or "").lower() for kw in _match_kws)),
                    None,
                )
                if _matched_opt is not None:
                    if not _matched_opt.get("note"):
                        _matched_opt["note"] = _note
                        print(
                            f"  Marked '{_matched_opt['label']}' as '{_note}' for {label}",
                            file=sys.stderr,
                        )
                    _handled_labels.add(_svc_label)
                    continue

                # ── Fallback: add placeholder ────────────────────────────────
                _opt.append({
                    "label":  _svc_label,
                    "amount": "Price on request",
                    "note":   _note,
                })
                _handled_labels.add(_svc_label)
                print(
                    f"  Added '{_svc_label}' ({_note}) placeholder for {label}",
                    file=sys.stderr,
                )

        yacht_data.append(entry)

    yacht_data = [y for y in yacht_data if y.get("display_name")]

    # Sort yachts cheapest-first by charter_price (the net price after discounts).
    # Yachts without a parseable price sort to the end.
    # Format is "3,956.82 €" — comma is thousands separator, period is decimal point.
    def _price_sort_key(y: dict[str, Any]) -> float:
        raw = (y.get("prices_json") or {}).get("charter_price", "")
        # Keep only digits, commas, and periods; then drop commas (thousands separators).
        cleaned = re.sub(r"[^\d,.]", "", str(raw).strip()).replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return float("inf")

    yacht_data.sort(key=_price_sort_key)

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

    # Look up itinerary URL from lead's region/country
    _itinerary_url = ""
    if lead_data:
        _answers = lead_data.get("answers") or {}
        _itinerary_url = get_itinerary_url(
            _answers.get("region"),
            _answers.get("country"),
        )

    payload: dict[str, Any] = {
        "yachts": yacht_data,
        "intro_html": intro_html,
        "itinerary_html": itinerary_html,
        "notes_html": notes_html,
        "contact_whatsapp": "",
        "contact_email": "",
        "requirements": {},
        "group_by_base": args.group_by_base,
    }
    if _itinerary_url:
        payload["ss_itinerary_link_url"] = _itinerary_url
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
