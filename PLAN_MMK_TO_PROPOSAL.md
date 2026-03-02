# Plan: MMK Email Block → SailScanner Proposal + Proposal Yacht Pages

This plan aligns the existing MMK-based email snippet workflow with the SailScanner proposal system: parse MMK HTML (bareboat or skippered), produce a live proposal with full yacht data, optionally fetch each yacht’s MMK “More Info” (YachtDetails) page and replicate that content on our own proposal-yacht pages (no supplier name, use make/model only). It also defines the proposal UI to match the ChatFox-style layout (sidebar, section order, styling, mobile).

---

## 1. Current state

### 1.1 Existing scripts (examples/)

| File | Purpose |
|------|--------|
| `build_email_block.py` | Reads MMK HTML export → SailScanner-branded **HTML email snippet** (bareboat). Uses model (or sanitized name) for display; “More info” links to MMK. |
| `build_email_block_skippered.py` | Same for **skippered**: adds skipper cost, changes “Bareboat” to “Skippered” in listings. |
| `mmk-nik-2.html` | Sample MMK HTML input (multi-yacht quote). |
| `email_snippet-mmk-nik-2-20260224-2326.html` | Sample output snippet. |

### 1.2 Parsed data (YachtEntry)

From MMK HTML we already get per yacht:

- **Identity:** name, boat_type, model, charter_type  
- **Media:** image_urls (2), more_info_url  
- **Pricing:** base_price, discount_items, charter_price_net, mandatory_advance_items, mandatory_base_items, optional_items, deposit  
- **Times:** check_in_time, check_out_time, date_from_str, date_to_str  
- **Specs:** year, length, berths, cabins, wc_shower, mainsail  
- **Location:** base_location, to_location  
- **Other:** equipment_tags, licence_required  

Display title is already “model not boat name” where possible (e.g. “Lagoon 40 (3 cab)” not “Saudade”).

### 1.3 MMK “More Info” / YachtDetails

- “More info” link in the snippet points to an MMK URL (e.g. `view=Event&event=moreInfo&...&page=<base64>`).
- The base64 `page` param decodes to a **YachtDetails** URL, e.g.  
  `https://www.booking-manager.com/wbm2/page.html?view=YachtDetails&companyid=7914&yachtId=...&setlang=en&dateFrom=...&dateTo=...`
- Direct form (from your example):  
  `https://portal.booking-manager.com/wbm2/page.html?view=YachtDetails&addMargins=true&templateType=responsive&companyid=7914&yachtId=31463911541600198`
- That page contains: yacht name in title, technical characteristics, equipment, obligatory/optional extras tables, images. We must **never** show supplier name or yacht name on our site; we use **make/model** only.

---

## 2. Goals (summary)

1. **Proposal from MMK (bareboat or skippered)**  
   One Python pipeline: input = MMK HTML (+ charter type). Output = proposal payload (intro, requirements, itinerary, notes, contact, **yacht selection** with full data) and **optionally** per-yacht “detail” content from MMK YachtDetails.

2. **“Yacht Selection” (renamed from “Yacht Picks”)**  
   Proposal main content includes a section “Yacht Selection” with one card per yacht (same data as today’s email block: images, specs, prices, equipment, base/dates). “View details” links to **our** proposal-yacht URL, not MMK.

3. **Proposal-yacht pages = our replica of MMK YachtDetails**  
   For each yacht we (optionally) fetch the MMK YachtDetails page, scrape: technical characteristics, equipment, prices (obligatory/optional), images. We store that in `ss_proposal_yacht` (or equivalent) and render on `/proposal-yacht/{slug}/` with:
   - **No** supplier/operator name  
   - **No** yacht name (e.g. “Saudade”) — use make/model only (e.g. “Sun Odyssey 349”)  
   So the client cannot use our page to go direct to the supplier for a better price.

4. **Charter type**  
   User can choose **bareboat** or **skippered** (CLI flag or two entrypoints reusing shared parser).

5. **Proposal UI (ChatFox-like)**  
   - **Sidebar (left):** Only section links (droplinks that scroll to sections). Order:  
     1. Introduction  
     2. Your Requirements  
     3. Yacht Selection  
     4. Example Itinerary  
     5. How it Works  
     6. Next Steps  
     7. Contact  
   - Icons beside each sidebar link; card-style blocks; `<hr>` (or equivalent) between main sections.  
   - Intro at top; requirements just below in a compact, clear format.  
   - **Mobile:** Sidebar moves to **top** of page (not hidden).

6. **Run locally in Python**  
   Script(s) run on this machine: parse MMK HTML → build proposal payload (+ optionally fetch MMK detail pages, parse, sanitize) → POST to WordPress (existing `proposal_import.py` flow) so the site has the proposal and all proposal-yacht pages with images, info, prices.

---

## 3. Phases

### Phase 1: Proposal builder from MMK (no scraping)

**Scope:** Reuse MMK parsing from `build_email_block*.py`, output **proposal JSON** instead of (or in addition to) the email snippet.

**Tasks:**

1. **Shared parser module**  
   - Extract the common MMK parsing (split_sections, parse_yacht_section, YachtEntry, Money, etc.) into a shared module (e.g. `scripts/mmk_parser.py` or `scripts/lib/`) so both bareboat and skippered can use it.
   - Keep charter-type logic (bareboat vs skippered) in the builder (e.g. “Skippered” label, skipper line in totals for skippered).

2. **Proposal payload builder**  
   - New script (e.g. `scripts/build_proposal_from_mmk.py`) that:
     - Takes: path(s) to MMK HTML file(s), `--type bareboat|skippered`, optional intro/itinerary/notes/contact/requirements (file or defaults).
     - Parses all yacht sections into `YachtEntry` list.
     - Builds one yacht object per entry for **ss_yacht_data** with: display_name (= model or sanitized name, **never** boat name), images_json, highlights_json (e.g. from equipment_tags), cabins, berths, length_m, year, base_name, country, region, model, plus **pricing/optional fields** if we extend the API (see Phase 2): e.g. charter_price_net, mandatory_extras, optional_extras, deposit, check_in/out.
     - Outputs: proposal JSON (same shape as `proposal_payload_test.json`) with `yachts`, `intro_html`, `itinerary_html`, `notes_html`, `contact_whatsapp`, `contact_email`, `requirements`.
   - Optional: still write the email snippet to a file for comparison/backward use.

3. **Charter type selection**  
   - `--type bareboat` or `--type skippered` (or `--skippered` flag).  
   - Skippered: same as existing skippered script (charter_type “Skippered”, skipper in optional/total).

4. **Integration with existing import**  
   - Run: `python scripts/build_proposal_from_mmk.py --input examples/mmk-nik-2.html --type skippered` → writes `proposal_from_mmk.json` (or stdout).  
   - Then: `SAILSCANNER_PROPOSAL_JSON=proposal_from_mmk.json python scripts/proposal_import.py` → creates proposal on WordPress.  
   - Or add a `--upload` flag that builds the JSON and calls the existing proposal_import logic (POST wp/v2/ss_proposal) so one command does “MMK → proposal on site”.

**Deliverables:**  
- Shared MMK parsing (if new module).  
- `build_proposal_from_mmk.py` with bareboat/skippered.  
- Proposal appears on site with “Yacht Selection” (we’ll rename in Phase 3) and “View details” linking to our proposal-yacht pages (content still from existing ss_proposal_yacht meta only; no MMK detail scrape yet).

---

### Phase 2: Enrich proposal-yacht data (prices, specs, equipment)

**Scope:** Extend WordPress and payload so each yacht in the proposal can store and display the same pricing/specs/equipment we already have in YachtEntry (no scraping yet).

**Tasks:**

1. **REST & meta for ss_proposal_yacht**  
   - Add meta (or JSON blob) for: charter_price_net, mandatory_advance_items, mandatory_base_items, optional_items, deposit, check_in_time, check_out_time, equipment_tags, base_location, to_location, date_from_str, date_to_str (and any other YachtEntry fields we want on the detail page).  
   - Either one `ss_yacht_detail_json` or separate meta keys; ensure REST and `after_insert_proposal` / `create_proposal_yacht_posts` accept them.

2. **Proposal payload**  
   - In `build_proposal_from_mmk.py`, for each yacht add the above fields to the object we send in ss_yacht_data (or in an extended structure the server maps into ss_proposal_yacht).

3. **single-ss-proposal-yacht.php**  
   - Use the new meta to show: key facts (year, length, berths, cabins, WC, mainsail), base/dates, **pricing** (charter price, mandatory extras, optional, total, deposit), check-in/out, equipment tags.  
   - Keep “no supplier / no yacht name”: title = display_name (model).

**Deliverables:**  
- Proposal-yacht pages show full pricing and specs from MMK list view (no YachtDetails fetch yet).

---

### Phase 3: Sidebar and section order (ChatFox-like)

**Scope:** Match the reference layout: sidebar with section links only, order and naming, styling, mobile = sidebar at top.

**Tasks:**

1. **Rename “Yacht Picks” → “Yacht Selection”**  
   - In `single-ss-proposal.php` and any strings/rules: replace “Yacht picks” / “Your yacht picks” with “Yacht Selection” / “Your yacht selection”.

2. **Sidebar: links only, fixed order**  
   - Sidebar contains **only** these links (no “How it works” body or “Your requirements” body in the sidebar; those live in the main column):  
     1. Introduction  
     2. Your Requirements  
     3. Yacht Selection  
     4. Example Itinerary  
     5. How it Works  
     6. Next Steps  
     7. Contact  
   - Each link is a droplink (anchor) that scrolls to the corresponding section in the main content.  
   - Optional: per-section sublinks (e.g. under “Yacht Selection”, one link per yacht card) as in ChatFox “Contents”.

3. **Main content section order**  
   - Reorder main sections to match:  
     1. Introduction (intro at top)  
     2. Your Requirements (compact, simple; e.g. definition list or small cards)  
     3. Yacht Selection (cards as now)  
     4. Example Itinerary  
     5. How it Works (steps)  
     6. Next Steps  
     7. Contact  
   - Add `<hr>` (or border) between each section for clear separation.

4. **Styling (ChatFox-like)**  
   - Icons beside each sidebar link (e.g. dashicons or simple SVG).  
   - Card styling for sidebar and/or section blocks.  
   - Intro and requirements: compact, easy to scan (same content as now, layout tweaks).

5. **Mobile**  
   - Sidebar moves to **top** of page (not hidden): e.g. sticky or static block at top with the same section links (can remain collapsible “Contents” if desired).

**Deliverables:**  
- Updated `single-ss-proposal.php` and `proposal-portal.css`.  
- Cursor rules / brief updated for “Yacht Selection” and sidebar order.

---

### Phase 4: Fetch MMK YachtDetails and replicate on proposal-yacht

**Scope:** For each yacht, optionally fetch the MMK “More Info” (YachtDetails) page, scrape content, sanitize (no supplier, no yacht name), and store/display on our proposal-yacht page.

**Tasks:**

1. **Resolve YachtDetails URL**  
   - From the “More info” link in the email/quote: parse the `page` query param (base64), decode to get YachtDetails URL, or extract companyid + yachtId and build `https://portal.booking-manager.com/wbm2/page.html?view=YachtDetails&companyid=...&yachtId=...`.  
   - Handle both portal. and www. booking-manager.com if needed.

2. **Scraper (Python)**  
   - Optional script or step in `build_proposal_from_mmk.py`: for each yacht with more_info_url, GET the YachtDetails page (with a session/cookies if required), parse HTML.  
   - Extract:  
     - All images (gallery).  
     - Technical characteristics (table/section).  
     - Equipment list.  
     - Obligatory extras table, optional extras table, prices.  
     - Any layout/description text (optional).  
   - Strip: supplier name, operator, yacht name (replace with model/make in titles/headings).  
   - Output: structured data (e.g. images_json, specs_json, equipment_json, prices_json, optional_html) that we can send per yacht.

3. **Rate limiting and robustness**  
   - Throttle requests (e.g. 1–2 per second).  
   - Retries and timeouts; skip yacht on failure and log.

4. **Payload and WordPress**  
   - Extend ss_yacht_data (or a separate “detail” blob per yacht) with the scraped fields.  
   - REST and `after_insert_proposal` / `create_proposal_yacht_posts` must persist these into ss_proposal_yacht meta (e.g. specs_json, equipment_json, prices_json, extra images).

5. **single-ss-proposal-yacht.php**  
   - Render: gallery (all images), technical characteristics, equipment, obligatory/optional extras and prices (if we store them), plus existing key facts and contact CTAs.  
   - Everywhere we show “title”, use display_name (make/model) only.

**Deliverables:**  
- Scraper that turns MMK YachtDetails into sanitized structured data.  
- Proposal-yacht pages that look like a cleaned-up version of MMK YachtDetails (no supplier, no boat name).

**Risks:**  
- MMK may require auth or change HTML; scraper may need updates.  
- Consider a “no-scrape” mode that only uses list-view data (Phase 1–2) if scraping is blocked or unreliable.

---

### Phase 5: One-command flow and docs

**Scope:** Single entrypoint to go from MMK HTML to live proposal (+ optional scrape), and document the flow.

**Tasks:**

1. **CLI**  
   - e.g. `python scripts/build_proposal_from_mmk.py --input mmk-nik-2.html --type skippered [--fetch-details] [--upload]`  
   - `--fetch-details`: run Phase 4 scrape for each yacht and include in payload.  
   - `--upload`: after building JSON, call proposal_import (POST proposal) and print proposal URL.

2. **README / docs**  
   - How to run MMK → proposal (bareboat vs skippered).  
   - How to run with/without `--fetch-details` and `--upload`.  
   - Note that “View details” goes to our proposal-yacht page; no MMK links on the proposal.

---

## 4. Sidebar and section spec (reference)

| # | Sidebar label   | Main content block        | Notes                          |
|---|-----------------|---------------------------|--------------------------------|
| 1 | Introduction    | Intro HTML                | At top                         |
| 2 | Your Requirements | Requirements (compact)   | DL or small cards              |
| 3 | Yacht Selection | Yacht cards               | Renamed from Yacht Picks       |
| 4 | Example Itinerary | Itinerary HTML          |                                |
| 5 | How it Works    | Steps (1–3)               | Same content as now            |
| 6 | Next Steps      | Next steps list           |                                |
| 7 | Contact         | WhatsApp + email          |                                |

- Sidebar: left, fixed (sticky) on desktop; on mobile, same links at **top** of page.  
- Icons beside sidebar links; card styling; `<hr>` between main sections.  
- ChatFox reference: [portal.chatfox.ai/proposals/JGHJI3](https://portal.chatfox.ai/proposals/JGHJI3).

---

## 5. File and script layout (proposed)

```
scripts/
  mmk_parser.py              # Shared: parse MMK HTML → list[YachtEntry] (Phase 1)
  build_proposal_from_mmk.py # MMK → proposal JSON (+ optional scrape, upload) (Phase 1–5)
  proposal_import.py        # Existing: POST proposal to wp/v2
  proposal_payload_test.json
  proposal_from_mmk.json    # Generated by build_proposal_from_mmk.py
examples/
  build_email_block.py
  build_email_block_skippered.py
  mmk-nik-2.html
  email_snippet-mmk-nik-2-20260224-2326.html
sailscanner-proposals/
  templates/single-ss-proposal.php      # Section order, sidebar links, “Yacht Selection” (Phase 3)
  templates/single-ss-proposal-yacht.php # Prices, specs, equipment; later scraped content (Phase 2, 4)
  assets/proposal-portal.css             # Sidebar icons, cards, hr, mobile top sidebar (Phase 3)
  includes/
    class-ss-proposal-rest-core.php      # Optional: extra meta for ss_proposal_yacht (Phase 2, 4)
```

---

## 6. Order of implementation

1. **Phase 1** – Proposal from MMK (bareboat/skippered), no scraping; “View details” = our proposal-yacht (current meta).  
2. **Phase 3** – Sidebar + section order + “Yacht Selection” + ChatFox-like styling + mobile sidebar at top.  
3. **Phase 2** – Enrich proposal-yacht with prices/specs/equipment from YachtEntry.  
4. **Phase 4** – Optional MMK YachtDetails fetch and replicate on proposal-yacht.  
5. **Phase 5** – One-command CLI and docs.

Phases 2 and 4 can be swapped if you prefer “scraped detail page” before “richer list-view data on detail page”.

---

## 7. Out of scope (for this plan)

- Changing yacht_charter or any other CPT (already out of scope).  
- HMAC/sailscanner/v1 (we use wp/v2 + Basic auth for import).  
- Editing the existing email snippet output format (optional to keep for backward compatibility).
