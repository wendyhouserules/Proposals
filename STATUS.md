# SailScanner Proposal Pipeline — Current Status
_Last updated: 2026-04-19_

---

## What's been built

The full automated pipeline exists and works end-to-end:

**Quiz lead → FastAPI → AI yacht selection → WordPress proposal → (email/WhatsApp TBD)**

### Files and what they do

| File | Purpose |
|------|---------|
| `app.py` | FastAPI server. Make.com POSTs a lead here → filters yachts → AI selects → builds and uploads proposal to WordPress → returns proposal URL. |
| `scripts/build_proposal_from_csv.py` | Core proposal builder. Reads `yacht_database_full.csv`, filters by region/dates/budget, builds the full proposal payload, POSTs to WordPress REST API. |
| `scripts/ai_select.py` | GPT-4o-mini selects 4–6 best yachts from filtered list and writes personalised intro copy for the proposal. |
| `scripts/cache_yacht_images.py` | Downloads yacht photos from booking-manager portal, converts to JPEG at 1920px max, uploads to WordPress media library. Saves to `scripts/image_cache.json` (resumable). |
| `scripts/image_cache.json` | Maps yacht_id → { images: [wp_urls], layout: wp_url }. Read by `build_proposal_from_csv.py` automatically. |
| `sailscanner-proposals/` | WordPress plugin. Registers `ss_proposal` and `ss_proposal_yacht` custom post types, REST endpoints, and proposal template. |
| `.env` | All credentials. See section below. |

### WordPress plugin fixes already applied
- `class-ss-proposal-rest-core.php`: AI-generated intro copy now correctly goes into `post_content` (previously a hardcoded generic template was always used instead).
- `app.py`: Contact email button now shows broker email (`chris@sailscanner.ai`) not the client's email.

---

## Current state of each component

### ✅ FastAPI (`app.py`)
Working. Auth check is **commented out** for local dev — must be re-enabled before production deploy.

Handles unsupported regions gracefully:
- Returns `{"status": "manual_required", "reason": "region_not_supported", ...}` instead of crashing with 422.
- Make.com should branch on `status` field: `"ok"` → automated flow, `"manual_required"` → notify Chris to handle manually.

**To start locally:**
```bash
cd ~/Documents/SailScanner/Website/Plugins/MU\ Plugins/Proposals
.venv/bin/uvicorn app:app --reload --port 8000
```

**To test:**
```bash
curl -s -X POST http://127.0.0.1:8000/build-proposal \
  -H "Content-Type: application/json" \
  -d '{
    "answers": {
      "contact": {"name": "Test Client", "email": "test@example.com"},
      "region": "Sardinia",
      "dates": {"start": "2026-07-05", "end": "2026-07-12"},
      "guests": 4,
      "budget": "mid-range",
      "experience": "intermediate",
      "notes": "Looking for a monohull in Sardinia"
    }
  }' | python3 -m json.tool
```

Available regions in the CSV: **Sardinia**, **Sicily**, **Marmaris**. Any other region returns `manual_required`.

### ⏳ Image cache (`scripts/cache_yacht_images.py`)
Partially complete. Script auto-logs in to booking-manager portal, fetches live detail pages for fresh photo URLs, downloads, resizes to 1920px, and uploads to WordPress.

**To wipe incomplete cache and restart from scratch:**
```bash
cd ~/Documents/SailScanner/Website/Plugins/MU\ Plugins/Proposals
rm scripts/image_cache.json
.venv/bin/python scripts/cache_yacht_images.py
```

**The cache is resumable** — safe to Ctrl-C and re-run. It skips already-cached yachts. Progress is saved after every yacht.

**Useful flags:**
```bash
# Single yacht (for testing)
.venv/bin/python scripts/cache_yacht_images.py --yacht-id 1341585820000101933

# Force re-process even if cached
.venv/bin/python scripts/cache_yacht_images.py --force

# Dry run (no uploads, just shows what it would do)
.venv/bin/python scripts/cache_yacht_images.py --dry-run --limit 3
```

**Known issue:** WordPress upload sometimes times out on large images. Script retries up to 3 times with backoff. If yachts end up with fewer images than expected, re-run with `--force` after the full run completes.

### ✅ WordPress plugin
Deployed and working at sailscanner.ai. Proposals and yacht pages render correctly with AI copy and images (when cached).

---

## What's left to do (in order)

### 1. Finish image cache run
Run overnight. ~381 yachts, ~90–120 minutes with the current settings.
```bash
rm scripts/image_cache.json   # if restarting from scratch
.venv/bin/python scripts/cache_yacht_images.py
```

### 2. Test a full proposal end-to-end
Once the cache has a decent number of yachts, run the API test above with `"region": "Sardinia"` and check:
- Proposal page appears at sailscanner.ai/proposals/...
- AI copy is in the intro (not generic hardcoded text)
- Yacht images appear (not broken)
- Email button shows `chris@sailscanner.ai` not the client's address

### 3. Git commit everything
Stage and commit all changed files:
- `app.py`
- `scripts/build_proposal_from_csv.py`
- `scripts/cache_yacht_images.py`
- `scripts/image_cache.json` (or add to .gitignore if large)
- `sailscanner-proposals/includes/class-ss-proposal-rest-core.php`
- `.env.example` (not `.env` — never commit credentials)

### 4. Re-enable API secret auth in `app.py`
Find the commented-out block (around line 195) and uncomment it before deploying:
```python
# TODO: re-enable before deploying to production
if API_SECRET:
    incoming_secret = request.headers.get("x-api-secret", "")
    if incoming_secret != API_SECRET:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Api-Secret header")
```
Set `SAILSCANNER_API_SECRET` to a strong random string in `.env` on the VPS, and enter the same value in Make.com.

### 5. Deploy to Hetzner VPS
- SSH to VPS, clone/pull repo
- Copy `.env` with production credentials
- Run under systemd or screen:
  ```bash
  .venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
  ```
- Note the VPS IP/domain — this is what Make.com will POST to

### 6. Complete Make.com scenario (modules 2–4)
Module 1 (quiz → Make.com trigger) is already set up.

**Module 2:** HTTP POST to `https://<vps-ip>:8000/build-proposal`
- Body: the full quiz lead JSON (same structure as the test curl above)
- Header: `X-Api-Secret: <your secret>`
- Parse response: if `status == "ok"` → continue; if `status == "manual_required"` → branch to notification

**Module 3:** Send proposal email
- Use the `proposal_url` from the response
- Trigger Klaviyo (or Gmail as interim) with client's name + proposal link

**Module 4:** WhatsApp (optional for v1)
- Use `SAILSCANNER_CONTACT_WHATSAPP` in `.env` — currently blank, add your E.164 number

### 7. Klaviyo email template
Simple transactional email: "Your sailing proposal is ready"
- CTA button linking to `proposal_url`
- From: chris@sailscanner.ai

---

## Credentials (all in `.env`)

| Key | What it's for |
|-----|--------------|
| `SAILSCANNER_WP_URL` | WordPress REST API base |
| `SAILSCANNER_WP_USER` | WP application password username |
| `SAILSCANNER_WP_APP_PASSWORD` | WP application password |
| `OPENAI_API_KEY` | GPT-4o-mini for AI yacht selection |
| `SAILSCANNER_API_SECRET` | Shared secret between Make.com and FastAPI (re-enable auth before deploy) |
| `SAILSCANNER_CONTACT_EMAIL` | Broker email shown on proposals (currently `chris@sailscanner.ai`) |
| `SAILSCANNER_CONTACT_WHATSAPP` | Broker WhatsApp E.164 number (currently blank) |
| `BOOKING_MANAGER_EMAIL` | Portal login for image caching |
| `BOOKING_MANAGER_PASSWORD` | Portal login for image caching |

---

## Data

- **Yacht database:** `/Users/chrishennessy/Documents/SailScanner/Provider Data/yacht_database_full.csv`
- **381 yachts** across Sardinia, Sicily, and Marmaris
- **Image cache:** `scripts/image_cache.json` — maps yacht_id to WordPress-hosted image URLs

---

## Key architectural decisions / gotchas

- **Portal image URLs are short-lived.** Never use URLs from the CSV directly — always fetch the live detail page to get fresh `bmdoc/` URLs. `cache_yacht_images.py` does this automatically.
- **bmdoc/ URLs are relative to `/wbm2/`**, not the portal root. Full URL: `https://portal.booking-manager.com/wbm2/bmdoc/...`
- **WordPress auto-scales images >2560px** (adds `-scaled` suffix and slows uploads). We pre-resize to 1920px in Pillow before uploading to avoid this.
- **AI copy goes into `post_content`**, not `ss_intro_html` — the template prefers `post_content`. The PHP plugin now checks for AI copy first and only falls back to the generic template if `ss_intro_html` is empty.
- **Unsupported regions** return `{"status": "manual_required"}` — Make.com must branch on this to alert Chris rather than silently failing.
