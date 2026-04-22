#!/usr/bin/env python3
"""
test_relaxation.py
==================
Prints the yacht count at each relaxation step for a given test lead.

Usage (run from the Proposals directory):
    python3 test_relaxation.py input_files/test-01-croatia-monohull-family.json
"""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from portal_live_search import live_search_all
from live_proposal_builder import (
    filter_live_yachts, BUDGET_RANGES, _parse_size_range,
    standard_search_duration,
)

lead_file = sys.argv[1] if len(sys.argv) > 1 else "input_files/test-01-croatia-monohull-family.json"
lead = json.loads(Path(lead_file).read_text())
answers = lead.get("answers", {})

region_raw = answers.get("region") or ""
region_str = (region_raw[0] if isinstance(region_raw, list) else region_raw).strip()
if not region_str:
    region_str = answers.get("country", "").strip()

dates      = answers.get("dates", {})
start_iso  = dates.get("start", "")
end_iso    = dates.get("end", "")
duration   = standard_search_duration(start_iso, end_iso)
budget_str = (answers.get("budget") or "").strip().lower()
size_str   = (answers.get("size") or "").strip()
boat_type  = (answers.get("boatType") or "").strip().lower()

_INF = float("inf")
_TARGET = 3
orig_bmin, orig_bmax = BUDGET_RANGES.get(budget_str, (0, _INF))
orig_smin, orig_smax = _parse_size_range(size_str)

print(f"\nLead:    {region_str} | {boat_type} | {size_str}ft | budget={budget_str} | {duration}n")
print(f"Budget:  €{orig_bmin:,.0f} – {'∞' if orig_bmax == _INF else f'€{orig_bmax:,.0f}'}")
print(f"Size:    {orig_smin}–{orig_smax if orig_smax != _INF else '∞'} ft")
print()

# ── Portal search ──────────────────────────────────────────────────────────────
from live_proposal_builder import BOAT_TYPE_MAP, SAILING_AND_CATS_TYPES, MONOHULL_TYPES
boat_kind_filter = BOAT_TYPE_MAP.get(boat_type, "")
print(f"Searching portal: {region_str} / {start_iso} / {duration}n / kind={boat_kind_filter or 'all'}")
live_results = live_search_all(
    region=region_str, date_from=start_iso, duration=duration,
    adults=answers.get("guests", {}).get("adults", 2),
    children=answers.get("guests", {}).get("children", 0),
    boat_kind=boat_kind_filter,
)
print(f"Portal total: {len(live_results)} yachts\n")

# ── Relaxation steps ───────────────────────────────────────────────────────────
def show(label, filtered, bmin=None, bmax=None, smin=None, smax=None):
    prices = sorted([d.get("charter_price") for _, d in filtered if d.get("charter_price")])
    price_str = f"€{prices[0]:,.0f}–€{prices[-1]:,.0f}" if prices else "n/a"
    b_str = ""
    if bmin is not None or bmax is not None:
        b_str = f"  budget=€{(bmin or 0):,.0f}–{'∞' if bmax == _INF else f'€{bmax:,.0f}'}"
    s_str = ""
    if smin is not None or smax is not None:
        s_str = f"  size={smin}–{'∞' if smax == _INF else smax}ft"
    hit = "✓ ENOUGH" if len(filtered) >= _TARGET else "✗"
    print(f"  {label}: {len(filtered)} yachts  {price_str}{b_str}{s_str}  {hit}")
    return filtered

# Step 0: exact
filtered = filter_live_yachts(live_results, lead)
show("Step 0 (exact)", filtered, orig_bmin, orig_bmax, orig_smin, orig_smax)
relaxation = "none" if len(filtered) >= _TARGET else ""

# Step 1: size ±5ft, budget unchanged
if len(filtered) < _TARGET:
    s1min = max(0, orig_smin - 5)
    s1max = orig_smax + 5 if orig_smax != _INF else _INF
    filtered = filter_live_yachts(live_results, lead, size_range_override=(s1min, s1max))
    show("Step 1 (size ±5ft)", filtered, orig_bmin, orig_bmax, s1min, s1max)
    if len(filtered) >= _TARGET: relaxation = "size ±5ft"

# Step 2: budget ±2k, original size
if len(filtered) < _TARGET:
    b2min = max(0, orig_bmin - 2_000)
    b2max = orig_bmax + 2_000 if orig_bmax != _INF else _INF
    filtered = filter_live_yachts(live_results, lead, budget_min_override=b2min, budget_max_override=b2max)
    show("Step 2 (budget ±2k)", filtered, b2min, b2max, orig_smin, orig_smax)
    if len(filtered) >= _TARGET: relaxation = "budget ±2k"

# Step 3: budget ±4k, size removed
if len(filtered) < _TARGET:
    b3min = max(0, orig_bmin - 4_000)
    b3max = orig_bmax + 4_000 if orig_bmax != _INF else _INF
    filtered = filter_live_yachts(live_results, lead, budget_min_override=b3min, budget_max_override=b3max, size_range_override=(0, _INF))
    show("Step 3 (budget ±4k + size removed)", filtered, b3min, b3max, 0, _INF)
    if len(filtered) >= _TARGET: relaxation = "budget ±4k + size removed"

# Step 4: budget ±4k, size removed, all sail/cat
if len(filtered) < _TARGET:
    b4min = max(0, orig_bmin - 4_000)
    b4max = orig_bmax + 4_000 if orig_bmax != _INF else _INF
    filtered = filter_live_yachts(live_results, lead, budget_min_override=b4min, budget_max_override=b4max, size_range_override=(0, _INF), allow_sailing_and_cats=True)
    show("Step 4 (budget ±4k + size removed + sail/cat)", filtered, b4min, b4max, 0, _INF)
    if len(filtered) >= _TARGET: relaxation = "budget ±4k + size removed + all sail/cat"

print(f"\nResult: relaxation={relaxation!r}  final_count={len(filtered)}")
if len(filtered) == 0:
    print("STATUS: NO_MATCHES")
