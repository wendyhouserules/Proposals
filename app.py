#!/usr/bin/env python3
"""
app.py — SailScanner Proposal Builder API
==========================================

FastAPI endpoint that Make.com calls when a new lead comes in.

Orchestrates the full pipeline:
  Lead JSON → filter yachts → AI select → build payload → upload to WordPress → return URL

Endpoints:
  GET  /health          → {"status": "ok", "yachts_loaded": N}
  POST /build-proposal  → {"status": "ok", "proposal_url": "https://..."}

Auth:
  Requests must include header: X-Api-Secret: <SAILSCANNER_API_SECRET>
  Set SAILSCANNER_API_SECRET in .env. If not set, auth is skipped (dev mode).

Run locally:
  cd Proposals/
  .venv/bin/uvicorn app:app --reload --port 8000

Deploy (Hetzner):
  .venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000

Test with curl:
  curl -X POST http://localhost:8000/build-proposal \\
    -H "Content-Type: application/json" \\
    -H "X-Api-Secret: your_secret" \\
    -d @scripts/input_files/hollie-pollak.json
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

# ── Load .env before importing anything that reads env vars ───────────────────
_project_root = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")
except ImportError:
    pass

# ── Add scripts/ to path ──────────────────────────────────────────────────────
_scripts_dir = _project_root / "scripts"
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

# ── Imports ───────────────────────────────────────────────────────────────────
import smtplib
import traceback
from email.mime.text import MIMEText

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:
    raise ImportError("Run: pip install fastapi uvicorn")

from portal_live_search import live_search_all
from live_proposal_builder import (
    filter_live_yachts, fetch_yacht_photos, live_yacht_to_ss_data,
    pro_rate_live_results, standard_search_duration,
)
from build_proposal_from_csv import inject_crew_services
from proposal_import import create_proposal
from ai_select import select_yachts_from_live

# ── Config from .env ──────────────────────────────────────────────────────────
WP_USER          = os.environ.get("SAILSCANNER_WP_USER", "")
WP_PASSWORD      = os.environ.get("SAILSCANNER_WP_APP_PASSWORD", "")
WP_BASE          = os.environ.get("SAILSCANNER_WP_URL", "https://sailscanner.ai").rstrip("/")
API_SECRET       = os.environ.get("SAILSCANNER_API_SECRET", "")
CONTACT_EMAIL    = os.environ.get("SAILSCANNER_CONTACT_EMAIL", "chris@sailscanner.ai")
CONTACT_WHATSAPP = os.environ.get("SAILSCANNER_CONTACT_WHATSAPP", "")
ALERT_EMAIL      = os.environ.get("SAILSCANNER_ALERT_EMAIL", CONTACT_EMAIL)
SMTP_HOST        = os.environ.get("SAILSCANNER_SMTP_HOST", "")
SMTP_PORT        = int(os.environ.get("SAILSCANNER_SMTP_PORT", "587"))
SMTP_USER        = os.environ.get("SAILSCANNER_SMTP_USER", "")
SMTP_PASS        = os.environ.get("SAILSCANNER_SMTP_PASS", "")

if "/wp-json" in WP_BASE:
    WP_BASE = WP_BASE.split("/wp-json")[0]

# ── Alert helper ──────────────────────────────────────────────────────────────

def _send_alert(subject: str, body: str) -> None:
    """
    Send an alert email to SAILSCANNER_ALERT_EMAIL.
    Tries Resend API first (more reliable), then falls back to direct SMTP.
    Supports port 465 (implicit SSL) and port 587 (STARTTLS).
    Fails silently if neither is configured — error is still logged to stdout.
    Configure in .env: RESEND_API_KEY and/or SAILSCANNER_SMTP_* vars.
    """
    print(f"ALERT: {subject}", flush=True)
    print(body, flush=True)

    full_subject = f"[SailScanner] {subject}"
    resend_key   = os.environ.get("RESEND_API_KEY", "")

    # ── 1. Try Resend API (primary — no SMTP firewall issues) ─────────────────
    if resend_key and ALERT_EMAIL:
        try:
            import urllib.request
            from_addr = "noreply@mail.sailscanner.ai"
            payload = json.dumps({
                "from":    f"SailScanner Alerts <{from_addr}>",
                "to":      [ALERT_EMAIL],
                "subject": full_subject,
                "text":    body,
            }).encode()
            req = urllib.request.Request(
                "https://api.resend.com/emails",
                data=payload,
                headers={
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type":  "application/json",
                },
            )
            urllib.request.urlopen(req, timeout=10)
            print(f"Alert sent via Resend to {ALERT_EMAIL}", flush=True)
            return
        except Exception as exc:
            print(f"WARNING: Resend failed ({exc}), falling back to SMTP", flush=True)

    # ── 2. SMTP fallback ──────────────────────────────────────────────────────
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS or not ALERT_EMAIL:
        print("(No alert channel configured — alert logged only)", flush=True)
        return

    try:
        import ssl
        msg = MIMEText(body)
        msg["Subject"] = full_subject
        msg["From"]    = SMTP_USER
        msg["To"]      = ALERT_EMAIL

        if SMTP_PORT == 465:
            # Implicit SSL (no STARTTLS handshake)
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT,
                                   context=ssl.create_default_context(),
                                   timeout=10) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        else:
            # Explicit TLS via STARTTLS (port 587)
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)

        print(f"Alert sent via SMTP to {ALERT_EMAIL}", flush=True)
    except Exception as exc:
        print(f"WARNING: Failed to send alert email: {exc}", flush=True)

# ── Run summary helper ────────────────────────────────────────────────────────

def _send_run_summary(lead_label: str, status: str, lines: list[str]) -> None:
    """
    Send a brief run summary after every proposal request — success or failure.
    status: "ok" | "manual_required" | "error"
    """
    icon = {"ok": "✅", "manual_required": "⚠️", "error": "❌"}.get(status, "ℹ️")
    subject = f"{icon} Proposal run [{status.upper()}] — {lead_label}"
    body = "\n".join(lines)
    _send_alert(subject, body)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="SailScanner Proposal Builder", version="2.0.0")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_lead_dates(lead: dict) -> tuple:
    """Return (lead_start_date, from_str, to_str, duration_days)."""
    answers   = lead.get("answers") or {}
    dates     = answers.get("dates") or {}
    start_iso = dates.get("start", "")
    end_iso   = dates.get("end", "")

    lead_start: date | None = None
    from_str = to_str = ""
    duration_days = 7

    if start_iso:
        try:
            d = date.fromisoformat(start_iso)
            lead_start = d
            from_str = f"{d.day} {d.strftime('%B %Y')}"
        except ValueError:
            pass
    if end_iso:
        try:
            d = date.fromisoformat(end_iso)
            to_str = f"{d.day} {d.strftime('%B %Y')}"
            if lead_start:
                duration_days = max(3, (d - lead_start).days)  # min 3 nights
        except ValueError:
            pass

    return lead_start, from_str, to_str, duration_days


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": "2.0.0 (live pipeline)",
        "wp_configured": bool(WP_USER and WP_PASSWORD),
    }


@app.post("/build-proposal")
async def build_proposal(request: Request) -> dict:
    """
    Build a personalised proposal from a lead JSON and return the WordPress URL.

    Pipeline (v2 — live data only, no CSV):
      1. Auth check
      2. Parse lead JSON
      3. Live search → all available yachts for exact dates
      4. Filter by lead criteria (cabins, budget, boat type, size)
      5. AI selects 4–6 best yachts + writes personalised copy
      6. Fetch full photo gallery for each selected yacht
      7. Build proposal payload
      8. POST to WordPress → get URL
      9. Return URL to Make.com

    On any unexpected failure: sends alert email, returns error response to Make.com.
    Make.com must have an error handler configured to notify Chris.
    """

    # ── 1. Auth ───────────────────────────────────────────────────────────────
    if API_SECRET:
        incoming = request.headers.get("x-api-secret", "")
        if incoming != API_SECRET:
            raise HTTPException(status_code=401,
                                detail="Invalid or missing X-Api-Secret header")

    # ── 2. Parse lead ─────────────────────────────────────────────────────────
    try:
        lead = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON")

    if not isinstance(lead, dict):
        raise HTTPException(status_code=400, detail="Lead must be a JSON object")

    answers = lead.get("answers") or {}
    contact = answers.get("contact") or {}
    # Handle both old {name} and new {firstName, lastName} contact formats
    contact_name = (
        f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()
        or contact.get("name", "Unknown")
    )
    region_raw = answers.get("region") or ""
    region_str = (region_raw[0] if isinstance(region_raw, list) else region_raw).strip()
    # Some destinations (Seychelles, Thailand) skip the region step — fall back to country
    if not region_str:
        region_str = (answers.get("country") or "").strip()

    lead_label = (
        f"{contact_name} | {region_str} | "
        f"{(answers.get('dates') or {}).get('start', '?')}"
    )
    print(f"New lead: {lead_label}", flush=True)

    # Collect a run log for the always-on summary email
    run_log: list[str] = [
        f"Lead:   {lead_label}",
        f"Region: {region_str}",
        f"Dates:  {(answers.get('dates') or {}).get('start', '?')} → {(answers.get('dates') or {}).get('end', '?')}",
        f"Guests: {answers.get('guests', {})}  |  Budget: {answers.get('budget', '?')}  |  Cabins: {answers.get('cabins', '?')}",
        "",
    ]

    try:
        # ── 3. Live search ────────────────────────────────────────────────────
        lead_start, from_str, to_str, duration_days = _parse_lead_dates(lead)
        start_iso = (answers.get("dates") or {}).get("start", "")
        # Handle both old flat {adults, children} and new nested {guests: {adults, children}}
        guests_raw = answers.get("guests") or {}
        if isinstance(guests_raw, dict):
            adults   = int(guests_raw.get("adults") or 2)
            children = int(guests_raw.get("children") or 0)
        else:
            adults   = int(guests_raw or answers.get("adults") or 2)
            children = int(answers.get("children") or 0)

        if not region_str or not start_iso:
            raise ValueError("Lead is missing region or start date")

        # Search with actual duration first
        print(f"Live search: {region_str} / {start_iso} / {duration_days} nights", flush=True)
        live_results = live_search_all(
            region=region_str,
            date_from=start_iso,
            duration=duration_days,
            adults=adults,
            children=children,
            flexibility="closest_day",
        )
        total_available      = len(live_results)
        original_total       = total_available  # remember count before any retry
        print(f"Live search returned {total_available} yachts", flush=True)

        # If too few results, retry with the standard duration and apply pro-rating
        pro_rated  = False
        std_days   = standard_search_duration(duration_days)
        if total_available < 5 and std_days != duration_days:
            print(
                f"Too few results ({total_available}) — retrying with "
                f"{std_days}-day duration + pro-rating ({duration_days}/{std_days})",
                flush=True,
            )
            live_results = live_search_all(
                region=region_str,
                date_from=start_iso,
                duration=std_days,
                adults=adults,
                children=children,
                flexibility="closest_day",
            )
            total_available = len(live_results)
            print(f"Retry returned {total_available} yachts", flush=True)

            if total_available > 0:
                live_results = pro_rate_live_results(live_results, duration_days, std_days)
                pro_rated = True

        if total_available == 0:
            run_log.append(f"Portal search: 0 yachts found for '{region_str}' on {start_iso}.")
            run_log.append("→ No live results — manual build required.")
            _send_alert(
                f"No live results — manual required: {lead_label}",
                f"Region '{region_str}' returned 0 results from the portal live search.\n"
                f"Lead: {lead_label}\n\nPlease build this proposal manually.",
            )
            _send_run_summary(lead_label, "manual_required", run_log)
            return {
                "status": "manual_required",
                "reason": "no_live_results",
                "region": region_str,
                "message": (
                    f"No yachts available for '{region_str}' on {start_iso}. "
                    "Please handle this proposal manually."
                ),
            }

        # ── 4. Filter ─────────────────────────────────────────────────────────
        filtered = filter_live_yachts(live_results, lead)
        print(f"Filtered to {len(filtered)} yachts matching lead criteria", flush=True)

        # ── Progressive filter relaxation (target: ≥3 yachts) ────────────────
        # Parse original budget ceiling and size range from lead
        from live_proposal_builder import BUDGET_RANGES, _parse_size_range as _psr
        _budget_str = (answers.get("budget") or "").strip().lower()
        _, _orig_bmax = BUDGET_RANGES.get(_budget_str, (0, float("inf")))
        _size_str = (answers.get("size") or "").strip()
        _orig_smin, _orig_smax = _psr(_size_str)

        _INF = float("inf")
        _TARGET = 3
        relaxation_applied = ""

        if len(filtered) < _TARGET:
            # Step 1: widen budget by €2k
            _bmax = _orig_bmax + 2_000 if _orig_bmax != _INF else _INF
            filtered = filter_live_yachts(live_results, lead, budget_max_override=_bmax)
            print(f"Relaxation step 1 (budget +2k → {_bmax:,.0f}): {len(filtered)} yachts", flush=True)
            if len(filtered) >= _TARGET:
                relaxation_applied = "budget widened by €2k"

        if len(filtered) < _TARGET:
            # Step 2: also widen size by ±5ft
            _bmax = _orig_bmax + 2_000 if _orig_bmax != _INF else _INF
            _smin = max(0, _orig_smin - 5)
            _smax = _orig_smax + 5 if _orig_smax != _INF else _INF
            filtered = filter_live_yachts(live_results, lead,
                budget_max_override=_bmax,
                size_range_override=(_smin, _smax))
            print(f"Relaxation step 2 (size ±5ft): {len(filtered)} yachts", flush=True)
            if len(filtered) >= _TARGET:
                relaxation_applied = "budget widened by €2k, size ±5ft"

        if len(filtered) < _TARGET:
            # Step 3: widen budget by another €2k (total +4k), keep size ±5ft
            _bmax = _orig_bmax + 4_000 if _orig_bmax != _INF else _INF
            _smin = max(0, _orig_smin - 5)
            _smax = _orig_smax + 5 if _orig_smax != _INF else _INF
            filtered = filter_live_yachts(live_results, lead,
                budget_max_override=_bmax,
                size_range_override=(_smin, _smax))
            print(f"Relaxation step 3 (budget +4k total): {len(filtered)} yachts", flush=True)
            if len(filtered) >= _TARGET:
                relaxation_applied = "budget widened by €4k, size ±5ft"

        if len(filtered) < _TARGET:
            # Step 4: remove size filter entirely, keep budget at +4k
            _bmax = _orig_bmax + 4_000 if _orig_bmax != _INF else _INF
            filtered = filter_live_yachts(live_results, lead,
                budget_max_override=_bmax,
                size_range_override=(0, _INF))
            print(f"Relaxation step 4 (size removed): {len(filtered)} yachts", flush=True)
            if len(filtered) >= _TARGET:
                relaxation_applied = "budget widened by €4k, size filter removed"

        boat_type_context = None
        if len(filtered) < _TARGET:
            # Step 5: open to sailing boats AND catamarans (never gulets/motorboats)
            _bmax = _orig_bmax + 4_000 if _orig_bmax != _INF else _INF
            filtered = filter_live_yachts(live_results, lead,
                budget_max_override=_bmax,
                size_range_override=(0, _INF),
                allow_sailing_and_cats=True)
            print(f"Relaxation step 5 (sail+cats, no size): {len(filtered)} yachts", flush=True)
            if len(filtered) >= _TARGET:
                relaxation_applied = "budget widened, size filter removed, opened to both sailing yachts and catamarans"

                # Detect preferred boat type and sort matching yachts to the top
                _preferred_kind = (answers.get("boatType") or "").strip().lower()
                _kind_map = {"catamaran": "Catamaran", "monohull": "Sail boat", "sailing yacht": "Sail boat"}
                _preferred_portal_kind = _kind_map.get(_preferred_kind)

                if _preferred_portal_kind:
                    # Sort: preferred type first, then others
                    filtered = (
                        [(yid, d) for yid, d in filtered if d.get("kind") == _preferred_portal_kind] +
                        [(yid, d) for yid, d in filtered if d.get("kind") != _preferred_portal_kind]
                    )
                    _preferred_label = "catamaran" if _preferred_portal_kind == "Catamaran" else "sailing monohull"
                    _other_label = "sailing monohulls" if _preferred_portal_kind == "Catamaran" else "catamarans"
                    _preferred_count = sum(1 for _, d in filtered if d.get("kind") == _preferred_portal_kind)
                    if _preferred_count > 0:
                        boat_type_context = (
                            f"NOTE — boat type availability: the client requested a {_preferred_label}. "
                            f"We found {_preferred_count} {_preferred_label}(s) plus additional {_other_label} "
                            f"after widening the filters. Prioritise the {_preferred_label}(s) in your selection "
                            f"and recommend one as the top pick if it fits the budget and cabin requirements. "
                            f"Only include {_other_label} if needed to reach 4 options. "
                            f"Mention naturally in the intro that {_preferred_label} availability was limited "
                            f"for these dates and you have included the best available options."
                        )
                    else:
                        boat_type_context = (
                            f"NOTE — boat type: the client requested a {_preferred_label} but none were "
                            f"available for these dates within budget. We have included the best available "
                            f"{_other_label} instead. Mention this clearly and sympathetically in the intro, "
                            f"and let them know you can search again for different dates if they want to "
                            f"hold out for a {_preferred_label}."
                        )

        if relaxation_applied:
            print(f"Filters relaxed: {relaxation_applied}", flush=True)

        if not filtered:
            run_log.append(f"Portal search: {total_available} yachts found.")
            run_log.append("Filter: 0 yachts matched lead criteria (cabins, size, type) even after budget relaxation.")
            run_log.append("→ Manual build required.")
            _send_alert(
                f"No matching yachts after filter — manual required: {lead_label}",
                f"Live search returned {total_available} yachts for '{region_str}' "
                f"but none matched the lead criteria (cabins, size, type).\n"
                f"Lead: {lead_label}\n\nPlease build this proposal manually.",
            )
            _send_run_summary(lead_label, "manual_required", run_log)
            return {
                "status": "manual_required",
                "reason": "no_matching_yachts",
                "region": region_str,
                "message": "No yachts matched the lead criteria. Please handle manually.",
            }

        # ── 5. AI selection ───────────────────────────────────────────────────
        # Build context strings for the AI based on what happened during search.
        #
        # Combinations:
        #   pro_rated=True          → searched actual duration, < 5 results, retried at
        #                             std_days and pro-rated prices. Always set both contexts.
        #   pro_rated=False,
        #     original_total < 15,
        #     non-standard duration → found some results but slim pickings; mention
        #                             standard durations to client.
        #   everything else         → standard situation, no special note needed.

        pro_rate_context      = None
        limited_avail_context = None

        if pro_rated:
            pro_rate_context = (
                f"⚠️ IMPORTANT — PRO-RATED PRICES. You MUST include ALL of the following "
                f"points in your intro paragraph 1. Do not skip or paraphrase:\n"
                f"(1) We searched for the client's exact {duration_days}-night charter "
                f"but only found {original_total} yacht(s) available for those precise dates.\n"
                f"(2) We therefore searched the standard {std_days}-night charter listings "
                f"— this is how most providers in this region operate.\n"
                f"(3) The prices shown have been pro-rated (scaled down) from the {std_days}-night "
                f"rate to {duration_days} nights and are estimates only.\n"
                f"(4) In peak season, providers may not be willing to offer charters shorter "
                f"than 7 nights — availability is not guaranteed at this duration.\n"
                f"(5) We will confirm the exact rate and availability with the provider "
                f"before the client commits to anything.\n"
                f"(6) If they'd like more options, we can search {std_days}-night charters "
                f"and adjust the dates slightly."
            )
            limited_avail_context = (
                f"NOTE — also make clear in the intro that {std_days}-night charters are "
                f"the standard in this region and have the widest selection; shorter durations "
                f"are possible but availability is limited, especially in peak season."
            )
        elif original_total < 15 and duration_days not in (7, 14):
            limited_avail_context = (
                f"NOTE — availability is limited for this {duration_days}-night duration "
                f"(only {original_total} yachts found). Let the client know naturally in "
                f"the intro that 7- and 14-night charters are the standard and have the "
                f"widest selection, and that you are happy to search either duration if "
                f"they would like more options to choose from."
            )

        selection = select_yachts_from_live(
            filtered, lead,
            total_available=total_available,
            pro_rate_context=pro_rate_context,
            limited_avail_context=limited_avail_context,
            boat_type_context=boat_type_context,
        )
        print(
            f"AI selected {len(selection.selected_ids)} yachts, "
            f"{len(selection.recommended_ids)} recommended",
            flush=True,
        )

        # Map selected IDs back to live data (preserves AI ordering)
        live_by_id    = {yid: data for yid, data in filtered}
        selected_live = [(yid, live_by_id[yid])
                         for yid in selection.selected_ids if yid in live_by_id]

        # Fallback if AI returned no valid IDs
        if not selected_live:
            print("Warning: AI returned no valid IDs — using top 5 cheapest", flush=True)
            selected_live = filtered[:5]

        # ── 6. Fetch photos + build yacht data ────────────────────────────────
        yacht_data: list[dict] = []
        for yid, live_data in selected_live:
            # Fetch full photo gallery and deck plan from detail page
            details_url           = live_data.get("details_url", "")
            photos, deck_plan_url = fetch_yacht_photos(details_url)
            if not photos:
                # Fallback to the two search thumbnails
                photos = [u for u in [live_data.get("image_url"),
                                       live_data.get("interior_url")] if u]

            entry = live_yacht_to_ss_data(
                yid, live_data, photos, lead, region_str, from_str, to_str,
                deck_plan_url=deck_plan_url,
            )
            inject_crew_services(entry, lead, display_label=entry.get("display_name", yid))

            # Attach AI notes and recommended flag
            if yid in selection.yacht_notes:
                entry["ai_recommendation_note"] = selection.yacht_notes[yid]
            if yid in selection.recommended_ids:
                entry["recommended"] = True

            if entry.get("display_name"):
                yacht_data.append(entry)

        if not yacht_data:
            raise RuntimeError("Could not build any valid yacht entries from live data")

        # ── 7. Upload to WordPress ────────────────────────────────────────────
        if not WP_USER or not WP_PASSWORD:
            raise RuntimeError("WordPress credentials not set in .env")

        result = create_proposal(
            yacht_data,
            auth=(WP_USER, WP_PASSWORD),
            intro_html=selection.intro_html,
            itinerary_html="",
            notes_html=selection.notes_html,
            contact_whatsapp=CONTACT_WHATSAPP,
            contact_email=CONTACT_EMAIL,
            lead=lead,
        )

        # ── 8. Extract and return URL ─────────────────────────────────────────
        proposal_url = result.get("proposal_url", "")
        if not proposal_url and result.get("ss_token"):
            proposal_url = f"{WP_BASE}/proposals/{result['ss_token']}/"
        if not proposal_url:
            proposal_url = result.get("link", "")

        print(f"Proposal ready: {proposal_url}", flush=True)

        run_log.append(f"Portal search: {total_available} yachts found{' (pro-rated from ' + str(std_days) + '-night)' if pro_rated else ''}.")
        run_log.append(f"Filter:        {len(filtered)} matched lead criteria.")
        run_log.append(f"AI selected:   {len(yacht_data)} yachts ({len([y for y in yacht_data if y.get('recommended')])} recommended).")
        run_log.append(f"Proposal URL:  {proposal_url}")
        _send_run_summary(lead_label, "ok", run_log)

        return {
            "status": "ok",
            "proposal_url": proposal_url,
            "yachts_selected": len(yacht_data),
            "yachts_recommended": len([y for y in yacht_data if y.get("recommended")]),
        }

    except Exception as exc:
        tb = traceback.format_exc()
        run_log.append(f"ERROR: {type(exc).__name__}: {exc}")
        run_log.append("")
        run_log.append("Traceback:")
        run_log.append(tb)
        run_log.append("→ Please build this proposal manually.")
        _send_alert(
            f"Proposal build FAILED — manual required: {lead_label}",
            f"An unexpected error occurred building the proposal.\n\n"
            f"Lead: {lead_label}\n\n"
            f"Error: {type(exc).__name__}: {exc}\n\n"
            f"Traceback:\n{tb}\n\n"
            f"Please build this proposal manually using the MMK export process.",
        )
        _send_run_summary(lead_label, "error", run_log)
        # Return error to Make.com — Make.com error handler should notify Chris
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "reason": f"{type(exc).__name__}: {exc}",
                "lead": lead_label,
                "message": "Proposal build failed. Please build manually — alert sent.",
            },
        )
