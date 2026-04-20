#!/usr/bin/env python3
"""
live_proposal_builder.py
========================
Builds a SailScanner proposal entirely from the booking-manager portal live
search API — no CSV, no pre-cached images required.

Pipeline
--------
1. live_search_all()       → all yachts available for exact dates + specs
2. filter_live_yachts()    → narrow by cabin count, budget, boat type, size
3. AI selects 4–6 yachts   → ai_select.select_yachts_from_live()
4. fetch_yacht_photos()    → full gallery per selected yacht (4–6 portal fetches)
5. live_yacht_to_ss_data() → build ss_yacht_data dict for WordPress upload
6. inject_crew_services()  → add crew/service placeholders to prices

Supported regions
-----------------
Any region configured in portal_live_search.REGION_CONFIG.
This is the primary pipeline for all automated proposals.

Error handling
--------------
Photo fetching fails gracefully — if the detail page is unreachable, the
two thumbnail images from the search API are used instead.
All other failures raise exceptions which app.py catches and alerts on.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

# ── Path setup ────────────────────────────────────────────────────────────────
_script_dir = Path(__file__).resolve().parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from portal_live_search import _portal as _portal_session, PORTAL_BASE, _ensure_logged_in

# ── Constants ─────────────────────────────────────────────────────────────────

BM_PUBLIC_BASE = "https://www.booking-manager.com/wbm2/"

BUDGET_RANGES: dict[str, tuple[float, float]] = {
    "under-1k": (0,  1_000),
    "1-2k":     (0,  2_000),
    "2-3k":     (0,  3_000),
    "3-5k":     (0,  5_000),
    "5-7k":     (0,  7_000),
    "5-8k":     (0,  8_000),
    "7-10k":    (0, 10_000),
    "8-12k":    (0, 12_000),
    "10k+":     (0, float("inf")),
    "12k+":     (0, float("inf")),
    "any":      (0, float("inf")),
}

BOAT_TYPE_MAP: dict[str, str | None] = {
    "monohull":  "Sail boat",
    "catamaran": "Catamaran",
    "any":       None,
    "either":    None,   # new quiz value meaning no preference
    "sailboat":  "Sail boat",
    "sail":      "Sail boat",
}

REGION_COUNTRY: dict[str, str] = {
    "Sardinia":         "Italy",
    "Sicily":           "Italy",
    "Marmaris":         "Turkey",
    "Balearic Islands": "Spain",
    "Croatia":          "Croatia",
    "Greece":           "Greece",
    "Montenegro":       "Montenegro",
    "Turkish Aegean":   "Turkey",
}

# Keywords that identify navigation equipment (vs comfort equipment)
_NAV_KEYWORDS = {
    "autopilot", "chart plotter", "chartplotter", "vhf", "ais", "radar",
    "depth sounder", "wind instrument", "wind meter", "compass", "gps",
    "log ", "echo sounder", "navtex", "epirb", "life raft", "flares",
    "safety", "first aid", "plotter",
}


def _is_nav(item: str) -> bool:
    lower = item.lower()
    return any(kw in lower for kw in _NAV_KEYWORDS)


# ── Size range parser ─────────────────────────────────────────────────────────

def _parse_size_range(size_str: str) -> tuple[float, float]:
    if not size_str:
        return (0, float("inf"))
    s = size_str.strip().lower()
    if s.startswith(("under-", "under ")):
        v = re.search(r"\d+", s)
        return (0, float(v.group(0)) if v else float("inf"))
    if s.endswith("+"):
        v = re.search(r"\d+", s)
        return (float(v.group(0)) if v else 0, float("inf"))
    m = re.match(r"(\d+)\s*[-–]\s*(\d+)", s)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    v = re.search(r"\d+", s)
    if v:
        val = float(v.group(0))
        return (val, val)
    return (0, float("inf"))


# ── Photo fetching ─────────────────────────────────────────────────────────────

def fetch_yacht_photos(details_url: str, max_photos: int = 8) -> tuple[list[str], str]:
    """
    Fetch the full photo gallery from a yacht's portal detail page.

    Returns (photos, deck_plan_url) where:
      photos:        List of regular gallery image URLs (max_photos).
      deck_plan_url: URL of the deck plan / layout image, or "" if not found.

    Both sets use public www.booking-manager.com bmdoc URLs (no auth needed).
    Falls back gracefully to ([], "") on any error — caller should use the two
    thumbnail images from the live search as a fallback for photos.

    Deck plan images are identified by keywords in their filename:
    layout, drawing, plano, plan_, deck, floor.
    The first matching image is used; it is excluded from the main gallery.

    Raises nothing — all errors are caught and logged as warnings.
    """
    if not details_url:
        return [], ""

    full_url = (PORTAL_BASE + details_url) if details_url.startswith("/") else details_url

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("WARNING: beautifulsoup4 not installed — skipping detail page photos",
              file=sys.stderr)
        return [], ""

    try:
        if not _ensure_logged_in():
            print("WARNING: portal session unavailable — skipping detail page photos",
                  file=sys.stderr)
            return [], ""

        resp = _portal_session.get(full_url, timeout=20)
        if resp.status_code != 200:
            print(f"WARNING: detail page returned HTTP {resp.status_code}: {full_url}",
                  file=sys.stderr)
            return [], ""

        soup          = BeautifulSoup(resp.text, "html.parser")
        photos:       list[str] = []
        seen:         set[str]  = set()
        deck_plan_url: str      = ""

        _DECK_PLAN_KEYWORDS = ("layout", "drawing", "plano", "plan_", "deck", "floor")

        for img in soup.find_all("img"):
            src = (img.get("src") or img.get("data-src") or "").strip()
            if not src or "bmdoc" not in src:
                continue
            if not re.search(r"\.(jpg|jpeg|webp|png)", src, re.I):
                continue

            # Resolve relative paths to absolute portal URLs
            if src.startswith("bmdoc/"):
                src = f"{PORTAL_BASE}/wbm2/{src}"
            elif src.startswith("/"):
                src = PORTAL_BASE + src

            # Convert portal URL → public www URL (no auth needed)
            src = src.replace("portal.booking-manager.com", "www.booking-manager.com")

            # Set width to 1200px for display quality
            clean = re.sub(r"([?&]width=)\d+", r"\g<1>1200", src)
            if "width=" not in clean:
                clean += ("&" if "?" in clean else "?") + "width=1200"

            # Detect deck plan / layout images by filename keywords
            fname = src.split("?")[0].rsplit("/", 1)[-1].lower()
            if any(kw in fname for kw in _DECK_PLAN_KEYWORDS):
                if not deck_plan_url:
                    deck_plan_url = clean  # capture the first one
                continue  # always exclude from main gallery

            if clean not in seen and len(photos) < max_photos:
                seen.add(clean)
                photos.append(clean)

        return photos, deck_plan_url

    except Exception as exc:
        print(f"WARNING: photo fetch failed for {full_url}: {exc}", file=sys.stderr)
        return [], ""


# ── Pro-rating ───────────────────────────────────────────────────────────────

def pro_rate_live_results(
    live_results: dict[str, dict],
    actual_days: int,
    standard_days: int,
) -> dict[str, dict]:
    """
    Scale charter prices from standard_days rate to actual_days.

    Scales:  charter_price, rack_price, discount amounts (proportional)
             per-day optional extras (detected via priceUnit field)
    Fixed:   mandatory_extras (per-booking fees — cleaning, permits, deposit etc.)

    Adds 'pro_rated', 'actual_days', 'standard_days', 'pro_rate_note' to each result.
    """
    factor = actual_days / standard_days
    scaled: dict[str, dict] = {}

    for yid, data in live_results.items():
        d = dict(data)  # shallow copy — don't mutate originals

        # Scale charter and rack prices
        if d.get("charter_price") is not None:
            d["charter_price"] = round(d["charter_price"] * factor, 2)
        if d.get("rack_price") is not None:
            d["rack_price"] = round(d["rack_price"] * factor, 2)

        # Scale discount amounts (they're proportional to the charter price)
        scaled_discounts = []
        for disc in (d.get("discounts") or []):
            disc = dict(disc)
            amt_str = disc.get("amount", "")
            # Parse "- 450.00 €" → scale → reformat
            m = re.search(r'[\d,.]+', amt_str.replace(",", ""))
            if m:
                try:
                    scaled_amt = float(m.group(0)) * factor
                    prefix = "- " if amt_str.strip().startswith("-") else ""
                    disc["amount"] = f"{prefix}{scaled_amt:,.2f} €"
                except ValueError:
                    pass
            scaled_discounts.append(disc)
        d["discounts"] = scaled_discounts

        # Scale per-day optional extras; leave per-booking ones unchanged
        scaled_opt = []
        for item in (d.get("optional_extras") or []):
            item = dict(item)
            unit = (item.get("unit") or "").lower()
            if any(kw in unit for kw in ("day", "daily", "per_day")):
                amt_str = item.get("amount", "")
                m = re.search(r'[\d,.]+', amt_str.replace(",", ""))
                if m:
                    try:
                        # unit price × actual days
                        unit_price = float(m.group(0))
                        total = unit_price * actual_days
                        item["amount"] = f"{total:,.2f} €"
                        item["note"] = f"({actual_days} days × {unit_price:,.2f} €/day)"
                    except ValueError:
                        pass
            scaled_opt.append(item)
        d["optional_extras"] = scaled_opt

        # Tag the result so downstream code knows pro-rating was applied
        d["pro_rated"]      = True
        d["actual_days"]    = actual_days
        d["standard_days"]  = standard_days
        d["pro_rate_note"]  = (
            f"Charter price scaled from {standard_days}-day rate "
            f"for your {actual_days}-night charter. "
            f"One-off fees (cleaning, permits etc.) are unchanged."
        )

        scaled[yid] = d

    return scaled


def standard_search_duration(actual_days: int) -> int:
    """Return the standard portal duration to use as a fallback for pro-rating."""
    if actual_days < 7:
        return 7
    if actual_days < 14:
        return 14
    return actual_days  # 14+ days: no change needed


# ── Filtering ─────────────────────────────────────────────────────────────────

def filter_live_yachts(
    live_results: dict[str, dict],
    lead: dict,
) -> list[tuple[str, dict]]:
    """
    Filter live search results by lead criteria.

    Args:
        live_results: {yacht_id: live_data_dict} from live_search_all()
        lead:         Full lead JSON from the quiz

    Returns:
        [(yacht_id, live_data), ...] sorted cheapest first.
        Yachts without a price are appended at the end.
    """
    answers = lead.get("answers") or {}

    desired_kind: str | None = BOAT_TYPE_MAP.get(
        (answers.get("boatType") or "any").strip().lower()
    )
    size_str              = (answers.get("size") or "").strip()
    min_ft, max_ft        = _parse_size_range(size_str)
    lead_cabins           = int(answers.get("cabins") or 0)
    budget_str            = (answers.get("budget") or "").strip().lower()
    budget_min, budget_max = BUDGET_RANGES.get(budget_str, (0, float("inf")))

    matched: list[tuple[str, dict]] = []

    for yacht_id, data in live_results.items():
        specs = data.get("specs") or {}

        # ── Boat type ──────────────────────────────────────────────────────
        if desired_kind is not None and data.get("kind", "") != desired_kind:
            continue

        # ── Cabins ─────────────────────────────────────────────────────────
        if lead_cabins:
            try:
                if int(specs.get("cabins") or 0) < lead_cabins:
                    continue
            except (ValueError, TypeError):
                pass

        # ── Size / length ───────────────────────────────────────────────────
        # Portal returns "33 ft" format — extract the number
        if size_str:
            try:
                _lraw = str(specs.get("length") or "")
                _lm = re.search(r'[\d.]+', _lraw)
                length = float(_lm.group(0)) if _lm else 0.0
                if length and not (min_ft <= length <= max_ft):
                    continue
            except (ValueError, TypeError):
                pass

        # ── Budget ─────────────────────────────────────────────────────────
        price = data.get("charter_price")
        if price is not None and not (budget_min <= price <= budget_max):
            continue

        matched.append((yacht_id, data))

    # Cheapest first; unpriced yachts go to the end
    matched.sort(key=lambda x: x[1].get("charter_price") or float("inf"))
    return matched


# ── ss_yacht_data builder ─────────────────────────────────────────────────────

def live_yacht_to_ss_data(
    yacht_id: str,
    live_data: dict,
    photos: list[str],
    lead: dict,
    region: str,
    from_str: str,
    to_str: str,
    deck_plan_url: str = "",
) -> dict[str, Any]:
    """
    Convert a live search yacht entry into an ss_yacht_data dict.
    Equivalent of csv_row_to_ss_data() but driven entirely by portal API data.
    """
    answers   = lead.get("answers") or {}
    specs     = live_data.get("specs") or {}
    equipment = live_data.get("equipment") or []

    model     = specs.get("model", "").strip()
    base_name = live_data.get("base", "").strip()
    country   = REGION_COUNTRY.get(region, "")

    try:
        year = int(specs.get("year") or 0) or None
    except (ValueError, TypeError):
        year = None

    # Length: portal returns "33 ft", "41 ft" etc — extract the number
    length_raw = str(specs.get("length") or "")
    _lm = re.search(r'[\d.]+', length_raw)
    length_ft = float(_lm.group(0)) if _lm else 0.0
    length_m  = round(length_ft * 0.3048, 1) if length_ft else None

    # Cabins: plain integer string e.g. "3"
    try:
        cabins = int(re.search(r'\d+', str(specs.get("cabins") or "0")).group(0))
    except (AttributeError, ValueError, TypeError):
        cabins = 0

    # Berths: may be "7 (6+1)" — keep full string for display, extract number for field
    berths_raw = str(specs.get("berths") or "").strip()
    try:
        berths = int(re.search(r'\d+', berths_raw).group(0))
    except (AttributeError, ValueError, TypeError):
        berths = 0

    heads = str(specs.get("heads") or "").strip()

    # ── Images ────────────────────────────────────────────────────────────
    # Full gallery from detail page fetch, falling back to search thumbnails
    if photos:
        images_json: list[str] = photos
    else:
        images_json = [u for u in [
            live_data.get("image_url"),
            live_data.get("interior_url"),
        ] if u]

    # ── Equipment (highlights block) ──────────────────────────────────────
    # Pass full equipment list — the proposal template renders these as chips
    highlights_json: list[str] = equipment

    # ── Specs block ───────────────────────────────────────────────────────
    specs_json: list[dict] = []
    for label, val in [
        ("Year",       str(year) if year else ""),
        ("Length",     length_raw if length_raw else ""),   # e.g. "33 ft" — portal's own string
        ("Berths",     berths_raw if berths_raw else ""),   # e.g. "7 (6+1)" — keeps saloon berth info
        ("Cabins",     str(cabins) if cabins else ""),
        ("WC / Heads", heads),
        ("Base",       base_name),
    ]:
        if val:
            specs_json.append({"label": label, "value": val})

    # ── Prices ────────────────────────────────────────────────────────────
    prices_json: dict[str, Any] = {}
    charter = live_data.get("charter_price")
    rack    = live_data.get("rack_price")
    deposit = live_data.get("deposit")

    if charter:
        prices_json["charter_price"] = f"{charter:,.2f} €"
    if rack:
        prices_json["base_price"] = f"{rack:,.2f} €"
    if live_data.get("discounts"):
        prices_json["discounts"] = live_data["discounts"]

    mand_base = list(live_data.get("mandatory_extras") or [])
    if deposit:
        mand_base.append({
            "label":  "Security Deposit (refundable, credit card only)",
            "amount": f"{deposit:,.2f} €",
        })
    if mand_base:
        prices_json["mandatory_base"] = mand_base

    opt_items = list(live_data.get("optional_extras") or [])
    if opt_items:
        prices_json["optional_extras"] = opt_items

    # Pro-rate note — shown below pricing table when prices have been scaled.
    # Key must be "prorated_note" to match render_pricing_table() in class-ss-proposal-helpers.php.
    if live_data.get("pro_rated") and live_data.get("pro_rate_note"):
        prices_json["prorated_note"] = live_data["pro_rate_note"]

    # ── Charter details ───────────────────────────────────────────────────
    charter_json: dict[str, Any] = {}
    if base_name:
        charter_json["base"] = base_name
    if from_str:
        charter_json["date_from"] = from_str
    if to_str:
        charter_json["date_to"] = to_str

    charter_type = (answers.get("charterType") or "").strip().lower()
    if charter_type == "skippered":
        charter_json["charter_type_label"] = "Skippered"
    elif charter_type == "bareboat":
        charter_json["charter_type_label"] = "Bareboat"

    # ── Assemble ──────────────────────────────────────────────────────────
    out: dict[str, Any] = {
        "display_name":     model or "Yacht",
        "model":            model or None,
        "year":             year,
        "length_m":         length_m,
        "cabins":           cabins,
        "berths":           berths,
        "base_name":        base_name or None,
        "country":          country or None,
        "region":           region or None,
        "images_json":      images_json,
        "highlights_json":  highlights_json,
        "layout_image_url": deck_plan_url or None,
    }
    if specs_json:
        out["specs_json"] = specs_json
    if prices_json:
        out["prices_json"] = prices_json
    if charter_json:
        out["charter_json"] = charter_json

    return out
