"""
portal_live_search.py
=====================
Fetches live, date-specific pricing from the booking-manager portal search API.

Confirmed endpoint (2026-04-19):
    POST https://portal.booking-manager.com/wbm2/page.html
    Body:  view=SearchResult2&responseType=JSON&companyid=7914&action=getResults&...
    Response: application/json

Usage:
    from scripts.portal_live_search import live_search

    results = live_search(
        region="Sardinia",
        date_from="2026-07-05",
        duration=7,
        adults=4,
        children=0,
        flexibility="closest_day",   # closest_day | in_week | in_month | on_day
    )
    # results: dict keyed by yacht_id (str) → pricing dict

    # Standalone test:
    python scripts/portal_live_search.py --region Sardinia --date 2026-07-05

Requirements:
    pip install requests python-dotenv
"""

from __future__ import annotations

import os
import sys
import json
import time
import argparse
from pathlib import Path

import requests
from dotenv import load_dotenv

# ── Load .env ─────────────────────────────────────────────────────────────────

_script_dir   = Path(__file__).resolve().parent
_project_root = _script_dir.parent
load_dotenv(_project_root / ".env")

PORTAL_EMAIL    = os.environ.get("BOOKING_MANAGER_EMAIL", "").strip()
PORTAL_PASSWORD = os.environ.get("BOOKING_MANAGER_PASSWORD", "").strip()

# ── Constants ─────────────────────────────────────────────────────────────────

PORTAL_BASE      = "https://portal.booking-manager.com"
PORTAL_LOGIN_URL = f"{PORTAL_BASE}/wbm2/app/login_register/login_to_continue.jsp"
PORTAL_TEST_URL  = f"{PORTAL_BASE}/wbm2/app/yachts/index.jsp"
SEARCH_URL       = f"{PORTAL_BASE}/wbm2/page.html"
COMPANY_ID       = "7914"
REQUEST_TIMEOUT  = 30

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
)

# ── Region configuration ───────────────────────────────────────────────────────
# Keys match quiz region values exactly (app.py passes region_str directly here).
# filter_region IDs discovered 2026-04-20 via discover_regions.py automated probe.
# filter_service lists aggregated from base→serviceId data for the region's bases.
# Multiple keys may share the same portal region (e.g. Cyclades + Saronic Gulf → region 10).

def _rc(country: str, region: str, service: str = "") -> dict:
    return {"filter_country": country, "filter_region": region, "filter_service": service}

REGION_CONFIG: dict[str, dict] = {

    # ── Greece ────────────────────────────────────────────────────────────────
    # Region 7 — Ionian Islands (Corfu, Lefkada, Kefalonia, Preveza, Palairos)
    "Ionian Islands":   _rc("GR", "7", "233,892,1002,1004,1019,1060,1492,1496,1520,1802,1909,2075,2142,2371,2458,2540,2753,2973,2996,3021,3111,3224,3502,3509,3622,3853,4103,4112,4152,4212,4485,4581,4840,4963,5307,6304,7291,7382,7471,7944,8736"),
    "Ionian":           _rc("GR", "7", "233,892,1002,1004,1019,1060,1492,1496,1520,1802,1909,2075,2142,2371,2458,2540,2753,2973,2996,3021,3111,3224,3502,3509,3622,3853,4103,4112,4152,4212,4485,4581,4840,4963,5307,6304,7291,7382,7471,7944,8736"),
    "Corfu":            _rc("GR", "7", "233,892,1002,1004,2371,4103,5307,6304,7291,8736"),
    "Lefkada":          _rc("GR", "7", "1002,1060,1492,1496,1520,1802,2075,2142,2458,2540,2753,2973,2996,3021,3111,3502,3509,3622,3853,4112,4152,4212,4485,4581,4840,4963,7382,7471,7944,8736"),
    "Kefalonia":        _rc("GR", "7", "1060,3224,7382"),
    "Preveza":          _rc("GR", "7", "1019,1060,1802,1909,2371,2142,2996,3853,4485,4963,7471"),

    # Region 8 — Sporades / Northern Mainland (Skiathos, Skopelos, Volos, Chalkidiki)
    "Sporades":         _rc("GR", "8", "923,1768,1802,2680,2808,2996,3528,3541,3582,3604,3853,4164,4603,4622,5292,5838,7992,8736"),
    "Skiathos":         _rc("GR", "8", "3582,4622,5838"),
    "Chalkidiki":       _rc("GR", "8", "3604,3853,5292,6692"),

    # Region 9 — Dodecanese / SE Aegean (Rhodes, Kos, Crete)
    "Dodecanese":       _rc("GR", "9", "1019,1254,1802,1909,2660,2996,3502,3569,3808,5249"),
    "Rhodes":           _rc("GR", "9", "2660,3502,3569,3808,5249"),
    "Kos":              _rc("GR", "9", "1019,1909,5249"),
    "Crete":            _rc("GR", "9", "1019,1254,1802,2996"),  # Crete departures via Athens/Rhodes area

    # Region 10 — Saronic Gulf / Cyclades (Athens-based departures)
    "Cyclades":         _rc("GR", "10", ""),   # All Athens providers; empty service = all
    "Saronic Gulf":     _rc("GR", "10", ""),
    "Athens":           _rc("GR", "10", ""),
    "Attica":           _rc("GR", "10", ""),

    # Region 47 — Northern Aegean (Kavala, Chalkidiki north, Thessaloniki)
    "Northern Aegean":  _rc("GR", "47", "3582,3604,3657,3801,3853,4931,5292,5568,6692,6711,7458,8736"),
    "Kavala":           _rc("GR", "47", "3582,3801,3853,4931,5568"),
    "Thessaloniki":     _rc("GR", "47", "7458"),

    # Region 55 — Peloponnese (Kalamata, Gytheio, Katakolo)
    "Peloponnese":      _rc("GR", "55", "4347,6414"),
    "Kalamata":         _rc("GR", "55", "6414"),

    # ── Croatia ───────────────────────────────────────────────────────────────
    # Region 1 — Istria & Kvarner (Pula, Medulin, Krk, Mali Lošinj, Novi Vinodolski)
    "Istria":               _rc("HR", "1", "126,172,220,1058,1869,2737,4027,4090,4305,4385,4613,4731,6003,6246,6364,6557,6605,7179,7387"),
    "Kvarner":              _rc("HR", "1", "126,1869,220,2737,4027,4090,4613,6003,7179"),
    "Istria & Kvarner":     _rc("HR", "1", "126,172,220,1058,1869,2737,4027,4090,4305,4385,4613,4731,6003,6246,6364,6557,6605,7179,7387"),

    # Region 2 — North Dalmatia / Zadar (Zadar, Biograd, Sukošan)
    "North Dalmatia":       _rc("HR", "2", "75,79,96,109,167,185,387,1222,1227,1502,1637,1994,2111,2283,3492,3855,7901,8083"),
    "Zadar Region":         _rc("HR", "2", "75,79,96,109,167,185,387,1222,1227,1502,1637,1994,2111,2283,3492,3855,7901,8083"),
    "Zadar":                _rc("HR", "2", "75,167,1222,1227,7901"),
    "Biograd":              _rc("HR", "2", "79,1637"),

    # Region 3 — Kornati & Šibenik (Šibenik, Murter, Primošten, Rogoznica)
    "Kornati & Šibenik":    _rc("HR", "3", "66,89,421,548,609,1664,1857,2104,2112,2511,2568,2679,3875,3919,4027,5733,6445,6476"),
    "Central Dalmatia":     _rc("HR", "3", "66,89,421,548,609,1664,1857,2104,2112,2511,2568,2679,3875,3919,4027,5733,6445,6476"),
    "Sibenik":              _rc("HR", "3", "89,2112,2568"),
    "Šibenik":              _rc("HR", "3", "89,2112,2568"),

    # Region 5 — Split & Central Dalmatia (Split, Trogir, Kaštela, Makarska, Baška Voda)
    "Split & Central Dalmatia": _rc("HR", "5", "66,98,126,160,172,198,246,512,548,667,809,928,1136,1571,1644,2104,2303,2332,2357,3513,3847,3919,4027,4618,6476,7050,7274,7817"),
    "Split":                _rc("HR", "5", "66,98,126,160,172,198,246,512,548,667,809,928,1136,1571,1644,2104,2303,2332,2357,3513,3847,3919,4027,4618,6476,7050,7274,7817"),
    "Trogir":               _rc("HR", "5", "126,246,928,1136,1571,7050"),
    "Makarska":             _rc("HR", "5", "3513"),

    # Region 6 — Dubrovnik & South Dalmatia (Dubrovnik, Ploče)
    "Dubrovnik & South Dalmatia": _rc("HR", "6", "172,198,1058,1136,1676,2303"),
    "Dubrovnik":            _rc("HR", "6", "172,198,1058,1136,1676,2303"),
    "South Dalmatia":       _rc("HR", "6", "172,198,1058,1136,1676,2303"),

    # ── Italy ─────────────────────────────────────────────────────────────────
    # Region 21 — Sardinia (Cagliari, Olbia, Portisco, Carloforte, Porto Cervo)
    "Sardinia":         _rc("IT", "21", "129,201,260,261,618,648,1230,1933,2501,3357,4128,4847,7771,7840,8003"),

    # Region 20 — Sicily (Palermo, Trapani, Marsala, Furnari, Syracuse)
    "Sicily":           _rc("IT", "20", "129,140,260,280,703,1230,1939,1952,2243,2532,2610,2653,2889,3072,3207,3575,3625,4883,5747,6300,6309,6723,7040,7152,7771,7829,7844,7887"),

    # Region 19 — Tuscany & Liguria (Cecina, La Spezia, Livorno, Genova, Punta Ala)
    "Tuscany":          _rc("IT", "19", "120,129,191,260,1230,1814,1842,2773,2979,3041,4307,4650,4664,5390,5423,648,7193,7840"),
    "Liguria":          _rc("IT", "19", "4307,5423"),

    # Region 18 — Naples, Amalfi & Calabria (Procida, Agropoli, Salerno, Tropea)
    "Amalfi Coast":     _rc("IT", "18", "129,260,273,648,1042,1093,1237,2235,2653,2691,2889,2903,4188,4252,6879,7771,7840"),
    "Naples":           _rc("IT", "18", "129,260,273,648,1042,1093,1237,2235,2653,2691,2889,2903,4188,4252,6879,7771,7840"),
    "Gulf of Naples":   _rc("IT", "18", "129,260,273,648,1042,1093,1237,2235,2653,2691,2889,2903,4188,4252,6879,7771,7840"),

    # Region 15 — Corsica & French Riviera (Ajaccio, Bonifacio, Cannes, Bormes)
    # Note: region 15 is under IT country filter but covers Corsica + Riviera sailing circuit
    "Corsica":                      _rc("IT", "15", "6709"),
    "French Riviera (Côte d'Azur)": _rc("IT", "15", "5620,6709"),  # Port Grimaud + Riviera/Corsica circuit

    # Region 20 also covers Aeolian Islands (Furnari/Portorosa is the departure base)
    "Aeolian Islands":  _rc("IT", "20", "129,260,280,703,1939,1952,2243,2653,2889,3072,7844"),

    # Region 30 — Adriatic / Venice (Chioggia, Casale sul Sile)
    "Venice":           _rc("IT", "30", "2746,7718"),
    "Adriatic":         _rc("IT", "30", "2746,7718"),

    # Region 17 — Puglia & Adriatic (Brindisi, Otranto, Pescara, Bari)
    "Puglia":           _rc("IT", "17", "2822,4396,6867,7420,7840,7996,8005"),

    # ── Spain ─────────────────────────────────────────────────────────────────
    # Region 13 — Balearic Islands broad (Ibiza + Mallorca + Costa Blanca)
    "Balearic Islands": _rc("ES", "13", "31,179,241,2517,2725,2755,2784,2850,3128,3605,3836,3994,4146,4651,4813,4949,5055,5386,5696,6793,6824,6883,7139,7470,7684,7772,7793,7813,8080,8093"),

    # Region 62 — Ibiza specifically
    "Ibiza":            _rc("ES", "62", "179,2517,2725,2755,2784,4146,4651,4813,4949,5055,5386,6793,7684,8080,8093"),

    # Region 63 — Mallorca specifically
    "Mallorca":         _rc("ES", "63", "31,241,2517,2850,3128,3605,3836,3994,4949,5696,6824,6883,7139,7772,7793"),
    "Majorca":          _rc("ES", "63", "31,241,2517,2850,3128,3605,3836,3994,4949,5696,6824,6883,7139,7772,7793"),

    # Region 46 — Barcelona & Costa Brava
    "Barcelona":        _rc("ES", "46", "1523,2850,3380,3725,4146,4175,5106,6804,6866"),
    "Costa Brava":      _rc("ES", "46", "1523,2850,3380,3725,4146,4175,5106,6804,6866"),

    # Region 48 — Valencia & Costa Blanca
    "Costa Blanca":     _rc("ES", "48", "4949,5389,6699,7470,7813"),
    "Valencia":         _rc("ES", "48", "5389"),

    # Region 14 — Canary Islands
    "Canary Islands":   _rc("ES", "14", "31,8086"),
    "Tenerife":         _rc("ES", "14", "31,8086"),

    # Region 29 — Galicia (Vigo, Baiona)
    "Galicia":          _rc("ES", "29", "2630,5103"),

    # ── Turkey ────────────────────────────────────────────────────────────────
    # Region 25 — Bodrum Peninsula
    "Bodrum":           _rc("TR", "25", "1284,1682,2304,2595,2887,3524,3587,3627,4068,4503,6402,7326,7476,7560,8109,8183"),

    # Region 26 — Turquoise Coast (Marmaris, Göcek, Fethiye)
    "Marmaris":         _rc("TR", "26", "1284,1427,1611,1907,2125,2660,3179,3187,4267,4371,4715,4748,4936,4948,5308,5316,5322,5349,5352,5357,5380,5382,5461,5479,5548,5565,5788,5831,6067,6108,6195,6206,6254,7025,7151,7327,7332,7347,7474,7716,7827,862,864,8773"),
    "Fethiye":          _rc("TR", "26", "862,864,1427,1611,2125,3187,3638,4371,4715,5316,5352,5357,5382,5461,5479,6067,6195,6206,7025,7151,7347,7716,8773"),
    "Gocek":            _rc("TR", "26", "233,3638,4715,4748,4948,5322,5349,5788,6195,6254,7327,7474"),
    "Göcek":            _rc("TR", "26", "233,3638,4715,4748,4948,5322,5349,5788,6195,6254,7327,7474"),
    "Turquoise Coast":  _rc("TR", "26", "862,864,1284,1427,1611,1907,2125,2660,3179,3187,3638,4267,4371,4715,4748,4936,4948,5308,5316,5322,5349,5352,5357,5380,5382,5461,5479,5548,5565,5788,5831,6067,6108,6195,6206,6254,7025,7151,7327,7332,7347,7474,7716,7827,8773"),

    # Region 12 — Antalya
    "Antalya":          _rc("TR", "12", "6837,7782"),

    # Region 49 — Istanbul
    "Istanbul":         _rc("TR", "49", "7941"),

    # ── Montenegro ────────────────────────────────────────────────────────────
    # Region 6 — Bay of Kotor (Herceg Novi, Kotor, Tivat, Portonovi)
    "Montenegro":       _rc("ME", "6", "665,4715,4834,5456,6766,7563,7622,7938,8077,8736"),
    "Bay of Kotor":     _rc("ME", "6", "665,4715,4834,5456,6766,7563,7622,7938,8077,8736"),
    "Budva Riviera":    _rc("ME", "6", "665,4715,4834,5456,6766,7563,7622,7938,8077,8736"),  # Budva south of Kotor — best MMK approximation is region 6
    "Kotor":            _rc("ME", "6", "5456,665"),
    "Tivat":            _rc("ME", "6", "4715,4834,6766,7563,7622,7938"),

    # ── Country-level entries (region = "any") ────────────────────────────────
    # Used when the quiz sends region:"any" — searches the full country fleet.
    # Empty filter_region tells the portal not to narrow by sub-region.
    "Italy":            {"filter_country": "IT", "filter_region": "", "filter_service": ""},
    "Greece":           {"filter_country": "GR", "filter_region": "", "filter_service": ""},
    "Croatia":          {"filter_country": "HR", "filter_region": "", "filter_service": ""},
    "Spain":            {"filter_country": "ES", "filter_region": "", "filter_service": ""},
    "Turkey":           {"filter_country": "TR", "filter_region": "", "filter_service": ""},
    "France":           {"filter_country": "IT", "filter_region": "15", "filter_service": ""},  # Corsica + Riviera circuit

    # ── Portugal ──────────────────────────────────────────────────────────────
    # (No region ID probe was needed — country-level search works for PT)
    "Portugal":         {"filter_country": "PT", "filter_region": "", "filter_service": "2219,2256,2257,4432,5158,5901,7542,7731"},
    "Lisbon":           {"filter_country": "PT", "filter_region": "", "filter_service": "2219,7731"},
    "Algarve":          {"filter_country": "PT", "filter_region": "", "filter_service": "2219,2256,4432,5158"},
    "Portimao":         {"filter_country": "PT", "filter_region": "", "filter_service": "2219,2256,4432,5158"},
    "Azores":           {"filter_country": "PT", "filter_region": "", "filter_service": "2257,7542"},
    "Madeira":          {"filter_country": "PT", "filter_region": "", "filter_service": "5901"},

    # ── French Polynesia ──────────────────────────────────────────────────────
    # French Polynesia — country-level search (no region filter).
    # filter_region=32 was too restrictive, limiting to 1 provider (2 boats).
    # Empty region returns the full PF fleet across all providers/bases.
    "French Polynesia":  {"filter_country": "PF", "filter_region": "", "filter_service": ""},
    "Bora Bora":         {"filter_country": "PF", "filter_region": "", "filter_service": ""},
    "Papeete":           {"filter_country": "PF", "filter_region": "", "filter_service": ""},
    "Tahiti":            {"filter_country": "PF", "filter_region": "", "filter_service": ""},
    "Raiatea":           {"filter_country": "PF", "filter_region": "", "filter_service": ""},

    # ── Bahamas ───────────────────────────────────────────────────────────────
    # Region 28 covers the whole Bahamas fleet (Marsh Harbour/Abacos + Nassau).
    # Portal has no separate region IDs for Exumas or Eleuthera — all quiz values
    # map here; AI will note which specific island the client asked for.
    # Discovered 2026-04-21 via discover_new_destinations.py (country code BS confirmed)
    "Bahamas":          _rc("BS", "28", "2889,2903"),
    "Abacos":           _rc("BS", "28", "2889,2903"),
    "Nassau":           _rc("BS", "28", "2889,2903"),
    "Exumas":           _rc("BS", "28", "2889,2903"),
    "Eleuthera":        _rc("BS", "28", "2889,2903"),

    # ── Seychelles ────────────────────────────────────────────────────────────
    # Region 37 — Eden Island Marina, Mahé, Victoria
    # Quiz skips sub-region step — country name is used as the lookup key.
    # Discovered 2026-04-21 via discover_new_destinations.py (country code SC confirmed)
    "Seychelles":       _rc("SC", "37", "2315,2886,2889,2903,4276,6222,6810,7183,7593"),

    # ── Thailand ─────────────────────────────────────────────────────────────
    # Region 34 — Phuket (Ao Po Grand Marina, Royal Phuket Marina, Yacht Haven)
    # Quiz skips sub-region step — country name is used as the lookup key.
    # Discovered 2026-04-21 via discover_new_destinations.py (country code TH confirmed)
    "Thailand":         _rc("TH", "34", "2889,2903,5041,7781"),
    "Phuket":           _rc("TH", "34", "2889,2903,5041,7781"),

    # ── British Virgin Islands ────────────────────────────────────────────────
    # Region 28 — Tortola / Road Town (Fort Burt Marina + Wickhams Cay II).
    # Portal has no separate region IDs for Virgin Gorda, Jost Van Dyke, Anegada —
    # all quiz sub-region values map here.
    # Discovered 2026-04-21 via discover_new_destinations.py (country code VG confirmed)
    "British Virgin Islands": _rc("VG", "28", "2889,2903,4863"),
    "BVI":              _rc("VG", "28", "2889,2903,4863"),
    "Tortola":          _rc("VG", "28", "2889,2903,4863"),
    "Virgin Gorda":     _rc("VG", "28", "2889,2903,4863"),
    "Jost Van Dyke":    _rc("VG", "28", "2889,2903,4863"),
    "Anegada":          _rc("VG", "28", "2889,2903,4863"),
}

# ── Portal session ─────────────────────────────────────────────────────────────

_portal = requests.Session()
_portal.headers.update({
    "User-Agent":       _UA,
    "Accept":           "application/json, text/plain, */*",
    "Accept-Language":  "en-US,en;q=0.9",
    "Origin":           PORTAL_BASE,
    "Referer":          f"{PORTAL_BASE}/wbm2/app/yachts/index.jsp",
    "Sec-Fetch-Dest":   "empty",
    "Sec-Fetch-Mode":   "cors",
    "Sec-Fetch-Site":   "same-origin",
})

_LOGIN_SIGNALS = [
    'name="login_email"',
    'name="login_password"',
    'id="login-box"',
    "login_to_continue",
    "To view this page you need to login",
]


def _is_login_page(text: str) -> bool:
    return any(sig in text for sig in _LOGIN_SIGNALS)


def _session_valid() -> bool:
    try:
        r = _portal.get(PORTAL_TEST_URL, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        return r.status_code == 200 and not _is_login_page(r.text)
    except Exception:
        return False


def _login() -> bool:
    """Log in to the portal, updating the shared session. Returns True on success."""
    if not PORTAL_EMAIL or not PORTAL_PASSWORD:
        print("ERROR: BOOKING_MANAGER_EMAIL / BOOKING_MANAGER_PASSWORD not set in .env",
              file=sys.stderr)
        return False

    print("Logging in to booking-manager portal...", flush=True)
    try:
        _portal.get(PORTAL_LOGIN_URL, timeout=REQUEST_TIMEOUT)
        resp = _portal.post(
            PORTAL_LOGIN_URL,
            data={
                "is_post_back":   "1",
                "login_email":    PORTAL_EMAIL,
                "login_password": PORTAL_PASSWORD,
                "referrer":       f"{PORTAL_BASE}/wbm2/app/yachts/index.jsp",
            },
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        if _is_login_page(resp.text):
            print("ERROR: Login failed — check credentials in .env", file=sys.stderr)
            return False
        print("Login successful.", flush=True)
        return True
    except Exception as exc:
        print(f"ERROR: Login exception: {exc}", file=sys.stderr)
        return False


def _ensure_logged_in() -> bool:
    """Check session; log in if needed. Returns True if authenticated."""
    if _session_valid():
        return True
    return _login()


# ── Response parser ────────────────────────────────────────────────────────────

def _parse_results(data: list | dict) -> dict[str, dict]:
    """
    Parse the JSON response from view=SearchResult2&action=getResults.

    Confirmed response structure (2026-04-19):
        {
          "results": [
            {
              "signature": "<sha1>",
              "data": "<json-encoded string>"   ← must be json.loads'd
            },
            ...
          ],
          "resultsCount": 57,
          "dateFrom": "2026-07-02 00:00:00",
          "dateTo":   "2026-07-15 00:00:00"
        }

    Confirmed yacht-level fields (inside parsed `data`):
        yachtId, yacht (boat name), model, year, berths, cabins, heads, length,
        mainsail, startBase, endBase, serviceId,
        price (net), startPrice (rack), discountPercentage,
        charterObligatoryDiscounts [{name, percentage, price, formattedPrice}],
        charterObligatoryExtras    [{name, unitPrice, displayPrice, priceUnit}],
        charterOptionalExtras      [{name, unitPrice, displayPrice, priceUnit}],
        deposit, formattedDeposit,
        dateFrom, dateTo,
        imagePath, interiorImagePath, yachtDetailsLink, equipment [{displayValue}]

    Returns a dict: { yacht_id (str) -> pricing_dict }
    """
    if not isinstance(data, dict) or "results" not in data:
        print(f"WARNING: Unexpected response shape. Top-level keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}",
              file=sys.stderr)
        return {}

    results: dict[str, dict] = {}

    for entry in data.get("results", []):
        raw_str = entry.get("data", "")
        if not raw_str:
            continue

        # data is a JSON-encoded string — parse it
        try:
            y = json.loads(raw_str) if isinstance(raw_str, str) else raw_str
        except (ValueError, TypeError):
            continue

        yacht_id = str(y.get("yachtId") or "").strip()
        if not yacht_id:
            continue

        # ── Prices ────────────────────────────────────────────────────────────
        rack    = _safe_float(y.get("startPrice"))   # list price before discounts
        charter = _safe_float(y.get("price"))         # net charter price
        deposit = _safe_float(y.get("deposit"))
        discount_pct = _safe_float(y.get("discountPercentage"))  # e.g. 14.5

        # ── Discounts (named, e.g. "Early Booking Mono 2026 10%") ─────────────
        discounts: list[dict] = []
        for d in (y.get("charterObligatoryDiscounts") or []):
            name = str(d.get("name") or "").strip()
            pct  = _safe_float(d.get("percentage"))
            amt  = _safe_float(d.get("price"))
            label = f"{name} ({pct:.0f}%)" if pct else name
            discounts.append({
                "label":  label,
                "amount": f"- {amt:,.2f} €" if amt else "",
            })

        # ── Mandatory extras ───────────────────────────────────────────────────
        mandatory: list[dict] = []
        for e in (y.get("charterObligatoryExtras") or []):
            mandatory.append({
                "label":  str(e.get("name") or "").strip(),
                "amount": str(e.get("displayPrice") or e.get("unitPrice") or "").strip(),
            })

        # ── Optional extras ────────────────────────────────────────────────────
        optional: list[dict] = []
        for e in (y.get("charterOptionalExtras") or []):
            optional.append({
                "label":  str(e.get("name") or "").strip(),
                "amount": str(e.get("displayPrice") or e.get("unitPrice") or "").strip(),
                "unit":   str(e.get("priceUnit") or "").strip(),
            })

        # ── Specs ──────────────────────────────────────────────────────────────
        specs = {
            "model":    str(y.get("model") or ""),
            "year":     str(y.get("year") or ""),
            "berths":   str(y.get("berths") or ""),
            "cabins":   str(y.get("cabins") or ""),
            "heads":    str(y.get("heads") or ""),
            "length":   str(y.get("length") or ""),
            "mainsail": str(y.get("mainsail") or ""),
        }

        # ── Images ────────────────────────────────────────────────────────────
        # imagePath / interiorImagePath are relative paths — prefix with BM_PUBLIC_BASE.
        # Confirmed publicly accessible without auth at 200 OK (tested 2026-04-20).
        BM_PUBLIC_BASE = "https://www.booking-manager.com/wbm2/"

        def _bm_image_url(raw_path: str, width: int = 1200) -> str:
            if not raw_path:
                return ""
            import re as _re
            full = BM_PUBLIC_BASE + raw_path
            full = _re.sub(r"([?&]width=)\d+", rf"\g<1>{width}", full)
            return full

        image_url    = _bm_image_url(str(y.get("imagePath") or ""))
        interior_url = _bm_image_url(str(y.get("interiorImagePath") or ""))

        # ── Equipment list ────────────────────────────────────────────────
        equipment = [
            str(e.get("displayValue") or "").strip()
            for e in (y.get("equipment") or [])
            if e.get("displayValue")
        ]

        # ── Detail page URL ───────────────────────────────────────────────
        details_path = str(y.get("yachtDetailsLink") or "")
        details_url  = (PORTAL_BASE + details_path) if details_path else ""

        results[yacht_id] = {
            "rack_price":       rack,
            "charter_price":    charter,
            "discount_pct":     discount_pct,
            "discounts":        discounts,
            "mandatory_extras": mandatory,
            "optional_extras":  optional,
            "deposit":          deposit,
            "date_from":        str(y.get("dateFrom") or ""),
            "date_to":          str(y.get("dateTo") or ""),
            "base":             str(y.get("startBase") or ""),
            "kind":             str(y.get("kind") or ""),
            "specs":            specs,
            "equipment":        equipment,
            "image_url":        image_url,
            "interior_url":     interior_url,
            "details_url":      details_url,
            "is_golden_partner": bool(y.get("isGoldenPartner")),
            "is_silver_partner": bool(y.get("isSilverPartner")),
            "service_id":       str(y.get("serviceId") or ""),
            "company_name":     str(y.get("companyName") or y.get("operatorName") or y.get("fleetName") or ""),
            "raw":              y,
        }

    return results


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "").replace("€", "").strip())
    except (ValueError, TypeError):
        return None


def _parse_extras_list(raw) -> list[dict]:
    """Normalise mandatory/optional extras into [{label, amount}]."""
    if not raw:
        return []
    out = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                label  = str(item.get("label") or item.get("name") or item.get("description") or "")
                amount = _safe_float(item.get("price") or item.get("amount") or item.get("value"))
                out.append({"label": label, "amount": f"{amount:,.2f} €" if amount else ""})
            elif isinstance(item, str):
                out.append({"label": item, "amount": ""})
    elif isinstance(raw, str):
        # Semicolon-separated string fallback (same format as CSV extras)
        for part in raw.split(";"):
            part = part.strip()
            if part:
                out.append({"label": part, "amount": ""})
    return out


# ── Public API ─────────────────────────────────────────────────────────────────

MAX_PAGES = 30  # hard cap: 30 × 50 = 1,500 yachts max per search


def live_search_all(
    region: str,
    date_from: str,
    duration: int = 7,
    adults: int = 2,
    children: int = 0,
    seniors: int = 0,
    flexibility: str = "closest_day",
    boat_kind: str = "",
    min_cabins: int = 0,
    debug: bool = False,
) -> dict[str, dict]:
    """
    Fetch ALL pages of search results and merge into one pricing dict.
    Handles the portal's 50-per-page limit automatically.

    boat_kind:  portal filter_kind value e.g. "Catamaran", "Sail boat", or "" for all.
    min_cabins: passed as filter_cabins=N-2000 to the portal. Supplying the lead's
                minimum cabin requirement here prevents low-cabin boats from filling
                the 50-per-page limit and crowding out boats that actually match.

    Termination logic (based on raw portal entry count, not deduplicated IDs):
      - Page returns 0 raw entries → done.
      - Page adds 0 new yacht IDs AND raw_count < 50 → sparse last page of all repeats → done.
      - Page adds 0 new yacht IDs AND raw_count >= 50 → portal is cycling past real end → done.
      - Page returns < 50 raw entries → last page (sparse tail, fewer than a full page) → done.
      - Hard cap of MAX_PAGES pages reached → stop to avoid runaway loops.

    Note: raw_count (pre-dedup entry count) is used rather than len(page_results) (unique
    yacht count) because the portal packs ~50 raw entries per page but many entries share
    the same yachtId across different availability windows. Using len(page_results) < 10
    would incorrectly terminate on page 1 when only 2 unique yachts exist across 50 entries.
    """
    all_results: dict[str, dict] = {}
    page = 1
    while page <= MAX_PAGES:
        page_results, raw_count = live_search(
            region=region, date_from=date_from, duration=duration,
            adults=adults, children=children, seniors=seniors,
            flexibility=flexibility, boat_kind=boat_kind, min_cabins=min_cabins,
            debug=debug, results_page=page,
        )
        if raw_count == 0:
            break

        # Count how many yacht IDs on this page are genuinely new
        new_count = sum(1 for k in page_results if k not in all_results)
        all_results.update(page_results)

        if new_count == 0:
            # All results on this page already seen — portal is cycling or at real end
            print(f"[live_search_all] Page {page} added 0 new yachts (portal cycling). Stopping.")
            break
        if raw_count < 50:
            # Fewer raw entries than a full page → this is the last page
            break

        page += 1
        time.sleep(0.5)  # be polite

    if page > MAX_PAGES:
        print(f"[live_search_all] WARNING: hit MAX_PAGES={MAX_PAGES} cap for {region}.")

    print(f"[live_search_all] {region} {date_from} → {len(all_results)} total yachts (across {page} page(s))")
    return all_results


def live_search(
    region: str,
    date_from: str,                   # "YYYY-MM-DD"
    duration: int = 7,
    adults: int = 2,
    children: int = 0,
    seniors: int = 0,
    flexibility: str = "closest_day", # closest_day | in_week | in_month | on_day
    boat_kind: str = "",              # "Catamaran", "Sail boat", or "" for all
    min_cabins: int = 0,              # portal filter_cabins lower bound
    results_page: int = 1,
    debug: bool = False,
) -> tuple[dict[str, dict], int]:
    """
    Fetch live pricing for all available yachts matching the given criteria.

    Returns:
        (results, raw_count) where:
          results   — dict keyed by yacht_id (str) → pricing dict (deduplicated)
          raw_count — number of raw entries in the portal's results array (pre-dedup),
                      used by live_search_all() for reliable pagination termination

    Returns ({}, 0) on error (caller should fall back to CSV prices).
    """
    cfg = REGION_CONFIG.get(region)
    if not cfg:
        print(f"WARNING: Unknown region '{region}'. Known: {list(REGION_CONFIG)}", file=sys.stderr)
        return {}, 0

    if not cfg.get("filter_region") and not cfg.get("filter_service"):
        print(f"WARNING: Region '{region}' has no region ID or service IDs configured — "
              f"will search by country only (may return unrelated results).", file=sys.stderr)

    if not _ensure_logged_in():
        print("ERROR: Cannot authenticate with portal — falling back to CSV prices.", file=sys.stderr)
        return {}, 0

    payload = {
        "view":                    "SearchResult2",
        "responseType":            "JSON",
        "companyid":               COMPANY_ID,
        "action":                  "getResults",
        "filter_country":          cfg["filter_country"],
        "filter_region":           cfg["filter_region"],
        # Service filter removed — we want all providers in the region, not just
        # our pre-configured list. Supplier preference and exclusion is handled
        # downstream via BLACKLISTED_SUPPLIERS / PREFERRED_SUPPLIERS in live_proposal_builder.py.
        "filter_service":          "",
        "filter_base":             "",
        "filterlocationdistance":  "5",
        "filter_flexibility":      flexibility,
        "filter_model":            "",
        "filter_shipyard":         "",
        "filter_offer_type":       "-1",
        "filter_base_to":          "",
        "filter_date_from":        date_from,              # YYYY-MM-DD
        "filter_duration":         str(duration),
        "filter_timeslot":         "",
        "filter_service_type":     "all",
        "filter_kind":             boat_kind,
        "filter_class":            "",
        "filter_mainsail":         "",
        "filter_genoa":            "",
        "filter_length_ft":        "0-2000",
        "filter_cabins":           f"{max(0, min_cabins)}-2000",
        "filter_berths":           "0-2000",
        "filter_heads":            "0-2000",
        "filter_price":            "0-10001000",
        "filter_yachtage":         "",
        "filter_year_from":        "",
        "filter_year_to":          "",
        "filter_equipment":        "",
        "filter_availability_status": "-1",
        "filter_options":          "-1",
        "personsByGroup0":         str(adults),
        "personsByGroup1":         str(children),
        "personsByGroup2":         str(seniors),
        "override_checkin_rules":  "false",
        "isTrusted":               "true",
        "_vts":                    str(int(time.time() * 1000)),
        "resultsPage":             str(results_page),
    }

    if debug:
        print(f"\n[live_search] POST {SEARCH_URL}")
        print(f"[live_search] Payload: {json.dumps(payload, indent=2)}\n")

    try:
        resp = _portal.post(
            SEARCH_URL,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"ERROR: Portal search request failed: {exc}", file=sys.stderr)
        return {}, 0

    # Response should be JSON
    try:
        data = resp.json()
    except ValueError:
        print(f"ERROR: Portal search returned non-JSON response "
              f"(status {resp.status_code}, {len(resp.text)} chars).\n"
              f"First 500 chars: {resp.text[:500]}", file=sys.stderr)
        if debug:
            Path("portal_search_raw_response.html").write_text(resp.text, encoding="utf-8")
            print("[debug] Full response saved to portal_search_raw_response.html")
        return {}, 0

    if debug:
        raw_path = Path("portal_search_raw_response.json")
        raw_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[debug] Raw JSON response saved to {raw_path}")

    raw_count = len(data.get("results", [])) if isinstance(data, dict) else 0
    parsed = _parse_results(data)
    print(f"[live_search] {region} {date_from} {duration}n → {raw_count} raw entries → {len(parsed)} unique yachts")
    return parsed, raw_count


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test portal live search")
    parser.add_argument("--region",      default="Sardinia",    help="Sardinia | Sicily | Marmaris")
    parser.add_argument("--date",        default="2026-07-05",  help="YYYY-MM-DD charter start")
    parser.add_argument("--duration",    type=int, default=7,   help="Charter nights")
    parser.add_argument("--adults",      type=int, default=2)
    parser.add_argument("--children",    type=int, default=0)
    parser.add_argument("--flexibility", default="closest_day")
    parser.add_argument("--debug",       action="store_true",   help="Save raw JSON response to disk")
    args = parser.parse_args()

    results, raw_count = live_search(
        region=args.region,
        date_from=args.date,
        duration=args.duration,
        adults=args.adults,
        children=args.children,
        flexibility=args.flexibility,
        debug=args.debug,
    )

    if not results:
        print(f"\nNo results returned (raw_count={raw_count}; see errors above).")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Live pricing for {args.region} | {args.date} | {args.duration} nights")
    print(f"{'='*60}")
    print(f"Total yachts returned: {len(results)}\n")

    # Show first 5 as a sample
    for i, (yacht_id, p) in enumerate(list(results.items())[:5]):
        rack    = f"€{p['rack_price']:,.0f}"    if p['rack_price']    else "n/a"
        charter = f"€{p['charter_price']:,.0f}" if p['charter_price'] else "n/a"
        discs   = ", ".join(d["label"] for d in p["discounts"]) or "none"
        print(f"  [{i+1}] yacht_id={yacht_id}  {p['specs'].get('model','')}")
        print(f"       rack={rack}  charter={charter}  discounts={discs}")
        if p["mandatory_extras"]:
            print(f"       mandatory: {[e['label'] for e in p['mandatory_extras'][:3]]}")
        print()
