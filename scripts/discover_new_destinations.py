#!/usr/bin/env python3
"""
discover_new_destinations.py — Find portal country codes + region IDs for
Bahamas, Seychelles, Thailand, and British Virgin Islands.

Run from the Proposals/ directory:
    .venv/bin/python scripts/discover_new_destinations.py

Takes ~3 minutes (probes region IDs 1–200 for each confirmed country code).
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(_root / ".env")
except ImportError:
    pass

try:
    import requests
except ImportError:
    print("Run: .venv/bin/pip install requests python-dotenv", file=sys.stderr)
    sys.exit(1)

PORTAL_BASE      = "https://portal.booking-manager.com"
LOGIN_URL        = f"{PORTAL_BASE}/wbm2/app/login_register/login_to_continue.jsp"
SESSION_TEST_URL = f"{PORTAL_BASE}/wbm2/app/yachts/index.jsp"
SEARCH_URL       = f"{PORTAL_BASE}/wbm2/page.html"
COMPANY_ID       = "7914"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36")

EMAIL    = os.environ.get("BOOKING_MANAGER_EMAIL", "")
PASSWORD = os.environ.get("BOOKING_MANAGER_PASSWORD", "")

if not EMAIL or not PASSWORD:
    print("ERROR: set BOOKING_MANAGER_EMAIL and BOOKING_MANAGER_PASSWORD in .env")
    sys.exit(1)

session = requests.Session()
session.headers.update({
    "User-Agent":      UA,
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin":          PORTAL_BASE,
    "Referer":         f"{PORTAL_BASE}/wbm2/app/yachts/index.jsp",
    "Sec-Fetch-Dest":  "empty",
    "Sec-Fetch-Mode":  "cors",
    "Sec-Fetch-Site":  "same-origin",
})

_LOGIN_SIGNALS = ['name="login_email"', 'name="login_password"',
                  'id="login-box"', "login_to_continue"]

def login() -> bool:
    print("Logging in...", flush=True)
    session.get(LOGIN_URL, timeout=20)
    r = session.post(LOGIN_URL, data={
        "is_post_back": "1", "login_email": EMAIL,
        "login_password": PASSWORD,
        "referrer": f"{PORTAL_BASE}/wbm2/app/yachts/index.jsp",
    }, timeout=20, allow_redirects=True)
    if any(s in r.text for s in _LOGIN_SIGNALS):
        print("ERROR: Login failed.")
        return False
    test = session.get(SESSION_TEST_URL, timeout=20)
    if any(s in test.text for s in _LOGIN_SIGNALS):
        print("ERROR: Session invalid.")
        return False
    print("Login OK.", flush=True)
    return True

if not login():
    sys.exit(1)

def search(country: str, region: str = "", service: str = "",
           date: str = "2026-07-17", duration: int = 7) -> dict:
    payload = {
        "view": "SearchResult2", "responseType": "JSON",
        "companyid": COMPANY_ID, "action": "getResults",
        "filter_country": country, "filter_region": region,
        "filter_service": service, "filter_base": "",
        "filterlocationdistance": "5", "filter_flexibility": "closest_day",
        "filter_model": "", "filter_shipyard": "", "filter_offer_type": "-1",
        "filter_base_to": "", "filter_date_from": date,
        "filter_duration": str(duration), "filter_timeslot": "",
        "filter_service_type": "all", "filter_kind": "", "filter_class": "",
        "filter_mainsail": "", "filter_genoa": "",
        "filter_length_ft": "0-2000", "filter_cabins": "0-2000",
        "filter_berths": "0-2000", "filter_heads": "0-2000",
        "filter_price": "0-10001000", "filter_yachtage": "",
        "filter_year_from": "", "filter_year_to": "", "filter_equipment": "",
        "filter_availability_status": "-1", "filter_options": "-1",
        "personsByGroup0": "4", "personsByGroup1": "0", "personsByGroup2": "0",
        "override_checkin_rules": "false", "isTrusted": "true",
        "_vts": str(int(time.time() * 1000)), "resultsPage": "1",
    }
    try:
        r = session.post(SEARCH_URL, data=payload,
                         headers={"Content-Type": "application/x-www-form-urlencoded"},
                         timeout=30)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}

def parse(data: dict) -> list[dict]:
    yachts = []
    for entry in (data.get("results") or []):
        raw = entry.get("data", "")
        try:
            yachts.append(json.loads(raw) if isinstance(raw, str) else raw)
        except Exception:
            pass
    return yachts

def count(data: dict) -> int:
    return int(data.get("resultsCount") or len(data.get("results") or []))

# ── Step 1: Try candidate country codes (no region filter) ────────────────────

# Each entry: (display_name, [codes_to_try])
CANDIDATES = [
    ("Bahamas",                ["BS", "BH", "BAH", "BHS"]),
    ("Seychelles",             ["SC", "SYC", "SEY"]),
    ("Thailand",               ["TH", "THA"]),
    ("British Virgin Islands", ["VG", "BVI", "VI", "VGB"]),
]

print("\n" + "="*65)
print("STEP 1 — Probe country codes (date: 2026-07-17, 7 nights)")
print("="*65)

confirmed: list[tuple[str, str]] = []  # (display_name, working_code)

for display_name, codes in CANDIDATES:
    print(f"\n  {display_name}:")
    for code in codes:
        data = search(code)
        n = count(data)
        yachts = parse(data)
        if n > 0:
            sids = sorted(set(str(y.get("serviceId","")) for y in yachts if y.get("serviceId")))
            bases = sorted(set(str(y.get("startBase","")) for y in yachts if y.get("startBase")))
            print(f"    ✓ code={code!r:6s}  yachts={n}  bases={bases[:4]}  sids={sids[:6]}")
            confirmed.append((display_name, code))
            break
        else:
            print(f"    ✗ code={code!r:6s}  → 0 results")
        time.sleep(0.2)

# ── Step 2: Probe region IDs 1–200 for confirmed countries ───────────────────

print("\n\n" + "="*65)
print("STEP 2 — Probe region IDs 1–200 for confirmed countries")
print("="*65)

found_regions = []

for display_name, cc in confirmed:
    print(f"\n  Probing {display_name} ({cc}) region IDs 1–200...", flush=True)
    for rid in range(1, 201):
        data = search(cc, region=str(rid))
        n = count(data)
        if n > 0:
            yachts = parse(data)
            bases = sorted(set(str(y.get("startBase","")).strip() for y in yachts if y.get("startBase")))
            sids  = sorted(set(str(y.get("serviceId","")).strip() for y in yachts if y.get("serviceId")))
            found_regions.append({
                "name": display_name, "country": cc,
                "region_id": rid, "count": n,
                "bases": bases, "service_ids": sids,
            })
            print(f"    ✓ region_id={rid:3d}  yachts={n:3d}  bases={bases[:3]}  sids={sids[:5]}")
        time.sleep(0.12)

# ── Step 3: Print REGION_CONFIG block ─────────────────────────────────────────

print("\n\n" + "="*65)
print("STEP 3 — READY-TO-PASTE REGION_CONFIG entries")
print("="*65)

for info in found_regions:
    cc   = info["country"]
    rid  = info["region_id"]
    sids = ",".join(info["service_ids"])
    name = info["name"]
    bases_str = " / ".join(b for b in info["bases"][:4] if b)
    label = bases_str or f"{name} region {rid}"
    print(f'    # {name} — region {rid} ({bases_str})')
    print(f'    "{label}": {{')
    print(f'        "filter_country": "{cc}",')
    print(f'        "filter_region":  "{rid}",')
    print(f'        "filter_service": "{sids}",')
    print(f'    }},')

# Also print country-level fallback entries (no region filter)
print(f'\n    # Country-level fallbacks (no region filter):')
for display_name, cc in confirmed:
    # Collect all service IDs from country search
    data = search(cc)
    yachts = parse(data)
    sids = sorted(set(str(y.get("serviceId","")).strip() for y in yachts if y.get("serviceId")))
    print(f'    "{display_name}": {{"filter_country": "{cc}", "filter_region": "", "filter_service": "{",".join(sids)}"}},')

print("\nDone.")
