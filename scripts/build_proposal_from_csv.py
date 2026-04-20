#!/usr/bin/env python3
"""
Build a SailScanner proposal payload from the yacht database CSV + a lead JSON file.
Filters and price-matches yachts from yacht_database_full.csv based on the lead's
requirements (region, boat type, size, cabins, budget, dates) without needing MMK HTML.

Usage:
  python scripts/build_proposal_from_csv.py \
    --lead input_files/hollie-pollak.json \
    --output output_files/hollie-pollak-out.json

  python scripts/build_proposal_from_csv.py \
    --lead input_files/hollie-pollak.json \
    --upload

  python scripts/build_proposal_from_csv.py \
    --lead input_files/hollie-pollak.json \
    --no-filter \
    --output output_files/all-yachts.json

Requires: python-dotenv (for --upload).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

# ── Live pricing from portal search API (portal_live_search.py) ───────────────
# Imported lazily in main() so the module works even without portal credentials.
try:
    from portal_live_search import live_search_all as _live_search_all
    _LIVE_SEARCH_AVAILABLE = True
except ImportError:
    _LIVE_SEARCH_AVAILABLE = False

# ── Image cache (built by scripts/cache_yacht_images.py) ──────────────────────
# Maps yacht_id → {"images": [wp_url, ...], "layout": wp_url_or_""}
# Falls back gracefully to portal URLs when cache is absent or yacht is uncached.
_CACHE_PATH = Path(__file__).resolve().parent / "image_cache.json"
_IMAGE_CACHE: dict[str, dict] = {}
if _CACHE_PATH.exists():
    try:
        _IMAGE_CACHE = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Path setup — mirrors build_proposal_from_mmk.py conventions
# ---------------------------------------------------------------------------
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent

if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

# Import pure helpers from the existing MMK script rather than duplicating them.
# These have no side effects and do not pull in HTML/BS4 dependencies.
try:
    from build_proposal_from_mmk import (
        _fmt_lead_date,
        _scale_price_str,
        _upsize_mmk_url,
    )
except ImportError:
    # Fallback definitions if the sibling script isn't importable for some reason.
    def _fmt_lead_date(iso: str) -> str:  # type: ignore[misc]
        try:
            d = date.fromisoformat(iso)
            return f"{d.day} {d.strftime('%B %Y')}"
        except (ValueError, AttributeError):
            return iso

    def _scale_price_str(price_str: str, lead_days: int, yacht_days: int) -> str:  # type: ignore[misc]
        if not price_str or yacht_days == 0:
            return price_str
        sym_match = re.search(r"[€$£¥]", price_str)
        symbol = sym_match.group(0) if sym_match else ""
        num_str = re.sub(r"[^\d.]", "", price_str.replace(",", ""))
        try:
            val = float(num_str)
        except ValueError:
            return price_str
        scaled = val * lead_days / yacht_days
        formatted = f"{scaled:,.2f}"
        return f"{formatted} {symbol}".strip() if symbol else formatted

    def _upsize_mmk_url(url: str, target_width: int = 1200) -> str:  # type: ignore[misc]
        return re.sub(r"([?&]width=)\d+", rf"\g<1>{target_width}", url) if url else url


# ---------------------------------------------------------------------------
# Budget string → (min_eur, max_eur) weekly price range
# ---------------------------------------------------------------------------
_BUDGET_RANGES: dict[str, tuple[float, float]] = {
    "under-1k": (0, 1_000),
    "1-2k":     (0, 2_000),
    "2-3k":     (0, 3_000),
    "3-5k":     (0, 5_000),
    "5-7k":     (0, 7_000),
    "7-10k":    (0, 10_000),
    "10k+":     (0, float("inf")),
}

# Boat type → CSV Kind value
_BOAT_TYPE_MAP: dict[str, str | None] = {
    "monohull":  "Sail boat",
    "catamaran": "Catamaran",
    "any":       None,   # None means no Kind filter
    "sailboat":  "Sail boat",
    "sail":      "Sail boat",
}

# Size range string → (min_ft, max_ft)
def _parse_size_range(size_str: str) -> tuple[float, float]:
    """Convert a size band string to a (min_ft, max_ft) range."""
    if not size_str:
        return (0, float("inf"))
    size_str = size_str.strip().lower()
    if size_str.startswith("under-") or size_str.startswith("under "):
        val = re.search(r"\d+", size_str)
        return (0, float(val.group(0)) if val else float("inf"))
    if size_str.endswith("+"):
        val = re.search(r"\d+", size_str)
        return (float(val.group(0)) if val else 0, float("inf"))
    m = re.match(r"(\d+)\s*[-–]\s*(\d+)", size_str)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    # Single value — treat as exact
    val = re.search(r"\d+", size_str)
    if val:
        v = float(val.group(0))
        return (v, v)
    return (0, float("inf"))


# ---------------------------------------------------------------------------
# Price calendar lookup
# ---------------------------------------------------------------------------
def _parse_cal_date(s: str) -> date | None:
    """Parse DD.MM.YYYY to date, return None on failure."""
    try:
        return datetime.strptime(s.strip(), "%d.%m.%Y").date()
    except ValueError:
        return None


def price_for_dates(row: dict[str, str], lead_start: date | None) -> float | None:
    """
    Return the weekly charter price (€) for the lead's start date.

    Consults Price Calendar (JSON) first (exact weekly match).
    Falls back to Net Price (€) — the discounted charter price, NOT Rack Price.
    Returns None if no price can be determined.
    """
    cal_str = (row.get("Price Calendar (JSON)") or "").strip()
    if cal_str and lead_start is not None:
        try:
            calendar: list[dict] = json.loads(cal_str)
            for entry in calendar:
                d_from = _parse_cal_date(entry.get("from", ""))
                d_to   = _parse_cal_date(entry.get("to", ""))
                if d_from and d_to and d_from <= lead_start < d_to:
                    return float(entry["price"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass

    # Fall back to Net Price (€) — the client-facing discounted price.
    # Rack Price is the undiscounted rack rate; we never quote that directly.
    net_str = (row.get("Net Price (€)") or "").strip()
    if net_str:
        try:
            return float(net_str)
        except ValueError:
            pass
    return None


# ---------------------------------------------------------------------------
# Extras string parser
# ---------------------------------------------------------------------------
# Matches a price at the END of a string: ": 375.00 € per booking"
# The label may itself contain colons and semicolons (e.g. starter packs with
# contents listed inline). We accumulate semicolon-separated segments until one
# terminates with a price pattern, then emit the whole accumulated text as one item.
_EXTRAS_TAIL_PRICE_RE = re.compile(
    r":\s*(\d[\d,.]*\s*(?:[€$£¥]|EUR|USD|GBP)(?:\s+per\s+\w+)?)\s*$",
    re.IGNORECASE,
)


def parse_extras_str(extras_str: str) -> list[dict[str, str]]:
    """
    Parse a semicolon-delimited extras string into [{label, amount}] dicts.

    Handles multi-phrase items where the label itself contains semicolons, e.g.:
      "Starter pack TOMMY: Welcome gift; Bed linen; Final cleaning): 375.00 € per booking"
    treats the entire text as ONE item labelled "Starter pack TOMMY: Welcome gift;
    Bed linen; Final cleaning" with amount "375.00 € per booking".

    Simple items ("Final Cleaning: 120.00 € per booking") are parsed as normal.
    """
    if not extras_str or not extras_str.strip():
        return []

    items: list[dict[str, str]] = []
    segments = [s.strip() for s in extras_str.split(";") if s.strip()]
    pending: list[str] = []   # segments accumulated for current item

    for seg in segments:
        pending.append(seg)
        combined = "; ".join(pending)
        m = _EXTRAS_TAIL_PRICE_RE.search(combined)
        if m:
            # The accumulated text ends with a price — emit as one item.
            label = combined[: m.start()].strip().rstrip(")").strip()
            amount = m.group(1).strip()
            if label:
                items.append({"label": label, "amount": amount})
            pending = []

    # Any trailing segments with no price (rare) — emit label-only
    if pending:
        label = "; ".join(pending).strip().rstrip(")").strip()
        if label:
            items.append({"label": label, "amount": ""})

    return items


# ---------------------------------------------------------------------------
# CSV row → ss_yacht_data dict
# ---------------------------------------------------------------------------
def csv_row_to_ss_data(
    row: dict[str, str],
    price: float | None,
    lead_data: dict[str, Any],
    lead_from_str: str,
    lead_to_str: str,
    live_prices: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """Convert a CSV row into an ss_yacht_data dict (same schema as build_proposal_from_mmk.py)."""

    def _safe_int(v: str) -> int:
        m = re.search(r"\d+", str(v or ""))
        return int(m.group(0)) if m else 0

    def _safe_float(v: str) -> float:
        m = re.search(r"[\d.]+", str(v or "").replace(",", "."))
        return float(m.group(0)) if m else 0.0

    answers = lead_data.get("answers") or {}

    # ── Basic identity ────────────────────────────────────────────────────
    model        = (row.get("Model") or "").strip()
    display_name = model or (row.get("Yacht Name") or "Yacht").strip()
    year         = _safe_int(row.get("Year Built") or "")
    length_ft    = _safe_float(row.get("Length (ft)") or "")
    cabins       = _safe_int(row.get("Cabins") or "")
    berths       = _safe_int(row.get("Berths") or "")

    # ── Location ──────────────────────────────────────────────────────────
    base_name = (row.get("Base") or "").strip()
    region    = (row.get("Region") or "").strip()
    # Derive country from the yacht's region, not from the lead answers
    _region_to_country = {"Sardinia": "Italy", "Sicily": "Italy", "Marmaris": "Turkey",
                          "Balearic Islands": "Spain", "French Polynesia": "French Polynesia",
                          "Thailand": "Thailand", "Tortola": "British Virgin Islands"}
    country = _region_to_country.get(region, (answers.get("country") or "").strip())

    # ── Images ────────────────────────────────────────────────────────────
    # Priority order:
    #   1. Live search image URLs (publicly accessible, no auth, always fresh)
    #   2. WordPress cache (legacy — from old cache_yacht_images.py runs)
    #   3. CSV Photos URL column (auth-gated portal URLs — last resort, often blank)
    yacht_id_str = (row.get("Yacht ID") or "").strip()
    live         = (live_prices or {}).get(yacht_id_str) if yacht_id_str else None

    if live and live.get("image_url"):
        # Use live search image URLs — publicly accessible, no upload needed
        images_json: list[str] = [live["image_url"]]
        if live.get("interior_url"):
            images_json.append(live["interior_url"])
        layout_image_url: str = ""   # interior_url served inline; no separate layout slot needed
    else:
        cached = _IMAGE_CACHE.get(yacht_id_str)
        if cached:
            images_json      = [u for u in (cached.get("images") or []) if u]
            layout_image_url = cached.get("layout") or ""
        else:
            # Last resort: CSV Photos URL column — these are auth-gated portal URLs
            # and will likely be blank for clients, but better than nothing.
            photos_raw = row.get("Photos URL") or ""
            all_photos = [p.strip() for p in photos_raw.split("|") if p.strip()]
            images_json      = []
            layout_image_url = ""
            for url in all_photos:
                fname = url.split("?")[0].rsplit("/", 1)[-1].lower()
                is_layout = any(kw in fname for kw in ("layout", "drawing", "plano", "plan_", "deck"))
                if is_layout:
                    if not layout_image_url:
                        layout_image_url = url
                    continue
                if len(images_json) < 20:
                    images_json.append(url)

    # ── Highlights (nav + comfort equipment) ─────────────────────────────
    # Data uses commas as separators, not semicolons
    nav     = row.get("Nav Equipment") or ""
    comfort = row.get("Comfort Equipment") or ""
    highlights_json: list[str] = []
    for equipment_str in (nav, comfort):
        for item in equipment_str.split(","):
            cleaned = item.strip()
            if cleaned and len(cleaned) < 80:
                highlights_json.append(cleaned)

    # ── Specs ─────────────────────────────────────────────────────────────
    specs_json: list[dict[str, str]] = []
    for label, val in [
        ("Year",       str(year) if year else ""),
        ("Length",     f"{length_ft:.0f} ft" if length_ft else ""),
        ("Berths",     str(berths) if berths else ""),
        ("Cabins",     str(cabins) if cabins else ""),
        ("WC / Heads", (row.get("WC / Heads") or "").strip()),
        ("Base",       base_name),
    ]:
        if val:
            specs_json.append({"label": label, "value": val})

    # ── Prices ───────────────────────────────────────────────────────────
    prices_json: dict[str, Any] = {}

    live = (live_prices or {}).get(yacht_id_str) if yacht_id_str else None

    if live:
        # ── Live pricing from portal (accurate, date-specific) ────────────
        charter = live.get("charter_price")
        rack    = live.get("rack_price")
        deposit = live.get("deposit")

        if charter:
            prices_json["charter_price"] = f"{charter:,.2f} €"
        if rack:
            prices_json["base_price"] = f"{rack:,.2f} €"
        if live.get("discounts"):
            prices_json["discounts"] = live["discounts"]

        mand_base = list(live.get("mandatory_extras") or [])
        if deposit:
            mand_base.append({
                "label":  "Security Deposit (refundable, credit card only)",
                "amount": f"{deposit:,.2f} €",
            })
        if mand_base:
            prices_json["mandatory_base"] = mand_base

        opt_items = list(live.get("optional_extras") or [])
        if opt_items:
            prices_json["optional_extras"] = opt_items

    else:
        # ── CSV snapshot fallback (used when live search not available) ───
        rack_raw = _safe_float(row.get("Rack Price (€)") or "")
        net_raw  = _safe_float(row.get("Net Price (€)") or "")

        if price is not None:
            prices_json["charter_price"] = f"{price:,.2f} €"

            if rack_raw and net_raw and net_raw < rack_raw and net_raw > 0:
                discount_pct = (rack_raw - net_raw) / rack_raw
                implied_rack = price / (1.0 - discount_pct)
                discount_amt = implied_rack - price
                prices_json["base_price"] = f"{implied_rack:,.2f} €"
                prices_json["discounts"] = [{
                    "label":  f"Discount ({discount_pct:.0%})",
                    "amount": f"- {discount_amt:,.2f} €",
                }]
            elif rack_raw and rack_raw > (price or 0):
                discount_amt = rack_raw - price
                discount_pct = discount_amt / rack_raw
                prices_json["base_price"] = f"{rack_raw:,.2f} €"
                prices_json["discounts"] = [{
                    "label":  f"Discount ({discount_pct:.0%})",
                    "amount": f"- {discount_amt:,.2f} €",
                }]

        mand_items = parse_extras_str(row.get("Mandatory Extras") or "")
        opt_items  = parse_extras_str(row.get("Optional Extras") or "")

        sec_dep = _safe_float(row.get("Security Dep (€)") or "")
        mand_base = list(mand_items)
        if sec_dep:
            mand_base.append({
                "label":  "Security Deposit (refundable, credit card only)",
                "amount": f"{sec_dep:,.2f} €",
            })

        if mand_base:
            prices_json["mandatory_base"] = mand_base
        if opt_items:
            prices_json["optional_extras"] = opt_items

    # ── Charter JSON ──────────────────────────────────────────────────────
    charter_json: dict[str, Any] = {}
    if base_name:
        charter_json["base"] = base_name
    if lead_from_str:
        charter_json["date_from"] = lead_from_str
    if lead_to_str:
        charter_json["date_to"] = lead_to_str

    charter_type = (answers.get("charterType") or "").strip().lower()
    if charter_type == "skippered":
        charter_json["charter_type_label"] = "Skippered"
    elif charter_type == "bareboat":
        charter_json["charter_type_label"] = "Bareboat"

    # ── Assemble output ───────────────────────────────────────────────────
    out: dict[str, Any] = {
        "display_name":     display_name,
        "model":            model or None,
        "year":             year,
        "length_m":         round(length_ft * 0.3048, 1) if length_ft else None,
        "cabins":           cabins,
        "berths":           berths,
        "base_name":        base_name or None,
        "country":          country or None,
        "region":           region or None,
        "images_json":      images_json,
        "highlights_json":  highlights_json,
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


# ---------------------------------------------------------------------------
# Crew service injection
# ---------------------------------------------------------------------------
# Mirrors the inline logic from build_proposal_from_mmk.py.
_CREW_SERVICE_MAP: list[tuple[str, str, list[str], str | None]] = [
    ("skipper",         "Skipper",          ["skipper", "skiper", "captain"], "Skippered charter"),
    ("chef",            "Chef",             ["chef", "cook"],                 None),
    ("cook",            "Chef / Cook",      ["chef", "cook"],                 None),
    ("hostess",         "Hostess",          ["hostess", "host"],              None),
    ("provisioning",    "Provisioning",     ["provisioning", "provision"],    None),
    ("airportTransfer", "Airport Transfer", ["airport", "transfer"],          None),
]

_CREW_KEYWORDS = ("skipper", "skiper", "captain", "crew", "hostess", "deckhand", "tour leader")


def inject_crew_services(
    entry: dict[str, Any],
    lead_data: dict[str, Any],
    display_label: str = "yacht",
) -> None:
    """
    Add crew service placeholders / notes to entry["prices_json"]["optional_extras"].
    Mutates entry in place. Mirrors the logic from build_proposal_from_mmk.py.
    """
    answers = lead_data.get("answers") or {}
    charter_type_str = (answers.get("charterType") or "").strip().lower()
    lead_services: dict[str, Any] = dict(answers.get("crewServices") or {})
    if charter_type_str == "skippered":
        lead_services.setdefault("skipper", True)

    if not lead_services and charter_type_str != "skippered":
        return
    if "prices_json" not in entry:
        entry["prices_json"] = {}

    yacht_is_crewed = bool((entry.get("charter_json") or {}).get("crewed"))
    opt = entry["prices_json"].setdefault("optional_extras", [])
    mandatory_items = (
        (entry["prices_json"].get("mandatory_advance") or [])
        + (entry["prices_json"].get("mandatory_base") or [])
    )
    mandatory_label_norms = [
        (item.get("label") or "").lower()
        for item in mandatory_items
        if isinstance(item, dict)
    ]

    handled_labels: set[str] = set()
    for svc_key, svc_label, match_kws, note_override in _CREW_SERVICE_MAP:
        if not lead_services.get(svc_key):
            continue
        if svc_label in handled_labels:
            continue

        note = note_override if note_override else "Requested"

        in_mandatory = any(
            kw in lbl
            for lbl in mandatory_label_norms
            for kw in match_kws
        )
        if in_mandatory:
            if yacht_is_crewed:
                opt.append({"label": svc_label, "amount": "", "note": "Included"})
                handled_labels.add(svc_label)
                print(f"  Added '{svc_label}' as 'Included' (crewed) for {display_label}", file=sys.stderr)
            else:
                handled_labels.add(svc_label)
                print(f"  Skipping '{svc_label}' for {display_label} — already mandatory", file=sys.stderr)
            continue

        matched_opt = next(
            (item for item in opt
             if isinstance(item, dict)
             and any(kw in (item.get("label") or "").lower() for kw in match_kws)),
            None,
        )
        if matched_opt is not None:
            if not matched_opt.get("note"):
                matched_opt["note"] = note
                print(f"  Marked '{matched_opt['label']}' as '{note}' for {display_label}", file=sys.stderr)
            handled_labels.add(svc_label)
            continue

        opt.append({"label": svc_label, "amount": "Price on request", "note": note})
        handled_labels.add(svc_label)
        print(f"  Added '{svc_label}' ({note}) placeholder for {display_label}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------
def filter_yachts(
    rows: list[dict[str, str]],
    lead_data: dict[str, Any],
    lead_start: date | None,
    no_filter: bool = False,
    live_prices: dict[str, dict] | None = None,
) -> list[tuple[dict[str, str], float | None]]:
    """
    Filter CSV rows by lead criteria and return (row, price) tuples.
    Price is None when no calendar/net price is available.
    """
    answers = lead_data.get("answers") or {}

    if no_filter:
        return [(row, price_for_dates(row, lead_start)) for row in rows]

    # Derive filter criteria from lead answers
    lead_regions: list[str] = []
    raw_region = answers.get("region")
    if isinstance(raw_region, list):
        lead_regions = [r.strip().lower() for r in raw_region if r]
    elif isinstance(raw_region, str) and raw_region:
        lead_regions = [raw_region.strip().lower()]

    boat_type_raw = (answers.get("boatType") or "any").strip().lower()
    desired_kind: str | None = _BOAT_TYPE_MAP.get(boat_type_raw)  # None = no filter

    size_str = (answers.get("size") or "").strip()
    min_ft, max_ft = _parse_size_range(size_str)

    lead_cabins = int(answers.get("cabins") or 0)

    budget_str = (answers.get("budget") or "").strip().lower()
    budget_min, budget_max = _BUDGET_RANGES.get(budget_str, (0, float("inf")))

    results: list[tuple[dict[str, str], float | None]] = []
    for row in rows:
        # ── Region ──────────────────────────────────────────────────────
        if lead_regions:
            csv_region = (row.get("Region") or "").strip().lower()
            if not any(lr in csv_region or csv_region in lr for lr in lead_regions):
                continue

        # ── Boat type (Kind) ─────────────────────────────────────────────
        if desired_kind is not None:
            if row.get("Kind", "").strip() != desired_kind:
                continue

        # ── Length ───────────────────────────────────────────────────────
        if size_str:
            try:
                ft = float(row.get("Length (ft)") or 0)
            except ValueError:
                ft = 0.0
            if not (min_ft <= ft <= max_ft):
                continue

        # ── Cabins ───────────────────────────────────────────────────────
        if lead_cabins:
            try:
                csv_cabins = int(row.get("Cabins") or 0)
            except ValueError:
                csv_cabins = 0
            if csv_cabins < lead_cabins:
                continue

        # ── Availability gate ─────────────────────────────────────────────
        # When live results are available, only show yachts the portal has
        # confirmed as bookable for these dates. Yachts absent from the live
        # results are either fully booked or deactivated — skip them.
        yacht_id_str = (row.get("Yacht ID") or "").strip()
        live = (live_prices or {}).get(yacht_id_str) if yacht_id_str else None

        if live_prices and not live:
            # Live data exists but this yacht isn't in it → not available
            continue

        # ── Price / Budget ───────────────────────────────────────────────
        # Use live price (accurate, date-specific); fall back to CSV snapshot.
        if live and live.get("charter_price"):
            price: float | None = live["charter_price"]
        else:
            price = price_for_dates(row, lead_start)

        if price is not None:
            if not (budget_min <= price <= budget_max):
                continue
        # If no price info at all, include the yacht (don't exclude blindly)
        results.append((row, price))

    return results


# ---------------------------------------------------------------------------
# Price sort helper (consistent with build_proposal_from_mmk.py)
# ---------------------------------------------------------------------------
def _price_sort_key(entry: dict[str, Any]) -> float:
    raw = (entry.get("prices_json") or {}).get("charter_price", "")
    cleaned = re.sub(r"[^\d,.]", "", str(raw).strip()).replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return float("inf")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a SailScanner proposal JSON from the yacht CSV database + a lead JSON file."
    )
    parser.add_argument(
        "--lead", "-l",
        required=True,
        help="Path to lead JSON file.",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Path to yacht_database_full.csv (default: yacht_database_full.csv in project root).",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Write proposal JSON to this path. Default: stdout (or proposal_from_csv.json if --upload).",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="POST to WordPress after building JSON (same as proposal_import.py).",
    )
    parser.add_argument(
        "--max-yachts",
        type=int,
        default=10,
        dest="max_yachts",
        help="Maximum number of yachts to include (default: 10).",
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        dest="no_filter",
        help="Skip all filtering — include every yacht from the CSV (debug).",
    )
    parser.add_argument(
        "--group-by-base",
        action="store_true",
        dest="group_by_base",
        help="Group yacht cards by charter base in the proposal.",
    )
    args = parser.parse_args()

    # Load .env
    try:
        from dotenv import load_dotenv
        load_dotenv(_project_root / ".env")
    except ImportError:
        pass

    # ── Lead JSON ─────────────────────────────────────────────────────────
    lead_path = Path(args.lead).expanduser()
    if not lead_path.is_absolute():
        lead_path = _project_root / lead_path
    if not lead_path.exists():
        print(f"Error: lead file not found: {lead_path}", file=sys.stderr)
        sys.exit(1)
    try:
        lead_data: dict[str, Any] = json.loads(lead_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error reading lead file: {e}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(lead_data, dict):
        print("Error: lead file must be a JSON object.", file=sys.stderr)
        sys.exit(1)

    # ── Lead dates ───────────────────────────────────────────────────────
    answers = lead_data.get("answers") or {}
    dates_dict = answers.get("dates") or {}
    start_iso = dates_dict.get("start", "")
    end_iso   = dates_dict.get("end", "")
    lead_start: date | None = None
    lead_from_str = ""
    lead_to_str   = ""
    lead_days: int | None = None
    if start_iso and end_iso:
        try:
            lead_start    = date.fromisoformat(start_iso)
            lead_end      = date.fromisoformat(end_iso)
            lead_days     = (lead_end - lead_start).days + 1
            lead_from_str = _fmt_lead_date(start_iso)
            lead_to_str   = _fmt_lead_date(end_iso)
            print(
                f"  Lead dates: {lead_from_str} → {lead_to_str} ({lead_days} days)",
                file=sys.stderr,
            )
        except ValueError:
            pass

    # ── CSV ───────────────────────────────────────────────────────────────
    csv_path = Path(args.csv).expanduser() if args.csv else (_project_root / "yacht_database_full.csv")
    if not csv_path.is_absolute():
        csv_path = _project_root / csv_path
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    print(f"  Loaded {len(rows)} yachts from CSV.", file=sys.stderr)

    # ── Live pricing from portal ──────────────────────────────────────────
    live_prices: dict[str, dict] = {}
    region_str = answers.get("region") or ""
    if isinstance(region_str, list):
        region_str = region_str[0] if region_str else ""

    if _LIVE_SEARCH_AVAILABLE and not args.no_filter and region_str and lead_start:
        duration_days = lead_days if lead_days else 7
        duration_weeks = max(1, round(duration_days / 7))
        adults = int(answers.get("guests") or answers.get("adults") or 2)
        children = int(answers.get("children") or 0)
        print(
            f"  Fetching live pricing for {region_str} / {start_iso} / {duration_weeks*7}n ...",
            file=sys.stderr,
        )
        try:
            live_prices = _live_search_all(
                region=region_str,
                date_from=start_iso,
                duration=duration_weeks * 7,
                adults=adults,
                children=children,
                flexibility="closest_day",
            )
            print(f"  Got live pricing for {len(live_prices)} yachts.", file=sys.stderr)
        except Exception as exc:
            print(f"  WARNING: Live pricing failed ({exc}). Falling back to CSV prices.", file=sys.stderr)
    else:
        if not _LIVE_SEARCH_AVAILABLE:
            print("  Live pricing unavailable (portal_live_search not importable).", file=sys.stderr)
        elif args.no_filter:
            print("  Skipping live pricing (--no-filter mode).", file=sys.stderr)
        elif not lead_start:
            print("  Skipping live pricing (no lead start date).", file=sys.stderr)

    # ── Filter ────────────────────────────────────────────────────────────
    filtered = filter_yachts(rows, lead_data, lead_start, no_filter=args.no_filter, live_prices=live_prices)
    print(
        f"  {len(filtered)} yachts match filters"
        + (" (no-filter mode)" if args.no_filter else "")
        + ".",
        file=sys.stderr,
    )

    # ── Convert to ss_yacht_data ──────────────────────────────────────────
    yacht_data: list[dict[str, Any]] = []
    for row, price in filtered:
        label = (row.get("Model") or row.get("Yacht Name") or "?").strip()
        entry = csv_row_to_ss_data(row, price, lead_data, lead_from_str, lead_to_str, live_prices=live_prices)
        inject_crew_services(entry, lead_data, display_label=label)
        if entry.get("display_name"):
            yacht_data.append(entry)

    # Sort cheapest-first
    yacht_data.sort(key=_price_sort_key)

    # Cap result set
    if args.max_yachts and len(yacht_data) > args.max_yachts:
        print(
            f"  Capping to {args.max_yachts} yachts (cheapest first, {len(yacht_data)} matched).",
            file=sys.stderr,
        )
        yacht_data = yacht_data[: args.max_yachts]

    if not yacht_data:
        print(
            "  Warning: no yachts remain after filtering. Try --no-filter to debug.",
            file=sys.stderr,
        )

    # ── Intro / notes defaults ────────────────────────────────────────────
    contact = (answers.get("contact") or {})
    first_name = (contact.get("name") or "").split()[0] if contact.get("name") else ""
    greeting = f"Hi {first_name}, " if first_name else "Hi, "

    region_label = ""
    raw_region = answers.get("region")
    if isinstance(raw_region, list) and raw_region:
        region_label = ", ".join(raw_region)
    elif isinstance(raw_region, str):
        region_label = raw_region

    date_range_str = ""
    if lead_from_str and lead_to_str:
        date_range_str = f" for <strong>{lead_from_str}</strong> to <strong>{lead_to_str}</strong>"

    intro_html = (
        f"<p>{greeting}here are your charter options{date_range_str}"
        + (f" in <strong>{region_label}</strong>" if region_label else "")
        + ". We've hand-picked these yachts to match your requirements.</p>"
        "<p>Click <strong>View details</strong> on any yacht to see the full specification and photo gallery.</p>"
    )
    notes_html = (
        "<p>This proposal is valid for 14 days. "
        "Contact us to confirm availability and secure your booking.</p>"
    )

    # ── Build payload ─────────────────────────────────────────────────────
    payload: dict[str, Any] = {
        "yachts":          yacht_data,
        "intro_html":      intro_html,
        "itinerary_html":  "",
        "notes_html":      notes_html,
        "contact_whatsapp": "",
        "contact_email":   "",
        "requirements":    {},
        "group_by_base":   args.group_by_base,
        "lead":            lead_data,
    }

    # ── Output ────────────────────────────────────────────────────────────
    out_path_str = args.output
    if args.upload:
        if not out_path_str:
            out_path_str = str(_project_root / "output_files" / "proposal_from_csv.json")
        out_path = Path(out_path_str).expanduser()
        if not out_path.is_absolute():
            out_path = _project_root / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  Wrote {out_path}", file=sys.stderr)
        os.chdir(_project_root)
        os.environ["SAILSCANNER_PROPOSAL_JSON"] = str(out_path)
        from proposal_import import main as run_import
        run_import()
        return

    json_str = json.dumps(payload, indent=2, ensure_ascii=False)
    if out_path_str:
        out_path = Path(out_path_str).expanduser()
        if not out_path.is_absolute():
            out_path = _project_root / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_str, encoding="utf-8")
        print(f"  Wrote {out_path}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
