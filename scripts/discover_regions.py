#!/usr/bin/env python3
"""
discover_regions.py — Discover region + service IDs from booking-manager portal.

Run from the Proposals/ directory:
    .venv/bin/python scripts/discover_regions.py

What it does:
  1. Logs into the portal (using the same working auth as portal_live_search.py)
  2. For each target country, runs a broad search with no region/service filter
  3. Parses every result and extracts: serviceId, startBase, kind, model
  4. Groups service IDs by base location so you can see which services cover each area
  5. Also probes region IDs 1-80 for key countries to find valid region numbers
  6. Prints a ready-to-paste REGION_CONFIG block for portal_live_search.py

The output gives you all the filter_region and filter_service values for every
region without needing manual DevTools capture.
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

# ── Env setup ──────────────────────────────────────────────────────────────────
_root = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(_root / ".env")
except ImportError:
    pass

try:
    import requests
except ImportError:
    print("Run:  .venv/bin/pip install requests python-dotenv", file=sys.stderr)
    sys.exit(1)

PORTAL_BASE      = "https://portal.booking-manager.com"
LOGIN_URL        = f"{PORTAL_BASE}/wbm2/app/login_register/login_to_continue.jsp"
SESSION_TEST_URL = f"{PORTAL_BASE}/wbm2/app/yachts/index.jsp"
SEARCH_URL       = f"{PORTAL_BASE}/wbm2/page.html"
COMPANY_ID       = "7914"
UA               = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
)

EMAIL    = os.environ.get("BOOKING_MANAGER_EMAIL", "")
PASSWORD = os.environ.get("BOOKING_MANAGER_PASSWORD", "")

if not EMAIL or not PASSWORD:
    print("ERROR: set BOOKING_MANAGER_EMAIL and BOOKING_MANAGER_PASSWORD in .env")
    sys.exit(1)

# ── Session + login ────────────────────────────────────────────────────────────

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

_LOGIN_SIGNALS = [
    'name="login_email"', 'name="login_password"',
    'id="login-box"', "login_to_continue", "To view this page you need to login",
]

def _is_login_page(text: str) -> bool:
    return any(sig in text for sig in _LOGIN_SIGNALS)

def login() -> bool:
    print("Logging in...", flush=True)
    session.get(LOGIN_URL, timeout=20)
    r = session.post(LOGIN_URL, data={
        "is_post_back":   "1",
        "login_email":    EMAIL,
        "login_password": PASSWORD,
        "referrer":       f"{PORTAL_BASE}/wbm2/app/yachts/index.jsp",
    }, timeout=20, allow_redirects=True)
    if _is_login_page(r.text):
        print("ERROR: Login failed — check credentials.")
        return False
    # Verify session is actually valid
    test = session.get(SESSION_TEST_URL, timeout=20)
    if _is_login_page(test.text):
        print("ERROR: Session not valid after login.")
        return False
    print("Login OK.", flush=True)
    return True

if not login():
    sys.exit(1)

# ── Base payload (matches portal_live_search.py exactly) ──────────────────────

def base_payload(country: str, region: str = "", service: str = "",
                 date: str = "2026-07-05", duration: int = 7, page: int = 1) -> dict:
    return {
        "view":                       "SearchResult2",
        "responseType":               "JSON",
        "companyid":                  COMPANY_ID,
        "action":                     "getResults",
        "filter_country":             country,
        "filter_region":              region,
        "filter_service":             service,
        "filter_base":                "",
        "filterlocationdistance":     "5",
        "filter_flexibility":         "closest_day",
        "filter_model":               "",
        "filter_shipyard":            "",
        "filter_offer_type":          "-1",
        "filter_base_to":             "",
        "filter_date_from":           date,
        "filter_duration":            str(duration),
        "filter_timeslot":            "",
        "filter_service_type":        "all",
        "filter_kind":                "",
        "filter_class":               "",
        "filter_mainsail":            "",
        "filter_genoa":               "",
        "filter_length_ft":           "0-2000",
        "filter_cabins":              "0-2000",
        "filter_berths":              "0-2000",
        "filter_heads":               "0-2000",
        "filter_price":               "0-10001000",
        "filter_yachtage":            "",
        "filter_year_from":           "",
        "filter_year_to":             "",
        "filter_equipment":           "",
        "filter_availability_status": "-1",
        "filter_options":             "-1",
        "personsByGroup0":            "4",
        "personsByGroup1":            "0",
        "personsByGroup2":            "0",
        "override_checkin_rules":     "false",
        "isTrusted":                  "true",
        "_vts":                       str(int(time.time() * 1000)),
        "resultsPage":                str(page),
    }


def do_search(country: str, region: str = "", service: str = "",
              date: str = "2026-07-05", duration: int = 7, page: int = 1) -> dict:
    """Run a search and return the parsed JSON (or {} on failure)."""
    p = base_payload(country, region, service, date, duration, page)
    try:
        r = session.post(
            SEARCH_URL, data=p,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        if r.status_code != 200:
            return {}
        return r.json()
    except Exception as e:
        print(f"    [search error] {e}", flush=True)
        return {}


def parse_yachts(data: dict) -> list[dict]:
    """Extract yacht dicts from the nested response structure."""
    yachts = []
    for entry in (data.get("results") or []):
        raw_str = entry.get("data", "")
        if not raw_str:
            continue
        try:
            y = json.loads(raw_str) if isinstance(raw_str, str) else raw_str
            yachts.append(y)
        except Exception:
            pass
    return yachts


def count_results(data: dict) -> int:
    return int(data.get("resultsCount") or len(data.get("results") or []))


# ── Step 1: Country-level searches to collect serviceId → base mappings ────────

COUNTRIES = [
    ("GR", "Greece"),
    ("HR", "Croatia"),
    ("IT", "Italy"),
    ("ES", "Spain"),
    ("TR", "Turkey"),
    ("ME", "Montenegro"),
    ("FR", "France"),
    ("PT", "Portugal"),
]

# service_id → set of bases seen
service_bases: dict[str, set[str]] = defaultdict(set)
# country → service_ids
country_services: dict[str, set[str]] = defaultdict(set)
# base → service_ids
base_services: dict[str, set[str]] = defaultdict(set)

print("\n" + "="*70)
print("STEP 1 — Country-level searches (no region filter)")
print("="*70)

for cc, name in COUNTRIES:
    total = 0
    for pg in range(1, 6):  # up to 5 pages = 250 yachts per country
        data = do_search(cc, page=pg)
        yachts = parse_yachts(data)
        if not yachts:
            break
        for y in yachts:
            sid  = str(y.get("serviceId") or "").strip()
            base = str(y.get("startBase") or "").strip()
            if sid:
                service_bases[sid].add(base)
                country_services[cc].add(sid)
                if base:
                    base_services[base].add(sid)
        total += len(yachts)
        if len(yachts) < 50:
            break
        time.sleep(0.3)

    sids = sorted(country_services[cc])
    print(f"\n  {name} ({cc}): {total} yachts, {len(sids)} distinct service IDs")
    # Group by base
    cc_bases: dict[str, set[str]] = defaultdict(set)
    for sid in sids:
        for base in service_bases[sid]:
            cc_bases[base].add(sid)
    for base in sorted(cc_bases):
        print(f"    Base: {base!r:35s} → sids: {sorted(cc_bases[base])}")


# ── Step 2: Probe region IDs for key countries ─────────────────────────────────

print("\n\n" + "="*70)
print("STEP 2 — Probe region IDs 1-80 for key countries")
print("(Prints only region IDs that return > 0 yachts)")
print("="*70)

PROBE_COUNTRIES = [("GR", "Greece"), ("HR", "Croatia"), ("IT", "Italy"),
                   ("ES", "Spain"), ("TR", "Turkey"), ("ME", "Montenegro")]

# region_id → {country, count, bases, service_ids}
found_regions: list[dict] = []

for cc, cname in PROBE_COUNTRIES:
    print(f"\n  Probing {cname} ({cc}) region IDs 1–80...", flush=True)
    for rid in range(1, 81):
        data = do_search(cc, region=str(rid))
        n = count_results(data)
        if n > 0:
            yachts = parse_yachts(data)
            bases = sorted(set(
                str(y.get("startBase") or "").strip()
                for y in yachts if y.get("startBase")
            ))
            sids = sorted(set(
                str(y.get("serviceId") or "").strip()
                for y in yachts if y.get("serviceId")
            ))
            found_regions.append({
                "country": cc, "country_name": cname,
                "region_id": rid, "count": n,
                "bases": bases, "service_ids": sids,
            })
            print(f"    ✓ region_id={rid:3d}  yachts={n:3d}  "
                  f"bases={bases[:4]}  sids={sids[:6]}", flush=True)
        time.sleep(0.12)


# ── Step 3: Print ready-to-paste REGION_CONFIG ────────────────────────────────

print("\n\n" + "="*70)
print("STEP 3 — READY-TO-PASTE REGION_CONFIG")
print("Copy this block into portal_live_search.py")
print("="*70)
print()
print("REGION_CONFIG: dict[str, dict] = {")

# Italy — Sardinia already known
print('    # ── Italy ───────────────────────────────────────────────────────────')
print('    "Sardinia": {')
print('        "filter_country": "IT",')
print('        "filter_region":  "21",')
print('        "filter_service": "648,6723,618,859,7840,7771,3044,4664,2971,260,1230,4276,129,2889,2903,2653,8736",')
print('    },')

prev_cc = None
for info in found_regions:
    cc   = info["country"]
    rid  = info["region_id"]
    sids = ",".join(info["service_ids"])
    bases_str = " / ".join(b for b in info["bases"][:5] if b)

    if cc != prev_cc:
        cname = info["country_name"]
        print(f'')
        print(f'    # ── {cname} {"─"*(50-len(cname))}')
        prev_cc = cc

    label = bases_str if bases_str else f"{cc} region {rid}"
    print(f'    "{label}": {{')
    print(f'        "filter_country": "{cc}",')
    print(f'        "filter_region":  "{rid}",')
    print(f'        "filter_service": "{sids}",')
    print(f'    }},')

print("}")

# ── Step 4: Summary — base → service IDs ──────────────────────────────────────

print("\n\n" + "="*70)
print("STEP 4 — Base → Service ID mapping (for manual tuning)")
print("="*70)
for base in sorted(base_services):
    if base:
        sids = sorted(base_services[base])
        print(f"  {base!r:40s} → {sids}")

print("\nDone.")
