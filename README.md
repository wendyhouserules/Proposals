# SailScanner Proposal Engine

Tokenized, portal-style proposal pages for SailScanner. Given an MMK Booking Manager HTML export (and optionally a lead/quiz JSON), one command builds the proposal and uploads it to WordPress — printing a ready-to-share URL.

Proposals are noindexed, leakage-free (no provider names, no MMK URLs rendered), and display:

- **Welcome / Introduction** (personalised from lead data)
- **Your Requirements** (two-column grid from lead answers)
- **Yacht Selection** (cards with ecommerce gallery, specs, full pricing breakdown, equipment & features)
- **Example Itinerary** (linked card)
- **How it Works** · **Next Steps** · **Contact**

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | `brew install python` / pyenv |
| pip packages | — | `pip install -r scripts/requirements.txt` |
| WordPress | 6.0+, PHP 7.4+ | — |
| WP Application Password | — | WP Admin → Users → Profile → Application Passwords |

---

## One-time setup

### 1. Python environment

```bash
cd "path/to/Proposals"
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
```

### 2. Environment variables

Create a `.env` file in the project root (the scripts load it automatically):

```dotenv
SAILSCANNER_WP_URL=https://sailscanner.ai
SAILSCANNER_WP_USER=your_wp_username
SAILSCANNER_WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
```

`SAILSCANNER_WP_APP_PASSWORD` is the Application Password from **WP Admin → Users → Profile → Application Passwords**. Spaces in the password are fine.

### 3. Flush permalinks

In WP Admin → **Settings → Permalinks → Save**. This ensures `/proposals/{token}/` resolves correctly.

---

## The full build + upload command

Run from the **Proposals** directory with your `.venv` active.

```bash
python scripts/build_proposal_from_mmk.py \
  --input input_files/mmk-costa-brava.html \
  --type skippered \
  --output output_files/out.json \
  --lead input_files/lead.json \
  --fetch-images \
  --upload
```

The script prints the proposal URL when done. Open it or send it directly to the client.

### Flag reference

| Flag | Required | Description |
|------|----------|-------------|
| `--input FILE` | **Yes** | Path to the MMK Booking Manager HTML export. Repeat for multiple files (yachts are merged). |
| `--type bareboat\|skippered` | **Yes** | Selects the correct email parser. `skippered` includes skipper cost and optional extras. |
| `--output FILE` | Recommended | Where to write the intermediate JSON (e.g. `output_files/out.json`). Defaults to `output_files/proposal_from_mmk.json` if omitted with `--upload`. |
| `--lead FILE` | Recommended | Path to lead/quiz JSON. Populates the personalised greeting and **Your Requirements** section. See [Lead file format](#lead-file-format) below. |
| `--fetch-images` | Optional | Fetches the full yacht gallery (up to 20 photos at 1200 px) from the MMK YachtDetails page for each yacht. Without this flag, the 2 email thumbnails are still upsized to 1200 px. Requires internet access. |
| `--upload` | Optional | After building the JSON, POSTs to WordPress and prints the proposal URL. Requires env vars. |
| `--group-by-base` | Optional | Group yacht cards by their charter base. Each base gets its own sub-heading and anchor, with clickable sub-nav items in the sidebar under "Yacht Selection". Useful when yachts span multiple departure marinas. |
| `--prorate` | Optional | Override yacht dates to match lead dates AND scale prices proportionally when the MMK quote is for 7 days and the lead is for a shorter/longer duration. Off by default — also enabled permanently via `SAILSCANNER_PRORATE=1` in `.env`. |
| `--no-prorate` | Optional | Explicitly disable pro-rating and date override for this run, even if `SAILSCANNER_PRORATE=1` is set in `.env`. |
| `--no-date-override` | Optional | When `--prorate` is active, skip overriding yacht dates but still apply price scaling. Also controlled permanently via `SAILSCANNER_DATE_OVERRIDE=0` in `.env`. |
| `--intro FILE` | Optional | HTML file to use as the proposal introduction instead of the default. |
| `--itinerary FILE` | Optional | HTML file for the Example Itinerary section. |
| `--notes FILE` | Optional | HTML file for the Notes/validity section. |

### Pro-rating and date override: env var reference

Both behaviours are **off by default** and can be set globally in `.env` or overridden per-run on the CLI.

| Behaviour | `.env` variable | CLI flag (on) | CLI flag (off) |
|-----------|----------------|---------------|----------------|
| Price pro-rating | `SAILSCANNER_PRORATE=1` | `--prorate` | `--no-prorate` |
| Date override | `SAILSCANNER_DATE_OVERRIDE=0` to disable | *(on by default when pro-rating is active)* | `--no-date-override` |

**CLI flags always win over `.env` values.**

Common combinations:

| Scenario | Command / `.env` |
|----------|-----------------|
| Never pro-rate anything | Default — do nothing |
| Always pro-rate all proposals | `SAILSCANNER_PRORATE=1` in `.env` |
| Pro-rate this run only | `--prorate` |
| Pro-rate but keep original dates | `--prorate --no-date-override` or `SAILSCANNER_DATE_OVERRIDE=0` in `.env` |
| Disable pro-rate even if env var is set | `--no-prorate` |

### Common command variations

```bash
# Bareboat, no lead data, JSON only (no upload):
python scripts/build_proposal_from_mmk.py \
  --input input_files/mmk-costa-brava.html \
  --type bareboat \
  --output output_files/out.json

# Skippered, with lead, fetch full gallery, upload (no pro-rating — default):
python scripts/build_proposal_from_mmk.py \
  --input input_files/mmk-costa-brava.html \
  --type skippered \
  --lead input_files/lead.json \
  --fetch-images \
  --output output_files/out.json \
  --upload

# Skippered, with lead — ENABLE pro-rating (dates overridden, prices scaled):
python scripts/build_proposal_from_mmk.py \
  --input input_files/mmk-sarah.html \
  --type skippered \
  --lead input_files/sarah.json \
  --fetch-images \
  --prorate \
  --output output_files/out.json \
  --upload

# Multiple MMK files (merge yachts from two sources):
python scripts/build_proposal_from_mmk.py \
  --input input_files/file1.html \
  --input input_files/file2.html \
  --type bareboat \
  --output output_files/out.json \
  --upload

# Group by base + pro-rate:
python scripts/build_proposal_from_mmk.py \
  --input input_files/lauren-murphey2.html \
  --type skippered \
  --lead input_files/lauren-murphey-lead.json \
  --fetch-images \
  --group-by-base \
  --prorate \
  --output output_files/out.json \
  --upload

# Upload an already-built JSON (skips build step):
export SAILSCANNER_PROPOSAL_JSON="$(pwd)/output_files/out.json"
python scripts/proposal_import.py
```

---

## Lead file format

The lead file personalises the greeting and the **Your Requirements** section. It comes from the SailScanner quiz/CRM.

```json
{
  "answers": {
    "charterType": "skippered",
    "boatType":    "catamaran",
    "country":     "Spain",
    "region":      "Costa Brava",
    "size":        "41-45",
    "cabins":      "3",
    "budget":      "3-5k",
    "experience":  "none",
    "dates":       "2026-06-24",
    "crewServices": { "chef": true, "provisioning": true }
  },
  "contact": {
    "name":  "Keerthana",
    "email": "keerthana@example.com",
    "phone": "+447700900000"
  }
}
```

All fields are optional — the greeting and requirements block render gracefully with whatever is present.

---

## What each proposal card shows

Each yacht card in the proposal contains:

1. **Gallery** — main image (16:9) + scrollable thumbnail strip. Thumbnails are clickable to swap the main image. With `--fetch-images`, up to 20 full-resolution photos are shown. Without it, the 2 email thumbnails are shown upsized to 1200 px.
2. **Specs** — Year, Length, Berths, Cabins, WC/Shower, Mainsail, Base (3-column grid).
3. **Charter Details** — Base port and date range (e.g. `27 June 2026, 18:00 → 4 July 2026, 08:00`) when available from the MMK email.
4. **Pricing table** (two-column layout on desktop):
   - Base Price
   - Discounts (e.g. Early Booking −5%)
   - **Charter Price** (net total, highlighted)
   - Mandatory Extras section (cleaning fees, starter packs, etc.)
   - Optional Extras section (Skipper, WiFi, etc.)
5. **Equipment & Features** — pill tags (Bimini, Autopilot, Radar, etc.).
6. **View details** and **Shortlist / Ask** (WhatsApp) buttons.

Clicking **View details** opens the `ss_proposal_yacht` page with a full gallery and complete pricing.

---

## Image quality

MMK Booking Manager serves images via a CDN endpoint:

```
https://www.booking-manager.com/wbm2/documents/image.jpg?name=FILENAME&width=N
```

- **Email thumbnails** (`width=310`) — small, do not scale well.
- **Build script (default)** — upsizes the 2 email thumbnails to `width=1200`.
- **`--fetch-images`** — fetches the YachtDetails page for each yacht and extracts up to 20 gallery photos at `width=1200`. This is the recommended approach for premium-looking proposals.

---

## WordPress REST API

All communication uses **wp/v2 + Basic auth** (Application Password). No HMAC needed.

**Base URL**: `https://your-site.com/wp-json/wp/v2`

### POST `/ss_proposal`

Creates a proposal with yacht picks. The server auto-generates the token, creates `ss_proposal_yacht` posts, and returns `proposal_url`.

Key request body fields:

| Field | Type | Description |
|-------|------|-------------|
| `ss_yacht_data` | array | Array of yacht objects (see below). Server creates `ss_proposal_yacht` posts. |
| `ss_intro_html` | string | HTML for the Introduction section. |
| `ss_itinerary_html` | string | HTML for the Example Itinerary section. |
| `ss_notes_html` | string | HTML for the Notes/validity section. |
| `ss_contact_whatsapp` | string | E.164 phone number for WhatsApp CTAs (e.g. `447700900000`). |
| `ss_contact_email` | string | Email address for contact CTAs. |
| `ss_requirements_json` | object | Requirements key/value pairs (shown in **Your Requirements**). |
| `ss_lead_json` | object | Full lead/quiz object (see [Lead file format](#lead-file-format)). |

**Yacht object fields** (inside `ss_yacht_data`):

| Field | Type | Description |
|-------|------|-------------|
| `display_name` | string | Yacht model/make (not the boat name — no supplier leakage). |
| `images_json` | array | Image URLs (CDN). First is the main photo; others are gallery thumbs. |
| `highlights_json` | array | Equipment tags (Bimini, Autopilot, etc.). |
| `specs_json` | array | `[{"label":"Year","value":"2024"}, ...]` |
| `prices_json` | object | `{charter_price, base_price, discounts[], mandatory_advance[], mandatory_base[], optional_extras[]}` |
| `charter_json` | object | `{base, date_from, date_to, checkin, checkout}` — charter dates and base port. |
| `cabins`, `berths`, `year`, `length_m` | int/float | Used as fallback when `specs_json` is absent. |
| `base_name`, `country`, `region` | string | Location metadata. |

---

## How to rotate HMAC secrets

*(Only relevant if using the optional `sailscanner/v1` custom endpoint.)*

1. Generate: `openssl rand -hex 32`
2. Update `SAILSCANNER_HMAC_SECRET` in `wp-config.php`.
3. Update in any signing script/service.
4. Old signed requests fail with 403 immediately. Proposal tokens and yacht data are unaffected.

---

## Proposal page layout

| Section | Anchor | Notes |
|---------|--------|-------|
| Welcome / Introduction | `#intro` | Personalised from lead; combined card with Your Requirements |
| Your Requirements | `#requirements` | Two-column grid with icons |
| Yacht Selection | `#yacht-selection` | Cards with gallery, specs, charter details, pricing, equipment |
| Example Itinerary | `#itinerary` | Linked card to region/country charter page |
| How it Works | `#how-it-works` | 5-step process |
| Next Steps | `#next-steps` | Bullet list |
| Contact | `#contact` | WhatsApp + email CTAs |

- **Sidebar** (desktop): sticky nav with section icons.
- **Mobile**: sidebar collapses to top of page.
- **Noindex**: `<meta name="robots">` + `X-Robots-Tag: noindex, nofollow` on all proposal and `ss_proposal_yacht` pages.
- **No leakage**: Provider names and MMK "more info" URLs are stored internally only — never rendered.

---

## File layout

```
Proposals/
├── .env                                   ← WP credentials (never commit)
├── input_files/                           ← MMK HTML exports, lead JSONs
│   ├── mmk-costa-brava.html
│   └── lead.json
├── output_files/                          ← Generated JSON payloads
│   └── out.json
├── scripts/
│   ├── build_proposal_from_mmk.py         ← Main build script (MMK HTML → JSON → WP)
│   ├── proposal_import.py                 ← Upload-only script (JSON → WP)
│   └── requirements.txt                   ← pip deps
├── examples/
│   ├── build_email_block.py               ← MMK bareboat email parser
│   └── build_email_block_skippered.py     ← MMK skippered email parser
└── sailscanner-proposals/
    ├── sailscanner-proposals.php           ← Plugin bootstrap
    ├── includes/
    │   ├── class-ss-proposal-cpt.php
    │   ├── class-ss-proposal-routing.php
    │   ├── class-ss-proposal-rest-core.php
    │   ├── class-ss-proposal-helpers.php   ← Render helpers (pricing table, gallery, requirements)
    │   └── class-ss-proposal-seo.php
    ├── templates/
    │   ├── single-ss-proposal.php          ← Proposal portal template
    │   └── single-ss-proposal-yacht.php    ← Yacht detail page template
    └── assets/
        └── proposal-portal.css            ← All proposal/yacht scoped styles
```

---

## FTP deployment (plugin files only)

After editing plugin PHP/CSS files locally, upload these to the server. Python scripts run locally only.

```
wp-content/mu-plugins/sailscanner-proposals/assets/proposal-portal.css
wp-content/mu-plugins/sailscanner-proposals/includes/class-ss-proposal-helpers.php
wp-content/mu-plugins/sailscanner-proposals/includes/class-ss-proposal-rest-core.php
wp-content/mu-plugins/sailscanner-proposals/templates/single-ss-proposal.php
wp-content/mu-plugins/sailscanner-proposals/templates/single-ss-proposal-yacht.php
```
