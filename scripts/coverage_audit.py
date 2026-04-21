#!/usr/bin/env python3
"""
coverage_audit.py — Audit every REGION_CONFIG location for sailing/catamaran inventory.

For each unique portal config (country + region + service), queries the portal on
three spread-out dates and counts available sailing yachts + catamarans.

Flags:
    DEAD   — 0 results on ALL three dates  → remove from quiz
    THIN   — avg < 3 across dates          → review
    OK     — avg ≥ 3                       → keep

Run from the Proposals/ directory:
    .venv/bin/python scripts/coverage_audit.py

Output:
    • Terminal summary (sorted worst → best)
    • coverage_audit_results.csv  (in the Proposals/ root)

Takes ~5-10 minutes (≈3 API calls per unique location × 0.3s delay).
"""

from __future__ import annotations

import csv
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

# ── Import REGION_CONFIG from sibling module ───────────────────────────────────
sys.path.insert(0, str(_root))
try:
    from scripts.portal_live_search import REGION_CONFIG
except Exception as exc:
    print(f"ERROR: Could not import REGION_CONFIG: {exc}", file=sys.stderr)
    sys.exit(1)

# ── Portal auth ────────────────────────────────────────────────────────────────

PORTAL_BASE      = "https://portal.booking-manager.com"
LOGIN_URL        = f"{PORTAL_BASE}/wbm2/app/login_register/login_to_continue.jsp"
SESSION_TEST_URL = f"{PORTAL_BASE}/wbm2/app/yachts/index.jsp"
SEARCH_URL       = f"{PORTAL_BASE}/wbm2/page.html"
COMPANY_ID       = "7914"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36")

EMAIL    = os.environ.get("BOOKING_MANAGER_EMAIL", "").strip()
PASSWORD = os.environ.get("BOOKING_MANAGER_PASSWORD", "").strip()

if not EMAIL or not PASSWORD:
    print("ERROR: Set BOOKING_MANAGER_EMAIL and BOOKING_MANAGER_PASSWORD in .env",
          file=sys.stderr)
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
                  'id="login-box"', "login_to_continue",
                  "To view this page you need to login"]


def _login() -> bool:
    print("Logging in to booking-manager portal...", flush=True)
    session.get(LOGIN_URL, timeout=20)
    r = session.post(LOGIN_URL, data={
        "is_post_back": "1",
        "login_email": EMAIL,
        "login_password": PASSWORD,
        "referrer": f"{PORTAL_BASE}/wbm2/app/yachts/index.jsp",
    }, timeout=20, allow_redirects=True)
    if any(s in r.text for s in _LOGIN_SIGNALS):
        print("ERROR: Login failed — check credentials.", file=sys.stderr)
        return False
    test = session.get(SESSION_TEST_URL, timeout=20)
    if any(s in test.text for s in _LOGIN_SIGNALS):
        print("ERROR: Session invalid after login.", file=sys.stderr)
        return False
    print("Login OK.", flush=True)
    return True


if not _login():
    sys.exit(1)

# ── Search helper ──────────────────────────────────────────────────────────────

SAILING_KINDS = {"Sail boat", "Catamaran"}


def _search_count(country: str, region: str, service: str,
                  date: str, duration: int = 7) -> int:
    """
    Fire one search and return number of sailing/cat yachts found (any price, any size).
    Does client-side kind filtering — gulets/motorboats are excluded.
    """
    payload = {
        "view":                     "SearchResult2",
        "responseType":             "JSON",
        "companyid":                COMPANY_ID,
        "action":                   "getResults",
        "filter_country":           country,
        "filter_region":            region,
        "filter_service":           service,
        "filter_base":              "",
        "filterlocationdistance":   "5",
        "filter_flexibility":       "closest_day",
        "filter_model":             "",
        "filter_shipyard":          "",
        "filter_offer_type":        "-1",
        "filter_base_to":           "",
        "filter_date_from":         date,
        "filter_duration":          str(duration),
        "filter_timeslot":          "",
        "filter_service_type":      "all",
        "filter_kind":              "",          # no kind filter at API level
        "filter_class":             "",
        "filter_mainsail":          "",
        "filter_genoa":             "",
        "filter_length_ft":         "0-2000",   # any size
        "filter_cabins":            "0-2000",
        "filter_berths":            "0-2000",
        "filter_heads":             "0-2000",
        "filter_price":             "0-10001000",  # unlimited budget
        "filter_yachtage":          "",
        "filter_year_from":         "",
        "filter_year_to":           "",
        "filter_equipment":         "",
        "filter_availability_status": "-1",
        "filter_options":           "-1",
        "personsByGroup0":          "4",
        "personsByGroup1":          "0",
        "personsByGroup2":          "0",
        "override_checkin_rules":   "false",
        "isTrusted":                "true",
        "_vts":                     str(int(time.time() * 1000)),
        "resultsPage":              "1",
    }
    try:
        r = session.post(
            SEARCH_URL,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        if r.status_code != 200:
            return -1
        data = r.json()
    except Exception as exc:
        print(f"    WARNING: search error: {exc}", flush=True)
        return -1

    # Count only sailing yachts and catamarans
    count = 0
    for entry in (data.get("results") or []):
        raw = entry.get("data", "")
        try:
            y = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            continue
        if y.get("kind", "") in SAILING_KINDS:
            count += 1
    return count


# ── De-duplicate REGION_CONFIG by portal config ───────────────────────────────
# Many quiz keys share the same (country, region, service) — only query once.
# We keep the first key encountered as the display label for that config.

TEST_DATES = ["2026-07-18", "2026-09-12", "2026-12-05"]

seen: dict[tuple, str] = {}   # (country, region, service) → first quiz key
groups: dict[str, list[str]] = defaultdict(list)  # first_key → all quiz keys

for quiz_key, cfg in REGION_CONFIG.items():
    dedup_key = (
        cfg.get("filter_country", ""),
        cfg.get("filter_region", ""),
        cfg.get("filter_service", ""),
    )
    if dedup_key not in seen:
        seen[dedup_key] = quiz_key
    groups[seen[dedup_key]].append(quiz_key)

unique_configs: list[tuple[str, tuple, dict]] = []
for dedup_key, first_key in seen.items():
    unique_configs.append((first_key, dedup_key, REGION_CONFIG[first_key]))

unique_configs.sort(key=lambda x: x[0])

print(f"\n{'='*70}")
print(f"COVERAGE AUDIT — {len(unique_configs)} unique portal configs")
print(f"Test dates: {', '.join(TEST_DATES)}")
print(f"Filter: any size, sailing + cats only, unlimited budget")
print(f"{'='*70}\n")

# ── Run the audit ─────────────────────────────────────────────────────────────

results: list[dict] = []

for i, (label, dedup_key, cfg) in enumerate(unique_configs, 1):
    country = cfg.get("filter_country", "")
    region  = cfg.get("filter_region", "")
    service = cfg.get("filter_service", "")
    all_keys = groups[label]

    print(f"[{i:2d}/{len(unique_configs)}] {label}  ({country} / region {region or 'any'})",
          flush=True)

    date_counts: list[int] = []
    for date in TEST_DATES:
        n = _search_count(country, region, service, date)
        date_counts.append(n)
        marker = "✓" if n >= 3 else ("△" if n > 0 else "✗")
        print(f"         {date}: {n:3d} yachts  {marker}", flush=True)
        time.sleep(0.3)

    valid_counts = [c for c in date_counts if c >= 0]
    avg = sum(valid_counts) / len(valid_counts) if valid_counts else 0
    min_count = min(date_counts) if date_counts else -1

    if avg == 0:
        status = "DEAD"
    elif avg < 3:
        status = "THIN"
    else:
        status = "OK"

    print(f"         → avg {avg:.1f}  min {min_count}  [{status}]\n", flush=True)

    results.append({
        "label":        label,
        "quiz_keys":    " | ".join(all_keys),
        "country":      country,
        "region":       region,
        "date_1":       date_counts[0] if len(date_counts) > 0 else "",
        "date_2":       date_counts[1] if len(date_counts) > 1 else "",
        "date_3":       date_counts[2] if len(date_counts) > 2 else "",
        "avg":          round(avg, 1),
        "min":          min_count,
        "status":       status,
    })

# ── Write CSV ─────────────────────────────────────────────────────────────────

csv_path = _root / "coverage_audit_results.csv"
fieldnames = ["label", "quiz_keys", "country", "region",
              f"date_{TEST_DATES[0]}", f"date_{TEST_DATES[1]}", f"date_{TEST_DATES[2]}",
              "avg", "min", "status"]

# Map generic date_1/2/3 keys to real date column headers
with open(csv_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["label", "quiz_keys", "country", "region",
                     TEST_DATES[0], TEST_DATES[1], TEST_DATES[2],
                     "avg_sailing_cats", "min_sailing_cats", "status"])
    for row in results:
        writer.writerow([
            row["label"], row["quiz_keys"], row["country"], row["region"],
            row["date_1"], row["date_2"], row["date_3"],
            row["avg"], row["min"], row["status"],
        ])

print(f"\nCSV saved → {csv_path}\n")

# ── Print summary by status ───────────────────────────────────────────────────

dead  = [r for r in results if r["status"] == "DEAD"]
thin  = [r for r in results if r["status"] == "THIN"]
ok    = [r for r in results if r["status"] == "OK"]

print("=" * 70)
print(f"SUMMARY:  {len(ok)} OK   {len(thin)} THIN   {len(dead)} DEAD")
print("=" * 70)

if dead:
    print(f"\n❌ DEAD — 0 sailing/cat results on all 3 dates (REMOVE from quiz):")
    for r in dead:
        print(f"   {r['label']:35s}  ({r['country']} / region {r['region']})")
        print(f"      Quiz keys: {r['quiz_keys']}")

if thin:
    print(f"\n⚠️  THIN — avg < 3 sailing/cat results (REVIEW):")
    for r in thin:
        print(f"   {r['label']:35s}  avg={r['avg']}  min={r['min']}  ({r['country']} / region {r['region']})")
        print(f"      Quiz keys: {r['quiz_keys']}")

if ok:
    print(f"\n✅ OK — avg ≥ 3 sailing/cat results:")
    for r in ok:
        print(f"   {r['label']:35s}  avg={r['avg']}  min={r['min']}")

print(f"\nDone. Full results in: {csv_path}")
