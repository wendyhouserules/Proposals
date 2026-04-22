#!/usr/bin/env node
/**
 * make_pipeline_doc.js
 * Generates pipeline-logic.docx — full step-by-step breakdown of the proposal pipeline.
 * Usage: node scripts/make_pipeline_doc.js <output.docx>
 */
"use strict";
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  VerticalAlign, LevelFormat, PageNumber, Header, Footer,
} = require("docx");

const outputFile = process.argv[2] || "pipeline-logic.docx";
const today = new Date().toISOString().slice(0, 10);

// ── Colours ────────────────────────────────────────────────────────────────────
const C = {
  navy:     "1B3A5C",
  teal:     "0F7173",
  green:    "1D7044",
  amber:    "7B5E00",
  red:      "8B2020",
  bg:       "F2F7FB",
  greenBg:  "DFF0E8",
  amberBg:  "FEF9E7",
  redBg:    "FDECEA",
  headerBg: "1B3A5C",
  altRow:   "F2F7FB",
  border:   "CCCCCC",
  white:    "FFFFFF",
  grey:     "555555",
};

// ── Helpers ────────────────────────────────────────────────────────────────────
const b = { style: BorderStyle.SINGLE, size: 1, color: C.border };
const borders = { top: b, bottom: b, left: b, right: b };

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 320, after: 160 },
    children: [new TextRun({ text, font: "Arial", size: 36, bold: true, color: C.navy })],
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 280, after: 120 },
    children: [new TextRun({ text, font: "Arial", size: 28, bold: true, color: C.teal })],
  });
}
function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 200, after: 80 },
    children: [new TextRun({ text, font: "Arial", size: 24, bold: true, color: C.navy })],
  });
}
function p(text, opts = {}) {
  const { color = "222222", bold = false, italic = false, size = 22, spacing = { before: 60, after: 80 } } = opts;
  return new Paragraph({
    spacing,
    children: [new TextRun({ text, font: "Arial", size, bold, color, italics: italic })],
  });
}
function note(text, type = "info") {
  const bgMap  = { info: C.bg,      warn: C.amberBg, stop: C.redBg,   ok: C.greenBg };
  const clrMap = { info: C.teal,    warn: C.amber,   stop: C.red,     ok: C.green   };
  const pfxMap = { info: "NOTE  ",  warn: "CAUTION  ", stop: "STOP  ", ok: "OK  " };
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [new TableRow({ children: [
      new TableCell({
        borders,
        width: { size: 9360, type: WidthType.DXA },
        shading: { fill: bgMap[type], type: ShadingType.CLEAR },
        margins: { top: 100, bottom: 100, left: 160, right: 160 },
        children: [new Paragraph({ children: [
          new TextRun({ text: pfxMap[type], font: "Arial", size: 20, bold: true, color: clrMap[type] }),
          new TextRun({ text, font: "Arial", size: 20, color: "222222" }),
        ]})],
      }),
    ]})],
  });
}
function spacer(before = 80, after = 80) {
  return new Paragraph({ spacing: { before, after }, children: [] });
}
function bullet(text, sub = false) {
  return new Paragraph({
    numbering: { reference: "bullets", level: sub ? 1 : 0 },
    spacing: { before: 40, after: 40 },
    children: [new TextRun({ text, font: "Arial", size: 20, color: "222222" })],
  });
}
function numbered(text, level = 0) {
  return new Paragraph({
    numbering: { reference: `numbers-${level}`, level: 0 },
    spacing: { before: 60, after: 60 },
    children: [new TextRun({ text, font: "Arial", size: 21, color: "222222" })],
  });
}

function twoCol(label, value, rowBg = C.white, labelColor = "222222", valueColor = "222222", valueBold = false) {
  return new TableRow({ children: [
    new TableCell({
      borders, width: { size: 3200, type: WidthType.DXA },
      shading: { fill: rowBg, type: ShadingType.CLEAR },
      margins: { top: 80, bottom: 80, left: 120, right: 120 },
      children: [new Paragraph({ children: [new TextRun({ text: label, font: "Arial", size: 20, bold: true, color: labelColor })] })],
    }),
    new TableCell({
      borders, width: { size: 6160, type: WidthType.DXA },
      shading: { fill: rowBg, type: ShadingType.CLEAR },
      margins: { top: 80, bottom: 80, left: 120, right: 120 },
      children: [new Paragraph({ children: [new TextRun({ text: value, font: "Arial", size: 20, bold: valueBold, color: valueColor })] })],
    }),
  ]});
}

function table2(rows) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [3200, 6160],
    rows: rows.map(([l, v, bg, lc, vc, vb], i) =>
      twoCol(l, v, bg || (i % 2 === 0 ? C.altRow : C.white), lc, vc, vb)
    ),
  });
}

function headerRow(cols, widths) {
  return new TableRow({
    tableHeader: true,
    children: cols.map((text, i) => new TableCell({
      borders,
      width: { size: widths[i], type: WidthType.DXA },
      shading: { fill: C.headerBg, type: ShadingType.CLEAR },
      margins: { top: 80, bottom: 80, left: 120, right: 120 },
      children: [new Paragraph({ children: [new TextRun({ text, font: "Arial", size: 18, bold: true, color: C.white })] })],
    })),
  });
}
function dataRow(cols, widths, bg = C.white) {
  return new TableRow({ children: cols.map((text, i) => new TableCell({
    borders,
    width: { size: widths[i], type: WidthType.DXA },
    shading: { fill: bg, type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ children: [new TextRun({ text: String(text || ""), font: "Arial", size: 19, color: "222222" })] })],
  })) });
}

// ── Content ────────────────────────────────────────────────────────────────────
const children = [

  // ── Title ──────────────────────────────────────────────────────────────────
  h1("SailScanner Proposal Pipeline — Full Logic Reference"),
  p(`Last updated: ${today}  ·  Covers: app.py, portal_live_search.py, live_proposal_builder.py, ai_select.py`, { color: C.grey, size: 19 }),
  spacer(40, 160),

  // ── Overview ───────────────────────────────────────────────────────────────
  h2("Overview"),
  p("When a lead arrives from the quiz, the pipeline runs these stages in sequence:"),
  spacer(),
  table2([
    ["Stage", "What it does"],
    ["1. Auth",            "Validates the X-Api-Secret header from Make.com"],
    ["2. Parse lead",      "Extracts region, dates, guests, budget, boat type, size, cabins"],
    ["3. Portal search",   "Fetches all available yachts with live prices from booking-manager.com"],
    ["4. Pro-rating",      "If the stay is non-standard and results are thin, re-searches at 7n/14n and scales prices"],
    ["5. Filter",          "Applies boat type, cabins, size and budget to the portal results"],
    ["6. Relaxation",      "If fewer than 3 yachts survive filtering, widens constraints step by step"],
    ["7. AI selection",    "Claude picks 4-6 yachts and writes personalised intro + notes"],
    ["8. Photo fetch",     "Downloads full gallery and deck plan for each selected yacht"],
    ["9. WordPress upload","Builds the proposal post and returns the public URL"],
  ]),
  spacer(120, 40),
  note("Pro-rating (step 4) happens BEFORE filtering (step 5). The filter always runs against prices that are already correct for the client's actual duration.", "info"),
  spacer(160),

  // ── Step 1: Auth ───────────────────────────────────────────────────────────
  h2("Step 1 — Auth"),
  p("Every POST to /build-proposal must include the header:"),
  p("    X-Api-Secret: <SAILSCANNER_API_SECRET>", { color: C.teal, bold: true }),
  p("If the secret is set in .env and the header is missing or wrong, the server returns 401 immediately. If no secret is configured (dev mode), auth is skipped."),
  spacer(160),

  // ── Step 2: Parse lead ─────────────────────────────────────────────────────
  h2("Step 2 — Parse Lead"),
  p("The lead JSON (posted by Make.com from the quiz) is unpacked into the fields the rest of the pipeline uses:"),
  spacer(),
  table2([
    ["Field",         "Source in JSON",                              C.altRow],
    ["region",        "answers.region[0]  (falls back to answers.country for destinations that skip the region step, e.g. Seychelles, Thailand)"],
    ["start date",    "answers.dates.start  (ISO 8601: YYYY-MM-DD)"],
    ["duration",      "Calculated as end date minus start date in days"],
    ["adults",        "answers.guests.adults"],
    ["children",      "answers.guests.children"],
    ["boat type",     "answers.boatType  (catamaran | monohull | either | any)"],
    ["size",          "answers.size  (e.g. '33-40', '40-50', '50+')  — interpreted as feet"],
    ["cabins",        "answers.cabins  (minimum number required)"],
    ["budget",        "answers.budget  (e.g. '5-7k', '9.5k-12.5k')  — charter price only"],
    ["charter type",  "answers.charterType  (bareboat | skippered)"],
    ["crew services", "answers.crewServices  (hostess, chef, provisioning flags)"],
  ]),
  spacer(160),

  // ── Step 3: Portal search ──────────────────────────────────────────────────
  h2("Step 3 — Portal Search"),
  p("The pipeline searches the Booking Manager portal (booking-manager.com) for all yachts available for the client's exact dates and region."),
  spacer(),
  h3("How the search works"),
  table2([
    ["Endpoint",        "POST https://portal.booking-manager.com/wbm2/page.html  with action=getResults, responseType=JSON"],
    ["Authentication",  "Session cookie from email/password login — shared session is reused across requests"],
    ["Region lookup",   "The region name (e.g. 'Cyclades') maps to a numeric portal region ID and a list of marina service IDs in REGION_CONFIG"],
    ["Boat kind filter","boatType is mapped to a portal filter_kind: 'Catamaran', 'Sail boat', or '' (all). When a specific kind is set, the service ID filter is cleared so that providers outside the pre-configured list are also included"],
    ["Duration",        "The exact client duration is passed (e.g. 10 nights)"],
    ["Flexibility",     "Always set to 'closest_day' — the portal returns the nearest available week to the requested start date"],
    ["Pagination",      "The portal returns max 50 yachts per page. The pipeline fetches all pages. It stops when a page adds zero new yacht IDs (indicating the portal has cycled back to the start), when a page has fewer than 10 results, or when 30 pages have been fetched (1,500 yacht cap)"],
  ]),
  spacer(),
  note("The portal occasionally returns a duplicate yacht ID within a single page. Our parser deduplicates by ID, so a 'full' page may parse to 49 rather than 50. The stop condition checks for new IDs added, not raw page count.", "info"),
  spacer(160),

  // ── Step 4: Pro-rating ─────────────────────────────────────────────────────
  h2("Step 4 — Pro-Rating  (only triggers in specific conditions)"),
  p("Pro-rating exists because the portal is built around 7-night and 14-night charters. Yachts listed for, say, a 5-night or 10-night stay are a much smaller subset of the total fleet."),
  spacer(),
  h3("When pro-rating triggers"),
  p("Both conditions must be true:"),
  bullet("The exact-duration search returned fewer than 5 yachts, AND"),
  bullet("The duration is non-standard (i.e. not exactly 7 or 14 nights)"),
  spacer(),
  table2([
    ["Duration",       "Standard?",                                  C.altRow],
    ["7 nights",       "Yes — no pro-rating ever needed"],
    ["14 nights",      "Yes — no pro-rating ever needed"],
    ["5 nights",       "No — if fewer than 5 results, retry at 7n"],
    ["10 nights",      "No — if fewer than 5 results, retry at 14n"],
    ["6 nights",       "No — if fewer than 5 results, retry at 7n"],
    ["13 nights",      "No — if fewer than 5 results, retry at 14n"],
  ]),
  spacer(),
  h3("What happens when it triggers"),
  numbered("Re-searches the portal at the standard duration (7n or 14n)  with the same region, dates and boat kind", 0),
  numbered("Scales all prices from the standard rate down to the client's actual duration  (e.g. a 10-night rate is multiplied by 10/14 = 0.714)", 0),
  numbered("Mandatory extras (cleaning fees, permits, skipper, deposit)  are NOT scaled — these are per-booking, not per-night", 0),
  numbered("Per-day optional extras (e.g. 'Skipper €150/day')  ARE scaled — multiplied by actual_days", 0),
  numbered("A 'pro_rated' flag is set on every result, and the AI is given a detailed mandatory notice to include in the intro", 0),
  spacer(),
  note("Pro-rating happens BEFORE the filter runs. The filtered set always sees prices denominated in the client's actual duration, whether pro-rated or not.", "warn"),
  spacer(),
  note("If the pro-rated retry ALSO returns 0 yachts, the pipeline returns status=manual_required and sends an alert email. No further steps run.", "stop"),
  spacer(160),

  // ── Step 5: Filter ─────────────────────────────────────────────────────────
  h2("Step 5 — Filter"),
  p("The full portal result set is filtered down to yachts that actually match the lead. Filters are applied in this order — a yacht must pass all four to survive:"),
  spacer(),

  // Filter table
  (() => {
    const W = [1800, 3500, 4060];
    return new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: W,
      rows: [
        headerRow(["Filter", "Rule", "Notes"], W),
        dataRow(["1. Boat type", "catamaran → kind must be 'Catamaran'.  monohull → kind must be 'Sail boat'.  either / any → kind must be 'Sail boat' or 'Catamaran' (gulets and motor yachts are always excluded).", "The portal already pre-filters by kind but we check client-side too to catch any leakage"], W, C.altRow),
        dataRow(["2. Cabins", "Yacht must have >= the number of cabins requested", "Yachts with no cabin data in the portal response are passed through (not rejected)"], W),
        dataRow(["3. Size / length", "Yacht length (in feet) must fall within the range from answers.size (e.g. 40-50 means 40ft <= length <= 50ft)", "Yachts with no length data are passed through. Size filter is removed entirely in relaxation step 3."], W, C.altRow),
        dataRow(["4. Budget", "charter_price must fall within the min and max for the budget label (e.g. '5-7k' = €5,000–€7,000). No floor is applied to 'under-X' tiers.", "Budget is charter price only — it does not include skipper, hostess, or provisioning costs. Those are extras shown separately in the proposal."], W),
      ],
    });
  })(),
  spacer(),
  p("Surviving yachts are sorted cheapest first. Yachts with no price are appended at the end.", { color: C.grey, italic: true }),
  spacer(160),

  // ── Step 6: Filter relaxation ──────────────────────────────────────────────
  h2("Step 6 — Filter Relaxation"),
  p("If fewer than 3 yachts survive the exact filter, the pipeline widens constraints step by step until 3+ yachts are found. As soon as a step reaches the target, relaxation stops — later steps do not run."),
  spacer(),

  (() => {
    const W = [600, 2400, 2400, 3960];
    return new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: W,
      rows: [
        headerRow(["Step", "Size filter", "Budget filter", "Notes"], W),
        dataRow(["0 (exact)", "Original (e.g. 40–50ft)", "Original (e.g. €5k–€7k)", "This is the initial filter — not a relaxation step"], W, C.altRow),
        dataRow(["1", "±5ft  (e.g. 35–55ft)", "Unchanged", "Tries a slightly larger/smaller boat before touching budget"], W),
        dataRow(["2", "Unchanged (original)", "±€2k  (e.g. €3k–€9k)", "Restores exact size, widens budget modestly"], W, C.altRow),
        dataRow(["3", "Removed entirely", "±€4k  (e.g. €1k–€11k)", "Drops size constraint — any size boat in the wider budget range"], W),
        dataRow(["4", "Removed entirely", "±€4k", "Same budget as step 3, but boat type opened to both sailing yachts AND catamarans (if client asked for one specific type). Gulets and motor yachts still excluded."], W, C.altRow),
      ],
    });
  })(),
  spacer(),
  note("If 0 yachts survive even after step 4, the pipeline returns status=manual_required. No AI call is made.", "stop"),
  spacer(),
  h3("What the AI is told about relaxation"),
  p("When step 4 (sail+cat) was needed and the client requested a specific boat type, the AI receives a boat_type_context note instructing it to:"),
  bullet("Prioritise the client's preferred type if any were found"),
  bullet("Only include the other type if needed to reach 4 options"),
  bullet("Mention naturally in the intro that availability was limited for their preferred type"),
  spacer(),
  p("If no boats of the preferred type were found at all, the AI is told to acknowledge this clearly and offer to search again for different dates.", { italic: true, color: C.grey }),
  spacer(160),

  // ── Step 7: AI selection ───────────────────────────────────────────────────
  h2("Step 7 — AI Selection"),
  p("Claude (claude-sonnet) receives the filtered yacht list and the lead data, and returns:"),
  bullet("4–6 yacht IDs to include in the proposal (ordered by recommendation strength)"),
  bullet("1–2 IDs flagged as 'recommended' (highlighted in the proposal UI)"),
  bullet("A personalised intro paragraph in HTML"),
  bullet("A notes_html section with any caveats or follow-up suggestions"),
  bullet("Per-yacht recommendation notes"),
  spacer(),
  h3("Context flags passed to the AI"),
  table2([
    ["Flag",                  "When it is set",                                                                                  C.altRow],
    ["pro_rate_context",      "When pro-rating was applied — instructs the AI to explain the duration mismatch, the pro-rated pricing, and that 7-night availability is wider"],
    ["limited_avail_context", "When original results were fewer than 15 and the duration is non-standard — softer note to mention that 7/14-night charters have wider selection"],
    ["boat_type_context",     "When relaxation step 4 was used and boat type was widened"],
  ]),
  spacer(),
  h3("How the AI scores yachts"),
  p("The AI is given the charter price (not all-in), specs, equipment, base port, discount details, and mandatory extras. It is instructed to consider:"),
  bullet("Value for money — best specification within budget"),
  bullet("Cabin and berth count relative to the group size"),
  bullet("Year and model quality"),
  bullet("Base port relative to the client's preferred cruising area"),
  bullet("Availability of key equipment (furling genoa, bimini, autopilot, watermaker, dinghy with outboard)"),
  bullet("Early booking or other discounts"),
  spacer(),
  note("The AI receives the charter price range directly from the budget label (e.g. 'budget range: €5k–€7k charter price'). It is explicitly told not to invent other figures. Skipper and crew costs are shown as separate line items in the proposal — not included in the budget comparison.", "info"),
  spacer(160),

  // ── Step 8: Photos ─────────────────────────────────────────────────────────
  h2("Step 8 — Photo Fetch"),
  p("For each AI-selected yacht, the pipeline fetches the full photo gallery from the yacht's booking-manager detail page:"),
  bullet("Up to 8 exterior/interior gallery photos"),
  bullet("The deck plan / layout image (identified by keywords: layout, drawing, plano, plan_, deck, floor)"),
  p("If the gallery fetch fails (network error, no images found), the pipeline falls back to the two thumbnail images returned by the search — so a proposal is always produced even if the gallery is unavailable.", { italic: true, color: C.grey }),
  spacer(160),

  // ── Step 9: WordPress upload ───────────────────────────────────────────────
  h2("Step 9 — WordPress Upload"),
  p("The assembled proposal data is POSTed to the WordPress REST API:"),
  bullet("Creates a new post of type 'proposal' (custom post type)"),
  bullet("Sets all ACF fields: intro HTML, yacht data (prices, specs, extras, photos, deck plan, AI note, recommended flag), itinerary, notes, contact details, WhatsApp link"),
  bullet("Injects skipper / hostess / provisioning service blocks from the lead's crewServices answers"),
  p("The response contains the proposal URL, which is returned to Make.com and sent to the client."),
  spacer(160),

  // ── Failure handling ───────────────────────────────────────────────────────
  h2("Failure Handling"),
  table2([
    ["Failure",                           "Response",                                               C.altRow],
    ["No region or start date in lead",   "HTTPException 500 — ValueError raised before portal call"],
    ["Portal search returns 0 yachts (exact duration)", "status=manual_required, reason=no_live_results. Alert email sent."],
    ["Pro-rated retry also returns 0",    "status=manual_required, reason=no_live_results. Alert email sent."],
    ["0 yachts after all filter relaxation", "status=manual_required, reason=no_matching_yachts. Alert email sent."],
    ["AI returns no valid yacht IDs",     "Falls back to top 5 cheapest from the filtered set (no AI copy — raw data only)"],
    ["WordPress upload fails",            "HTTPException 500. Alert email sent. run_summary email sent with error detail."],
    ["Any other unhandled exception",     "HTTPException 500. Alert email + run_summary sent with full traceback."],
  ]),
  spacer(),
  note("All manual_required and error cases trigger a run_summary email to Chris so every lead is accounted for.", "warn"),
  spacer(160),

  // ── Quick reference ────────────────────────────────────────────────────────
  h2("Quick Reference — Decision Flow"),
  (() => {
    const W = [4680, 4680];
    return new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: W,
      rows: [
        headerRow(["Condition", "Outcome"], W),
        dataRow(["Exact search < 5 results AND non-standard duration", "Retry at 7n/14n + pro-rate prices  (BEFORE filter)"], W, C.altRow),
        dataRow(["Exact search 0 results (after any retry)", "STOP → manual_required"], W),
        dataRow(["Exact filter < 3 yachts", "Run relaxation steps 1–4"], W, C.altRow),
        dataRow(["Relaxation step 1: size ±5ft", "If >= 3 → stop relaxing"], W),
        dataRow(["Relaxation step 2: budget ±2k, original size", "If >= 3 → stop relaxing"], W, C.altRow),
        dataRow(["Relaxation step 3: budget ±4k, size removed", "If >= 3 → stop relaxing"], W),
        dataRow(["Relaxation step 4: budget ±4k, size removed, sail+cat", "If >= 3 → stop relaxing"], W, C.altRow),
        dataRow(["Still 0 after step 4", "STOP → manual_required"], W),
        dataRow(["AI returns no valid IDs", "Fallback: top 5 cheapest, no AI copy"], W, C.altRow),
        dataRow(["Everything succeeds", "Proposal created → URL returned to Make.com"], W),
      ],
    });
  })(),
  spacer(160),

  // ── Key constants ──────────────────────────────────────────────────────────
  h2("Key Constants & Thresholds"),
  table2([
    ["Constant",                "Value",                                                           C.altRow],
    ["MIN_YACHTS_TARGET",       "3  (minimum yachts needed to proceed to AI)"],
    ["PRO_RATE_THRESHOLD",      "5  (if exact search returns fewer than this, and non-standard, retry at std duration)"],
    ["STANDARD_DURATIONS",      "7 nights, 14 nights  (all other durations may trigger pro-rating)"],
    ["PAGINATION_MAX_PAGES",    "30  (1,500 yacht cap per search)"],
    ["PAGINATION_STOP_TRIGGER", "A page that adds 0 new unique yacht IDs (portal cycling detected)"],
    ["RELAXATION_STEPS",        "4  (size ±5ft → budget ±2k → budget ±4k + size removed → + sail/cat)"],
    ["AI_YACHTS_TARGET",        "4–6 yachts selected, 1–2 flagged as recommended"],
    ["PHOTO_MAX",               "8 gallery photos per yacht + 1 deck plan"],
    ["BUDGET_FLOORS",           "Budget filter always includes a floor (e.g. '5-7k' rejects yachts below €5k). Floor relaxes by €4k in steps 3–4."],
  ]),

];

// ── Document ───────────────────────────────────────────────────────────────────
const doc = new Document({
  numbering: {
    config: [
      { reference: "bullets", levels: [
        { level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
        { level: 1, format: LevelFormat.BULLET, text: "\u25E6", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 1080, hanging: 360 } } } },
      ]},
      { reference: "numbers-0", levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
      ]},
    ],
  },
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: C.navy },
        paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: C.teal },
        paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: C.navy },
        paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 } },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 },
      },
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: C.border } },
        spacing: { after: 120 },
        children: [
          new TextRun({ text: "SailScanner  ·  Proposal Pipeline Logic Reference  ·  ", font: "Arial", size: 18, color: "888888" }),
          new TextRun({ text: today, font: "Arial", size: 18, color: "888888" }),
        ],
      })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        children: [
          new TextRun({ text: "Page ", font: "Arial", size: 16, color: "999999" }),
          new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 16, color: "999999" }),
          new TextRun({ text: " of ", font: "Arial", size: 16, color: "999999" }),
          new TextRun({ children: [PageNumber.TOTAL_PAGES], font: "Arial", size: 16, color: "999999" }),
        ],
      })] }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.mkdirSync(path.dirname(path.resolve(outputFile)), { recursive: true });
  fs.writeFileSync(outputFile, buf);
  console.log("Written:", outputFile);
}).catch(err => { console.error(err); process.exit(1); });
