#!/usr/bin/env python3
"""
ai_select.py — AI Yacht Selection for SailScanner
==================================================

Calls OpenAI to:
  1. Select 4–6 best-matching yachts from a pre-filtered shortlist
  2. Mark 1–2 as recommended
  3. Write a personalised 2–3 sentence note per yacht
  4. Write the proposal intro HTML and closing notes HTML

Called by app.py after filter_yachts() has reduced the database to a shortlist.

Model: gpt-4o-mini (default) — fractions of a penny per call.
       Override with OPENAI_MODEL=gpt-4o in .env for better quality.

Privacy rules enforced at prompt level:
  - Never mentions provider/company names
  - Never mentions individual boat names (e.g. "Tommy", "Stella")
  - Always uses model names only (e.g. "Bavaria 39", "Oceanis 46.1")

Fallback behaviour:
  If the API call fails for any reason, returns the top 5 cheapest yachts
  with generic copy — the proposal still gets built and sent.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("openai not installed. Run: pip install openai")


# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


# ── Lead parsing helpers ──────────────────────────────────────────────────────

def _contact_first_name(lead: dict) -> str:
    """
    Extract first name from a lead, handling both contact formats:
      Old: { contact: { name: "John Smith" } }
      New: { contact: { firstName: "John", lastName: "Smith" } }
    """
    contact = (lead.get("answers") or {}).get("contact") or {}
    if contact.get("firstName"):
        return str(contact["firstName"]).strip()
    name = str(contact.get("name") or "").strip()
    return name.split()[0] if name else ""


def _contact_full_name(lead: dict) -> str:
    """Full name from either contact format."""
    contact = (lead.get("answers") or {}).get("contact") or {}
    if contact.get("firstName"):
        first = str(contact.get("firstName") or "").strip()
        last  = str(contact.get("lastName") or "").strip()
        return f"{first} {last}".strip()
    return str(contact.get("name") or "").strip()


def _parse_guests(answers: dict) -> tuple[int, int]:
    """
    Return (adults, children) from either guests format:
      Old flat: { adults: 4, children: 1 }
      New nested: { guests: { adults: 4, children: 1 } }
    """
    guests_raw = answers.get("guests") or {}
    if isinstance(guests_raw, dict):
        return int(guests_raw.get("adults") or 2), int(guests_raw.get("children") or 0)
    # Old flat format
    return int(guests_raw or answers.get("adults") or 2), int(answers.get("children") or 0)


# Base charter price ranges for each budget enum value (in EUR).
# These are the CHARTER PRICE ceilings — the quiz labels shown to the client
# are higher by the offset (skippered +€1.5k, catamaran +€3k, both +€4.5k).
_BUDGET_BASE: dict[str, tuple[float, float]] = {
    "under-3k": (0,     3_000),
    "3-5k":     (3_000, 5_000),
    "5-8k":     (5_000, 8_000),
    "8-12k":    (8_000, 12_000),
    "12k+":     (12_000, float("inf")),
    "any":      (0,     float("inf")),
}


def _budget_offset_k(charter_type: str, boat_type: str) -> float:
    """
    Return the k-EUR offset that was added to the quiz budget labels.
    Skippered: +1.5k  |  Catamaran: +3k  |  Both: +4.5k
    """
    offset = 0.0
    if (charter_type or "").strip().lower() == "skippered":
        offset += 1.5
    if (boat_type or "").strip().lower() == "catamaran":
        offset += 3.0
    return offset


def _budget_label(budget_enum: str, charter_type: str, boat_type: str) -> str:
    """
    Build a human-readable budget string for the AI prompt, showing both
    the charter price range and the effective all-in estimate.

    Example: "€8k–€12k charter price (client's all-in expectation ~€9.5k–€13.5k
              including skipper fee)"
    """
    base_min, base_max = _BUDGET_BASE.get(budget_enum.lower(), (0, float("inf")))
    offset = _budget_offset_k(charter_type, boat_type)

    def _fmt(v: float) -> str:
        if v == float("inf"):
            return "no limit"
        k = v / 1_000
        return f"€{k:g}k"

    charter_str = (
        f"Under {_fmt(base_max)}" if base_min == 0 and base_max != float("inf")
        else f"{_fmt(base_min)}–{_fmt(base_max)}" if base_max != float("inf")
        else f"{_fmt(base_min)}+"
    )

    if offset == 0:
        return f"{charter_str} charter price"

    # Show effective all-in range
    eff_min = base_min + offset * 1_000
    eff_max = base_max + offset * 1_000
    eff_str = (
        f"under ~€{(eff_max/1000):g}k" if base_min == 0 and base_max != float("inf")
        else f"~€{eff_min/1000:g}k–€{eff_max/1000:g}k" if base_max != float("inf")
        else f"~€{eff_min/1000:g}k+"
    )
    extras = []
    if "skippered" in charter_type.lower():
        extras.append("skipper fee")
    if "catamaran" in boat_type.lower():
        extras.append("catamaran premium")
    extra_note = f" including {' + '.join(extras)}" if extras else ""
    return (
        f"{charter_str} charter price "
        f"(client's all-in expectation {eff_str}{extra_note})"
    )

# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a yacht charter specialist at SailScanner, an expert broker \
helping clients find their perfect sailing holiday in the Mediterranean and Turkey.

Your job is to review a shortlist of available yachts and select the best options for \
a specific client, then write personalised proposal copy.

CRITICAL RULES — never break these:
- NEVER mention the name of any charter company, provider, or operator
- NEVER mention individual boat names (e.g. "Stella", "Tommy") — only model names \
  (e.g. "Bavaria 39", "Oceanis 46.1")
- Always refer to yachts by model name only
- Write in a warm, expert, confident tone — you are the trusted guide
- Your output must be valid JSON only — no markdown, no other text
- NEVER use em dashes (—) anywhere in your output; use a comma or reword the sentence instead
- If the CLIENT REQUIREMENTS section contains any instruction marked IMPORTANT or NOTE, \
  you MUST weave the substance of that information naturally into the intro copy. \
  Do not copy the instruction framing itself (e.g. do not write "NOTE" or "IMPORTANT" \
  or "mention to the client") — just include the actual information naturally"""

SELECTION_PROMPT_TEMPLATE = """\
A client has submitted a yacht charter enquiry. Here are their requirements:

## CLIENT REQUIREMENTS
{lead_summary}

## AVAILABLE YACHTS
We searched {total_available} yachts confirmed available for these exact dates. \
The {shortlist_count} best candidates for this client are listed below \
(sorted cheapest first).

Fields reference:
- charter_price_eur: client-facing price for their week (live, date-specific)
- rack_price_eur: undiscounted list price (shows the saving)
- active_discounts: named promotional discounts currently applied
- mandatory_extras_approx_eur: approximate total of required extras per booking
- provider_rating: charter company quality score (0–5 scale)
- skipper_available: whether a professional skipper can be arranged
- comfort_equipment: onboard amenities list
- nav_equipment: navigation instruments and safety gear

{yacht_summaries}

## YOUR TASK

1. Select 4–6 yachts that best match this client from the shortlist above.
   Prioritise: correct cabin count → within budget (including mandatory extras) → \
   newer build year → higher provider_rating → best comfort for their group.
   Explain in the per-yacht notes WHY each yacht made the cut over the others you \
   did not select (e.g. "better value than the Oceanis 46 due to lower extras", \
   "newer build and higher provider_rating than the Bavaria 40").

2. Mark 1–2 as RECOMMENDED — the single best overall fit must always be marked. \
   Consider: value for money (charter_price + mandatory_extras vs rack_price), \
   build year, provider_rating, comfort_equipment match to client priorities. \
   Never recommend purely on price.

3. For each selected yacht write 2–3 sentences explaining specifically why it suits \
   THIS client. Reference concrete details: their cabin requirement, group size, \
   charter type, budget, and specific equipment they would value. \
   Always mention why it was chosen ahead of yachts you did NOT select.

4. Write a personalised intro as a SINGLE HTML <p> tag using this exact structure:

   "Hi [FirstName],<br/><br/>[Overview body]<br/><br/>Our top pick is the [Model]...<br/><br/>Best regards,<br/>Chris"

   Overview body (3-4 sentences):
   - Address them by FIRST NAME ONLY (never full name), followed by a comma
   - State exactly how many yachts were confirmed available for their exact dates \
     (use {total_available} — say "X yachts confirmed available")
   - Explain the key filter criteria applied to narrow to this shortlist \
     (always mention: required cabin count, budget ceiling, and at least one other \
     factor actually used — e.g. yacht age, provider rating, skipper availability, \
     comfort features relevant to the client)
   - If {total_available} > 15, note that there are more options available on request
   - If the CLIENT REQUIREMENTS section contains a NOTE about availability or pro-rating, \
     weave that information naturally into this paragraph as if you are telling the client. \
     Do NOT copy the instruction text itself.

   Top pick sentence (1-2 sentences):
   - Name the recommended yacht model explicitly (e.g. "Our top pick is the Beneteau \
     Oceanis 46.1...")
   - State 1-2 specific reasons it stands out: price-to-value, build year, provider \
     rating, or standout comfort features relevant to this client
   - Warm, expert, confident tone — not salesy

   Always end with exactly: Best regards,<br/>Chris

5. Write a closing notes paragraph (2 sentences) as a single HTML <p> tag:
   - Note that prices shown are live rates pulled for their exact dates, \
     not generic seasonal averages
   - Invite them to get in touch to hold a yacht and confirm dates

Return ONLY valid JSON in this exact format — no other text:
{{
  "selected_yacht_ids": ["id1", "id2", "id3", "id4"],
  "recommended_yacht_ids": ["id1"],
  "yacht_notes": {{
    "id1": "The Beneteau Oceanis 46.1 is our top pick for your group...",
    "id2": "At this budget the Jeanneau 53 offers..."
  }},
  "intro_html": "<p>Hi [FirstName],<br/><br/>We searched 9 yachts confirmed available for your exact dates in [Destination]. We focused on [cabin count], [budget], and [other factor].<br/><br/>Our top pick is the [Model], offering [reason 1] and [reason 2].<br/><br/>Best regards,<br/>Chris</p>",
  "notes_html": "<p>Prices shown are live rates for your exact dates...</p>"
}}"""


# ── Data class ────────────────────────────────────────────────────────────────

@dataclass
class SelectionResult:
    """Output of the AI selection call."""
    selected_ids: list       # Yacht IDs in display order
    recommended_ids: list    # Subset of selected_ids to highlight
    yacht_notes: dict        # {yacht_id: "recommendation note text"}
    intro_html: str          # Personalised intro HTML for the proposal
    notes_html: str          # Closing notes HTML for the proposal


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_summary(row: dict, price: float | None, live_data: dict | None = None) -> dict:
    """
    Build a compact summary dict for a single yacht row.

    Includes enough data for the AI to make informed selection decisions and
    write specific per-yacht copy. Never includes provider name or boat name.
    """
    photos = [p for p in (row.get("Photos URL") or "").split("|") if p.strip()]

    # Skipper availability — check both optional extras and charter type columns
    optional_raw = (row.get("Optional Extras") or "").lower()
    charter_type_raw = (row.get("Charter Type") or "").lower()
    has_skipper = any(kw in optional_raw for kw in ("skipper", "skiper", "captain")) or \
                  "skippered" in charter_type_raw

    # Rough mandatory extras total from booking
    mand_total = 0.0
    for m in re.finditer(
        r"([\d,]+\.?\d*)\s*€\s*per\s+booking",
        row.get("Mandatory Extras") or "",
        re.IGNORECASE,
    ):
        try:
            mand_total += float(m.group(1).replace(",", ""))
        except ValueError:
            pass

    # Full comfort and nav equipment lists (not capped — AI needs to see everything)
    comfort = [t.strip() for t in (row.get("Comfort Equipment") or "").split(",") if t.strip()]
    nav     = [t.strip() for t in (row.get("Nav Equipment") or "").split(",") if t.strip()]

    # Air conditioning flag (quick scan)
    ac_keywords = ("air conditioning", "a/c", "aircon", "air con", "klimaanlage")
    has_ac = any(kw in c.lower() for c in comfort for kw in ac_keywords)

    # WC count
    wc_val = (row.get("WC / Heads") or "").strip()

    # Build year as integer for age calculation
    year_str = row.get("Year Built", "")
    year_int = None
    try:
        year_int = int(year_str)
    except (ValueError, TypeError):
        pass

    # Provider rating from live search data (0–5 scale)
    provider_rating = None
    if live_data:
        r = live_data.get("raw", {}) or {}
        rating = r.get("serviceRating")
        if rating is not None:
            try:
                provider_rating = round(float(rating), 1)
            except (ValueError, TypeError):
                pass

    # Rack price and named discounts from live data
    rack = live_data.get("rack_price") if live_data else None
    discount_labels = [d["label"] for d in (live_data.get("discounts") or [])] if live_data else []

    # All-in price estimate (charter + mandatory extras) to help AI assess true budget fit
    all_in = None
    if price is not None and mand_total:
        live_mand = sum(
            item.get("amount_eur", 0) or 0
            for item in (live_data.get("mandatory_extras") or [])
        ) if live_data else None
        extras_est = live_mand if (live_mand is not None and live_mand > 0) else mand_total
        all_in = round(price + extras_est)

    summary: dict = {
        "id":                           row.get("Yacht ID", ""),
        "model":                        (row.get("Model") or row.get("Yacht Name") or "Unknown").strip(),
        "year":                         year_int or year_str,
        "kind":                         row.get("Kind", ""),
        "cabins":                       row.get("Cabins", ""),
        "berths":                       row.get("Berths", ""),
        "wc_heads":                     wc_val or None,
        "length_ft":                    row.get("Length (ft)", ""),
        "base":                         row.get("Base", ""),
        "charter_price_eur":            round(price) if price is not None else None,
        "rack_price_eur":               round(rack) if rack else None,
        "active_discounts":             discount_labels or None,
        "mandatory_extras_approx_eur":  round(mand_total) if mand_total else None,
        "all_in_approx_eur":            all_in,
        "provider_rating":              provider_rating,
        "skipper_available":            has_skipper,
        "air_conditioning":             has_ac,
        "comfort_equipment":            comfort if comfort else None,
        "nav_equipment":                nav[:8] if nav else None,  # cap nav at 8 items
        "photo_count":                  len(photos),
    }

    # Strip None values to keep token count lean
    return {k: v for k, v in summary.items() if v is not None and v != "" and v != [] and v is not False}


def _lead_summary(lead: dict) -> str:
    """Format lead data into a readable string for the AI prompt."""
    answers = lead.get("answers") or {}
    contact = answers.get("contact") or {}
    dates = answers.get("dates") or {}

    region = answers.get("region", "")
    if isinstance(region, list):
        region = ", ".join(region)

    # Calculate trip duration in days
    duration_str = ""
    start_iso = dates.get("start", "")
    end_iso = dates.get("end", "")
    if start_iso and end_iso:
        try:
            from datetime import date as _date
            d_start = _date.fromisoformat(start_iso)
            d_end   = _date.fromisoformat(end_iso)
            days = (d_end - d_start).days
            duration_str = f" ({days} nights)"
        except ValueError:
            pass

    # Guest counts — handle both old flat and new nested {adults, children} formats
    adults, children = _parse_guests(answers)
    guest_str = f"{adults} adults"
    if children:
        guest_str += f" + {children} children"

    lines = [
        f"Client name: {_contact_full_name(lead)}",
        f"Destination: {region or answers.get('country', 'Unknown')}",
        f"Dates: {start_iso or '?'} to {end_iso or '?'}{duration_str}",
        f"Guests: {guest_str}",
        f"Cabins needed: {answers.get('cabins', '?')}",
        f"Budget: {_budget_label(answers.get('budget', 'any'), answers.get('charterType', ''), answers.get('boatType', ''))}",
        f"Charter type: {answers.get('charterType', 'Not specified')} (bareboat = self-sailed; skippered = captain provided)",
        f"Boat type preference: {answers.get('boatType', 'Any')}",
        f"Boat size preference: {answers.get('size', 'Any')} ft",
    ]

    crew = answers.get("crewServices") or {}
    services = [k for k, v in crew.items() if v]
    if services:
        lines.append(f"Crew / services requested: {', '.join(services)}")

    if answers.get("notes"):
        lines.append(f"Additional notes from client: {answers['notes']}")

    return "\n".join(lines)


def _fallback_result(rows_with_prices: list, lead: dict) -> SelectionResult:
    """
    Return a basic selection without AI — used when the API call fails.
    Selects the cheapest 5 yachts with generic copy so the proposal still works.
    """
    answers = lead.get("answers") or {}
    first_name = _contact_first_name(lead)
    greeting = f"Hi {first_name}" if first_name else "Hi"

    region = answers.get("region", "")
    if isinstance(region, list):
        region = ", ".join(region)

    dates = answers.get("dates") or {}
    date_str = ""
    if dates.get("start") and dates.get("end"):
        date_str = f" for {dates['start']} to {dates['end']}"

    top = rows_with_prices[:5]
    selected_ids = [row.get("Yacht ID", "") for row, _ in top]

    intro_html = (
        f"<p>{greeting}, thank you for your enquiry. "
        f"Here are our selected yacht options"
        + (f" for {region}" if region else "")
        + (date_str if date_str else "")
        + " — each hand-picked to match your requirements.</p>"
        "<p>Click <strong>View details</strong> on any yacht to see the full specification and photo gallery.</p>"
    )
    notes_html = (
        "<p>Prices shown are based on our reference week rates and may vary slightly for your specific dates. "
        "Contact us to confirm availability and we'll get everything arranged for you.</p>"
    )

    return SelectionResult(
        selected_ids=selected_ids,
        recommended_ids=selected_ids[:1],
        yacht_notes={},
        intro_html=intro_html,
        notes_html=notes_html,
    )


# ── Main function ─────────────────────────────────────────────────────────────

def select_yachts(
    rows_with_prices: list,
    lead: dict,
    *,
    model: str | None = None,
    max_shortlist: int = 25,
    total_available: int | None = None,
    live_prices: dict | None = None,
) -> SelectionResult:
    """
    Use OpenAI to select 4–6 best-matching yachts and write proposal copy.

    Args:
        rows_with_prices: Pre-filtered list of (csv_row_dict, price) tuples,
                          sorted cheapest first by filter_yachts().
        lead:             Full lead JSON dict from the quiz.
        model:            OpenAI model override (default: gpt-4o-mini).
        max_shortlist:    Max yachts to send to AI — controls token usage.
                          Default 25 = ~5,000 tokens input, ~$0.001 per call.

    Returns:
        SelectionResult with selected IDs, recommended IDs, notes, and copy.
        If the API call fails, falls back to top 5 cheapest with generic copy.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("Warning: OPENAI_API_KEY not set — using fallback selection.", flush=True)
        return _fallback_result(rows_with_prices, lead)

    if not rows_with_prices:
        return _fallback_result([], lead)

    # Cap shortlist to control token usage
    shortlist = rows_with_prices[:max_shortlist]

    # Build compact summaries — include live data for provider rating + discounts
    summaries = [
        _row_to_summary(
            row, price,
            live_data=(live_prices or {}).get((row.get("Yacht ID") or "").strip())
        )
        for row, price in shortlist
    ]

    n_total = total_available if total_available is not None else len(rows_with_prices)

    prompt = SELECTION_PROMPT_TEMPLATE.format(
        lead_summary=_lead_summary(lead),
        yacht_summaries=json.dumps(summaries, indent=2, ensure_ascii=False),
        total_available=n_total,
        shortlist_count=len(summaries),
    )

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model or DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.7,
            max_tokens=2500,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        data = json.loads(raw)

        result = SelectionResult(
            selected_ids=data.get("selected_yacht_ids", []),
            recommended_ids=data.get("recommended_yacht_ids", []),
            yacht_notes=data.get("yacht_notes", {}),
            intro_html=data.get("intro_html", ""),
            notes_html=data.get("notes_html", ""),
        )

        # Sanity check — if AI returned nothing usable, fall back
        if not result.selected_ids:
            print("Warning: AI returned no selected IDs — using fallback.", flush=True)
            return _fallback_result(rows_with_prices, lead)

        return result

    except Exception as e:
        print(f"Warning: AI selection failed ({type(e).__name__}: {e}) — using fallback.", flush=True)
        return _fallback_result(rows_with_prices, lead)


# ── Live-data variant ─────────────────────────────────────────────────────────

def _live_summary(yacht_id: str, live_data: dict) -> dict:
    """
    Build a compact summary dict from a live search result entry.
    Used by select_yachts_from_live() — no CSV row needed.
    """
    specs     = live_data.get("specs") or {}
    equipment = live_data.get("equipment") or []
    rack      = live_data.get("rack_price")
    charter   = live_data.get("charter_price")
    discounts = [d["label"] for d in (live_data.get("discounts") or [])]

    # Mandatory extras total for all-in estimate
    mand_total = 0.0
    for item in (live_data.get("mandatory_extras") or []):
        amt_str = str(item.get("amount") or "")
        cleaned = re.sub(r"[^\d.]", "", amt_str.replace(",", ""))
        try:
            mand_total += float(cleaned)
        except ValueError:
            pass
    all_in = round(charter + mand_total) if charter and mand_total else None

    # Provider rating from raw portal data
    provider_rating = None
    raw = live_data.get("raw") or {}
    rating = raw.get("serviceRating")
    if rating is not None:
        try:
            provider_rating = round(float(rating), 1)
        except (ValueError, TypeError):
            pass

    # Partner quality signal
    partner = None
    if live_data.get("is_golden_partner"):
        partner = "Gold"
    elif live_data.get("is_silver_partner"):
        partner = "Silver"

    # AC flag
    ac_kws = ("air conditioning", "a/c", "aircon", "air con")
    has_ac = any(kw in e.lower() for e in equipment for kw in ac_kws)

    # Skipper availability
    has_skipper = any(
        kw in (item.get("label") or "").lower()
        for item in (live_data.get("optional_extras") or [])
        for kw in ("skipper", "captain")
    )

    summary: dict = {
        "id":                           yacht_id,
        "model":                        specs.get("model", "Unknown"),
        "year":                         specs.get("year", ""),
        "kind":                         live_data.get("kind", ""),
        "cabins":                       specs.get("cabins", ""),
        "berths":                       specs.get("berths", ""),
        "wc_heads":                     specs.get("heads") or None,
        "length_ft":                    specs.get("length", ""),
        "base":                         live_data.get("base", ""),
        "charter_price_eur":            round(charter) if charter else None,
        "rack_price_eur":               round(rack) if rack else None,
        "active_discounts":             discounts or None,
        "mandatory_extras_approx_eur":  round(mand_total) if mand_total else None,
        "all_in_approx_eur":            all_in,
        "provider_rating":              provider_rating,
        "partner_status":               partner,
        "skipper_available":            has_skipper or None,
        "air_conditioning":             has_ac or None,
        "equipment":                    equipment if equipment else None,
    }
    # Strip None/empty values to keep tokens lean
    return {k: v for k, v in summary.items() if v is not None and v != "" and v != []}


def _fallback_result_live(filtered: list[tuple[str, dict]], lead: dict) -> SelectionResult:
    """Fallback selection for the live pipeline — top 5 cheapest with generic copy."""
    answers = lead.get("answers") or {}
    first = _contact_first_name(lead)
    greeting = f"Hi {first}" if first else "Hi"

    region = answers.get("region", "")
    if isinstance(region, list):
        region = ", ".join(region)

    top = filtered[:5]
    selected_ids = [yid for yid, _ in top]

    intro_html = (
        f"<p>{greeting}, thank you for your enquiry. "
        f"Here are our selected yacht options"
        + (f" for {region}" if region else "")
        + " — each hand-picked to match your requirements.</p>"
    )
    notes_html = (
        "<p>Prices shown are live rates pulled for your exact dates. "
        "Get in touch to hold a yacht and we'll confirm availability for you.</p>"
    )
    return SelectionResult(
        selected_ids=selected_ids,
        recommended_ids=selected_ids[:1],
        yacht_notes={},
        intro_html=intro_html,
        notes_html=notes_html,
    )


def select_yachts_from_live(
    filtered: list[tuple[str, dict]],
    lead: dict,
    *,
    model: str | None = None,
    max_shortlist: int = 25,
    total_available: int | None = None,
    pro_rate_context: str | None = None,
    limited_avail_context: str | None = None,
) -> SelectionResult:
    """
    AI yacht selection for the live pipeline.

    Args:
        filtered:              [(yacht_id, live_data), ...] from filter_live_yachts(),
                               sorted cheapest first.
        lead:                  Full lead JSON from the quiz.
        model:                 OpenAI model override.
        max_shortlist:         Max yachts to send to AI (controls token cost).
        total_available:       Total yachts the search returned (before filtering).
        pro_rate_context:      Injected when prices have been pro-rated.
        limited_avail_context: Injected when few results exist for a non-standard duration.

    Returns:
        SelectionResult — or a cheap fallback if the API call fails.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("Warning: OPENAI_API_KEY not set — using fallback selection.", flush=True)
        return _fallback_result_live(filtered, lead)

    if not filtered:
        return _fallback_result_live([], lead)

    shortlist = filtered[:max_shortlist]

    summaries = [_live_summary(yid, data) for yid, data in shortlist]

    n_total = total_available if total_available is not None else len(filtered)

    lead_summary_str = _lead_summary(lead)
    if pro_rate_context:
        lead_summary_str += f"\n\n{pro_rate_context}"
    if limited_avail_context:
        lead_summary_str += f"\n\n{limited_avail_context}"

    prompt = SELECTION_PROMPT_TEMPLATE.format(
        lead_summary=lead_summary_str,
        yacht_summaries=json.dumps(summaries, indent=2, ensure_ascii=False),
        total_available=n_total,
        shortlist_count=len(summaries),
    )

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model or DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.7,
            max_tokens=2500,
            response_format={"type": "json_object"},
        )
        raw  = response.choices[0].message.content or ""
        data = json.loads(raw)

        result = SelectionResult(
            selected_ids=data.get("selected_yacht_ids", []),
            recommended_ids=data.get("recommended_yacht_ids", []),
            yacht_notes=data.get("yacht_notes", {}),
            intro_html=data.get("intro_html", ""),
            notes_html=data.get("notes_html", ""),
        )

        if not result.selected_ids:
            print("Warning: AI returned no selected IDs — using fallback.", flush=True)
            return _fallback_result_live(filtered, lead)

        return result

    except Exception as e:
        print(f"Warning: AI selection failed ({type(e).__name__}: {e}) — using fallback.",
              flush=True)
        return _fallback_result_live(filtered, lead)


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import csv
    import sys
    from pathlib import Path

    _root = Path(__file__).parent.parent
    if str(_root / "scripts") not in sys.path:
        sys.path.insert(0, str(_root / "scripts"))

    try:
        from dotenv import load_dotenv
        load_dotenv(_root / ".env")
    except ImportError:
        pass

    from build_proposal_from_csv import filter_yachts

    csv_path = _root / "yacht_database_full.csv"
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}")
        sys.exit(1)

    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))

    # Test lead matching hollie-pollak.json
    test_lead = {
        "answers": {
            "charterType": "skippered",
            "region": ["Sardinia"],
            "boatType": "monohull",
            "size": "33-40",
            "cabins": 2,
            "budget": "3-5k",
            "dates": {"start": "2026-08-16", "end": "2026-08-22"},
            "contact": {"name": "Hollie Pollak", "email": "test@test.com"},
        }
    }

    from datetime import date
    filtered = filter_yachts(rows, test_lead, date(2026, 8, 16))
    print(f"Filtered to {len(filtered)} yachts")

    result = select_yachts(filtered, test_lead)
    print(f"\nSelected: {result.selected_ids}")
    print(f"Recommended: {result.recommended_ids}")
    print(f"\nIntro HTML:\n{result.intro_html}")
    print(f"\nFirst yacht note:\n{list(result.yacht_notes.values())[:1]}")
