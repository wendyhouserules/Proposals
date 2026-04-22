#!/usr/bin/env node
/**
 * make_test_results_docx.js
 * =========================
 * Reads a JSON results file produced by run_all_tests.py and writes a .docx report.
 *
 * Usage:
 *   node scripts/make_test_results_docx.js <results.json> <output.docx>
 */
"use strict";

const fs   = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  VerticalAlign, LevelFormat, ExternalHyperlink, PageNumber, Header, Footer,
} = require("docx");

// ── Args ───────────────────────────────────────────────────────────────────────
const [,, resultsFile, outputFile] = process.argv;
if (!resultsFile || !outputFile) {
  console.error("Usage: node make_test_results_docx.js <results.json> <output.docx>");
  process.exit(1);
}
const results = JSON.parse(fs.readFileSync(resultsFile, "utf8"));
const today   = new Date().toISOString().slice(0, 10);

// ── Colours ────────────────────────────────────────────────────────────────────
const C = {
  navy:      "1B3A5C",
  teal:      "0F7173",
  lightBlue: "D5E8F0",
  green:     "1D7044",
  greenBg:   "D4EDDA",
  amber:     "856404",
  amberBg:   "FFF3CD",
  red:       "842029",
  redBg:     "F8D7DA",
  headerBg:  "1B3A5C",
  altRow:    "F2F7FB",
  border:    "CCCCCC",
  white:     "FFFFFF",
};

// ── Helpers ────────────────────────────────────────────────────────────────────
const cellBorder = { style: BorderStyle.SINGLE, size: 1, color: C.border };
const allBorders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };

function cell(text, opts = {}) {
  const {
    bold = false, color = "000000", bg = null, align = AlignmentType.LEFT,
    width, font = "Arial", size = 18, italic = false, url = null,
  } = opts;

  const run = url
    ? new ExternalHyperlink({
        children: [new TextRun({ text, bold, color: C.teal, size, font, underline: {} })],
        link: url,
      })
    : new TextRun({ text: String(text || ""), bold, color, size, font, italics: italic });

  return new TableCell({
    borders: allBorders,
    width: width ? { size: width, type: WidthType.DXA } : undefined,
    shading: bg ? { fill: bg, type: ShadingType.CLEAR } : undefined,
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({ alignment: align, children: [run] })],
  });
}

function headerCell(text, width) {
  return new TableCell({
    borders: allBorders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill: C.headerBg, type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      children: [new TextRun({ text, bold: true, color: C.white, size: 18, font: "Arial" })],
    })],
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text, font: "Arial", size: 32, bold: true, color: C.navy })],
    spacing: { before: 240, after: 160 },
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text, font: "Arial", size: 26, bold: true, color: C.teal })],
    spacing: { before: 200, after: 120 },
  });
}

function para(text, opts = {}) {
  const { bold = false, color = "000000", size = 20, spacing = { before: 60, after: 60 } } = opts;
  return new Paragraph({
    spacing,
    children: [new TextRun({ text, bold, color, size, font: "Arial" })],
  });
}

function spacer() {
  return new Paragraph({ children: [new TextRun("")], spacing: { before: 80, after: 80 } });
}

function statusLabel(r) {
  const s = r.status;
  if (s === "ok")              return { label: "✓ OK",       bg: C.greenBg, color: C.green };
  if (s === "manual_required") return { label: "⚠ Manual",  bg: C.amberBg, color: C.amber };
  return                              { label: "✗ Error",    bg: C.redBg,   color: C.red   };
}

// ── Counts ─────────────────────────────────────────────────────────────────────
const ok      = results.filter(r => r.status === "ok");
const manual  = results.filter(r => r.status === "manual_required");
const errors  = results.filter(r => r.status === "error");
const relaxed = ok.filter(r => r.relaxation_applied);
const avgTime = results.length
  ? Math.round(results.reduce((a, r) => a + (r._elapsed || 0), 0) / results.length)
  : 0;

// ── Summary table ──────────────────────────────────────────────────────────────
function summaryTable() {
  const rows = [
    ["Total leads run",         String(results.length)],
    ["✓ Proposals created",     String(ok.length)],
    ["⚠ Manual required",      String(manual.length)],
    ["✗ Errors",                String(errors.length)],
    ["~ Filters relaxed",       String(relaxed.length)],
    ["Avg time per lead",        `${avgTime}s`],
    ["Date run",                 today],
  ];
  return new Table({
    width: { size: 5400, type: WidthType.DXA },
    columnWidths: [3200, 2200],
    rows: rows.map(([label, value], i) =>
      new TableRow({
        children: [
          cell(label, { bold: true, bg: i % 2 === 0 ? C.altRow : C.white, width: 3200 }),
          cell(value, { bg: i % 2 === 0 ? C.altRow : C.white, width: 2200, align: AlignmentType.CENTER }),
        ],
      })
    ),
  });
}

// ── Results table ──────────────────────────────────────────────────────────────
// Columns: Lead | Region | Type | Budget | Portal | Filtered | Relaxation | Selected | Status | Time | Proposal
const COL = [1300, 1100, 900, 900, 700, 700, 1500, 800, 800, 600, 1550];
// Total = 1300+1100+900+900+700+700+1500+800+800+600+1550 = 10850 — use landscape content width

function resultsTable() {
  const headers = [
    "Lead","Region","Type","Budget","Portal","Filtered","Relaxation","Selected","Status","Time","Proposal URL"
  ];

  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) => headerCell(h, COL[i])),
  });

  const dataRows = results.map((r, idx) => {
    const { label, bg, color } = statusLabel(r);
    const rowBg = idx % 2 === 0 ? C.white : C.altRow;
    const url   = r.proposal_url || "";
    const leadName = r._lead_id
      ? r._lead_id.replace(/^test-\d+-/, "").replace(/-/g, " ")
      : "";

    return new TableRow({
      children: [
        cell(leadName,                          { bg: rowBg, width: COL[0], size: 16 }),
        cell(r._region || "",                   { bg: rowBg, width: COL[1], size: 16 }),
        cell(r._boat_type || "",                { bg: rowBg, width: COL[2], size: 16 }),
        cell(r._budget || "",                   { bg: rowBg, width: COL[3], size: 16 }),
        cell(r.portal_total != null ? String(r.portal_total) : "—", { bg: rowBg, width: COL[4], size: 16, align: AlignmentType.CENTER }),
        cell(r.filtered_count != null ? String(r.filtered_count) : "—", { bg: rowBg, width: COL[5], size: 16, align: AlignmentType.CENTER }),
        cell(r.relaxation_applied || "none",    { bg: rowBg, width: COL[6], size: 14, italic: !r.relaxation_applied }),
        cell(r.yachts_selected != null ? `${r.yachts_selected} (${r.yachts_recommended || 0} rec)` : "—", { bg: rowBg, width: COL[7], size: 16, align: AlignmentType.CENTER }),
        cell(label,                             { bg, color, width: COL[8], size: 16, bold: true, align: AlignmentType.CENTER }),
        cell(`${r._elapsed || 0}s`,             { bg: rowBg, width: COL[9], size: 16, align: AlignmentType.CENTER }),
        url
          ? cell("View proposal", { bg: rowBg, width: COL[10], size: 16, url })
          : cell(r.detail || r.reason || "",    { bg: rowBg, width: COL[10], size: 14, color: C.red }),
      ],
    });
  });

  return new Table({
    width: { size: COL.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: COL,
    rows: [headerRow, ...dataRows],
  });
}

// ── Per-lead detail section ────────────────────────────────────────────────────
function detailSection(r) {
  const { label, color } = statusLabel(r);
  const leadTitle = r._lead_id || "Unknown";
  const priceRange = r.filtered_price_range || "—";
  const relaxation = r.relaxation_applied || "none (exact match)";

  const rows = [];

  rows.push(h2(`${leadTitle}  [${label}]`));
  rows.push(para(`${r._name}  ·  ${r._region}  ·  ${r._boat_type || "any"}  ·  ${r._size || "any"}ft  ·  budget: ${r._budget}  ·  ${r._dates}`, { color: "444444" }));
  rows.push(spacer());

  // Mini stats table
  const stats = [
    ["Portal results",    r.portal_total != null ? String(r.portal_total) : "—"],
    ["After filtering",   r.filtered_count != null ? String(r.filtered_count) : "—"],
    ["Price range",       priceRange],
    ["Relaxation",        relaxation],
    ["AI selected",       r.yachts_selected != null ? `${r.yachts_selected} yachts (${r.yachts_recommended || 0} recommended)` : "—"],
    ["Time",              `${r._elapsed || 0}s`],
    ["Status",            label],
  ];
  if (r.proposal_url) stats.push(["Proposal URL", r.proposal_url]);
  if (r.detail || r.reason) stats.push(["Note", r.detail || r.reason || ""]);

  rows.push(new Table({
    width: { size: 7200, type: WidthType.DXA },
    columnWidths: [2400, 4800],
    rows: stats.map(([k, v], i) => {
      const isUrl = k === "Proposal URL" && v.startsWith("http");
      return new TableRow({
        children: [
          cell(k, { bold: true, bg: i % 2 === 0 ? C.altRow : C.white, width: 2400 }),
          isUrl
            ? (() => new TableCell({
                borders: allBorders,
                width: { size: 4800, type: WidthType.DXA },
                shading: { fill: i % 2 === 0 ? C.altRow : C.white, type: ShadingType.CLEAR },
                margins: { top: 80, bottom: 80, left: 120, right: 120 },
                children: [new Paragraph({ children: [new ExternalHyperlink({
                  children: [new TextRun({ text: v, color: C.teal, size: 20, font: "Arial", underline: {} })],
                  link: v,
                })] })],
              }))()
            : cell(v, { bg: i % 2 === 0 ? C.altRow : C.white, width: 4800,
                        color: k === "Status" ? color : "000000",
                        bold: k === "Status" }),
        ],
      });
    }),
  }));

  rows.push(spacer());
  rows.push(new Paragraph({
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: C.border } },
    children: [],
    spacing: { before: 80, after: 80 },
  }));
  rows.push(spacer());

  return rows;
}

// ── Build document ─────────────────────────────────────────────────────────────
const children = [
  h1(`SailScanner — Proposal Pipeline Test Results`),
  para(`Run date: ${today}  ·  ${results.length} leads  ·  Server: http://127.0.0.1:8000`, { color: "666666" }),
  spacer(),
  h2("Summary"),
  summaryTable(),
  spacer(),
  spacer(),
  h2("All Results"),
  resultsTable(),
  new Paragraph({ children: [], pageBreakBefore: true }),
  h2("Per-Lead Detail"),
  ...results.flatMap(detailSection),
];

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 20 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: C.navy },
        paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: C.teal },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 1 } },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 15840, height: 12240 },  // US Letter landscape
        margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 },
        orientation: "landscape",
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          children: [
            new TextRun({ text: "SailScanner Proposal Pipeline  ·  Test Results  ", font: "Arial", size: 18, color: "666666" }),
            new TextRun({ text: today, font: "Arial", size: 18, color: "666666" }),
          ],
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: C.border } },
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [
            new TextRun({ text: "Page ", font: "Arial", size: 16, color: "999999" }),
            new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 16, color: "999999" }),
            new TextRun({ text: " of ", font: "Arial", size: 16, color: "999999" }),
            new TextRun({ children: [PageNumber.TOTAL_PAGES], font: "Arial", size: 16, color: "999999" }),
          ],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.mkdirSync(path.dirname(outputFile), { recursive: true });
  fs.writeFileSync(outputFile, buf);
  console.log(`Written: ${outputFile}`);
}).catch(err => {
  console.error("Error generating docx:", err);
  process.exit(1);
});
