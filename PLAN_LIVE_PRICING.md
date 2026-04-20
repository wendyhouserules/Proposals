# Live Pricing via Portal Search API
_Created: 2026-04-19_

This plan picks up from the end of Phase 1 of the proposal pipeline.  
The immediate goal: replace the stale snapshot pricing in `build_proposal_from_csv.py` with **live, date-specific pricing** fetched from the booking-manager portal at proposal time.

---

## Why this is necessary

The `yacht_database_full.csv` dump is a one-week snapshot. Discounts on the portal (Easter, early-booking, seasonal, etc.) are real contractual discounts that change daily and by date window. A proposal built from the snapshot will show wrong rack prices, wrong discounts, and wrong charter prices for any date range other than the exact week captured.

The portal has a JSON search API. When a search is submitted, it returns live pricing for every available yacht. We need to call this API at proposal time with the lead's actual dates and region, then merge the live pricing into the proposal.

---

## What we know about the portal API

### Endpoint confirmed
```
POST https://portal.booking-manager.com/wbm2/page.html
     ?view=SearchForm2&responseType=JSON&companyid=7914&action=saveHistoryFilter
```
This endpoint **saves and returns search history** — it confirms our filter params are correct but does not return yacht results.

### ✅ Search results endpoint — CONFIRMED (2026-04-19)

```
POST https://portal.booking-manager.com/wbm2/page.html
Content-Type: application/x-www-form-urlencoded
Response:     application/json  (~71 kB for Sardinia)
```

**POST body params (key fields):**
```
view=SearchResult2
responseType=JSON
companyid=7914
action=getResults
filter_country=IT
filter_region=21
filter_service=648,6723,618,...   (comma-separated, not array)
filter_date_from=2026-08-23       (YYYY-MM-DD, NOT datetime)
filter_duration=7
filter_flexibility=closest_day
personsByGroup0=2
personsByGroup1=0
personsByGroup2=0
_vts=<unix_ms_timestamp>
resultsPage=1
```

Full implementation: `scripts/portal_live_search.py`

### Confirmed filter parameter structure
Full reference: `scripts/portal_search_params_sardinia.json`

| Parameter | Meaning | Example |
|-----------|---------|---------|
| `filter_region` | Portal region ID (array) | `["21"]` = Sardinia, `["20"]` = Sicily |
| `filter_service` | Provider service IDs (array) | 17 IDs for Sardinia (see JSON) |
| `filter_date_from` | Charter start date | `"2026-07-05 00:00:00"` |
| `filter_duration` | Charter length in days | `"7"` |
| `filter_flexibility` | Date flexibility | `"closest_day"`, `"in_week"`, `"in_month"`, `"on_day"` |
| `personsByGroup0` | Adults | `"4"` |
| `personsByGroup1` | Children | `"0"` |
| `personsByGroup2` | Seniors | `"0"` |
| `filter_price` | Price range | `"0-10001000"` (no limit) |
| `filter_availability_status` | `-1` = all | leave as-is |
| `override_checkin_rules` | `false` | leave as-is |

### Region mapping (confirmed so far)

| Region name | Portal `filter_region` ID | Notes |
|-------------|--------------------------|-------|
| Sardinia | `21` | 17 service IDs confirmed — see JSON |
| Sicily | `20` | Service IDs TBD — needs DevTools capture |
| Marmaris | TBD | Region ID and service IDs both TBD |

---

## Action steps

### ~~Step 1 — Find the search results endpoint~~ ✅ DONE
Endpoint confirmed: `POST page.html` with `view=SearchResult2&action=getResults`.  
Implementation: `scripts/portal_live_search.py`

### Step 2 — Capture Sicily and Marmaris filter params
Repeat the same DevTools capture for Sicily and Marmaris.  
We need:
- `filter_region` ID for each
- Full `filter_service` array for each

Save as `portal_search_params_sicily.json` and `portal_search_params_marmaris.json` alongside the existing Sardinia file.

### ~~Step 3 — Parse the search results response~~ ✅ DONE
`_parse_results()` in `portal_live_search.py` handles common JSON shapes.  
**Field names not yet verified against live response** — run `--debug` flag to dump raw JSON and confirm.

Extracts per yacht:
- `yachtId`
- `rack_price` (start/list price)
- `charter_price` (net price after discounts)
- `discount_percentage` or `discount_items[]`
- `mandatory_extras[]`
- `optional_extras[]`

The dump HTML showed these in `reservationDataEnc` hidden fields and in price tables. The JSON API may return them directly.

### ~~Step 4 — Write `portal_live_search.py`~~ ✅ DONE
`scripts/portal_live_search.py` written. Auth reused from `cache_yacht_images.py`.

**To test:**
```bash
cd ~/Documents/SailScanner/Website/Plugins/MU\ Plugins/Proposals
.venv/bin/python scripts/portal_live_search.py --region Sardinia --date 2026-07-05 --debug
```
`--debug` saves the raw JSON to `portal_search_raw_response.json` so you can inspect the exact field names.

### ⚠️ Step 4b — Verify JSON field names from live response
The `_parse_results()` parser tries common field name variants but the actual field names are not yet confirmed. After running the test above:
1. Open `portal_search_raw_response.json`
2. Find a yacht object and check what fields hold rack price, net price, discount %, mandatory extras
3. Update `_parse_results()` in `portal_live_search.py` with the correct field names

### Step 5 (was Step 4) — Write `portal_live_search.py`
~~Already done above~~

```python
def live_search(
    region: str,          # "Sardinia" | "Sicily" | "Marmaris"
    date_from: str,       # "YYYY-MM-DD"
    duration: int,        # nights (default 7)
    adults: int = 2,
    children: int = 0,
    seniors: int = 0,
    flexibility: str = "closest_day",  # closest_day | in_week | in_month | on_day
) -> list[dict]:
    """
    POST to the portal search endpoint.
    Returns a list of yacht dicts with live pricing keyed by yacht_id.
    """
```

The function should:
1. Authenticate with the portal (reuse session logic from `cache_yacht_images.py`)
2. POST the search params (from the region's JSON file, with date/duration/pax overridden)
3. Parse the response and return `{yacht_id: {rack, charter, discounts, extras}}`

### Step 5 — Integrate into `build_proposal_from_csv.py`
In `price_for_dates()` (or a new `enrich_with_live_pricing()` function):
1. Call `live_search()` with the lead's dates, region, and pax
2. Build a lookup dict keyed by `yacht_id`
3. For each filtered yacht, replace the CSV-snapshot prices with live prices
4. Fall back to CSV snapshot prices if a yacht isn't in the live results (shouldn't happen often)

### Step 6 — Integrate into `app.py`
Pass `guests`, `dates.start`, `dates.end` from the lead into the pricing call.  
The live search can run once per proposal request — results cover all yachts in the region for those dates.

---

## File layout

```
scripts/
  portal_live_search.py              ← NEW: auth + search + parse
  portal_search_params_sardinia.json ← EXISTS: confirmed filter params
  portal_search_params_sicily.json   ← TODO: capture from DevTools
  portal_search_params_marmaris.json ← TODO: capture from DevTools
  build_proposal_from_csv.py         ← MODIFY: call live_search(), merge prices
  cache_yacht_images.py              ← REUSE: portal auth session logic
```

---

## Key gotchas to remember

- **`saveHistoryFilter` is not the results endpoint.** It only saves/retrieves search history. The actual results come from a different action.
- **Portal session required.** All portal requests need a valid login session (email + password). Reuse `cache_yacht_images.py` auth logic.
- **`bmdoc/` URLs** are relative to `/wbm2/`, not the portal root. Full path: `https://portal.booking-manager.com/wbm2/bmdoc/...`
- **Rate limiting.** Don't hammer the portal. One search call per proposal is fine; no need to loop.
- **Fallback.** If the live search fails (network error, portal down), fall back to CSV snapshot prices and log a warning. Never crash the proposal build.
- **`reservationDataEnc`** in portal HTML contains base64-encoded pricing. The JSON API may expose these fields directly — check the raw response carefully.

---

## Related files

| File | Purpose |
|------|---------|
| `STATUS.md` | Full pipeline status and commands to run |
| `PLAN_MMK_TO_PROPOSAL.md` | Plan for building proposals from MMK HTML input |
| `scripts/build_proposal_from_csv.py` | Current proposal builder (uses CSV snapshot pricing) |
| `scripts/cache_yacht_images.py` | Portal auth + image downloader (session logic to reuse) |
| `scripts/portal_search_params_sardinia.json` | Captured Sardinia filter params |
| `app.py` | FastAPI server — calls build_proposal_from_csv |
