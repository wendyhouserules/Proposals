#!/usr/bin/env python3
"""
SailScanner Email Block Builder

Reads Booking Manager HTML export(s) and outputs a SailScanner-branded HTML snippet
for email templates. It:
- Uses both yacht images side by side
- Includes a button linking to the yacht's 'more info' page
- Lists charter price, mandatory extras (advance + at base), and a bold total in SailScanner blue
- Shows equipment as small blue pills/tags
- Includes security deposit, check-in and check-out times, and licence required

Usage:
  python build_email_block.py --input /path/to/file.html [--input another.html] > email_snippet.html

Python: 3.11+
Dependencies: beautifulsoup4
  pip install beautifulsoup4
"""
from __future__ import annotations

import argparse
import html
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from datetime import datetime
from typing import Iterable, List, Optional, Tuple

from bs4 import BeautifulSoup

SAILSCANNER_BLUE = "#12305c"
SECTION_SEPARATOR = '<p style="margin:20px">&nbsp;</p>'


@dataclass
class Money:
    amount: Decimal
    currency: str

    def format(self) -> str:
        quantized = self.amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        # Format with thousands separator and two decimals (e.g., 3,392.50 €)
        parts = f"{quantized:,.2f}"
        return f"{parts} {self.currency}".strip()

    @staticmethod
    def zero(currency: str = "€") -> "Money":
        return Money(Decimal("0.00"), currency)

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError("Currency mismatch")
        return Money(self.amount + other.amount, self.currency)


def parse_money(text: str, default_currency: str = "€") -> Money:
    if not text:
        return Money.zero(default_currency)
    t = text.strip()
    # Extract currency (assume symbol present or fallback)
    currency_match = re.search(r"(€|EUR|£|GBP|\$|USD)", t)
    currency = currency_match.group(1) if currency_match else default_currency
    # Remove currency, spaces, and standard thousand separators
    cleaned = re.sub(r"[^\d,.\-]", "", t)
    # Convert European "1.234,56" or "1,234.56" to Decimal
    if cleaned.count(",") == 1 and cleaned.count(".") >= 1 and cleaned.rfind(",") > cleaned.rfind("."):
        # Likely "1.234,56" -> remove thousand dots, replace comma with dot
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        # Remove thousand separators (commas)
        cleaned = cleaned.replace(",", "")
    try:
        return Money(Decimal(cleaned), currency)
    except (InvalidOperation, ValueError):
        return Money.zero(currency)


def text_of(el) -> str:
    if not el:
        return ""
    return " ".join(el.get_text(separator=" ", strip=True).split())


def find_first(soup: BeautifulSoup, name: str, **kwargs):
    found = soup.find_all(name, **kwargs)
    return found[0] if found else None

def is_mostly_uppercase(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    upper = sum(1 for c in letters if c.isupper())
    return (upper / len(letters)) >= 0.8

def to_sentence_case(text: str) -> str:
    if not text:
        return text
    lowered = text.lower()
    chars = list(lowered)
    for i, ch in enumerate(chars):
        if ch.isalpha():
            chars[i] = ch.upper()
            break
    return "".join(chars)


def split_sections(html_text: str) -> List[str]:
    # Normalize for exact known separator
    parts = html_text.split(SECTION_SEPARATOR)
    # The export often includes content after the last separator; keep all non-empty segments
    return [p for p in parts if BeautifulSoup(p, "html.parser").find(True)]


@dataclass
class YachtEntry:
    name: str
    boat_type: Optional[str]
    model: Optional[str]
    charter_type: Optional[str]
    image_urls: List[str]
    more_info_url: Optional[str]
    base_price: Optional[Money]
    discount_items: List[Tuple[str, Money]]
    charter_price_net: Money
    mandatory_advance_items: List[Tuple[str, Money]]
    mandatory_base_items: List[Tuple[str, Money]]
    optional_extra_items: List[Tuple[str, Money]]
    deposit: Optional[Money]
    check_in_time: Optional[str]
    check_out_time: Optional[str]
    licence_required: Optional[str]
    equipment_tags: List[str]
    year: Optional[str]
    length: Optional[str]
    berths: Optional[str]
    cabins: Optional[str]
    wc_shower: Optional[str]
    mainsail: Optional[str]
    base_location: Optional[str]
    date_from_str: Optional[str]
    date_to_str: Optional[str]

    @property
    def mandatory_extras_total(self) -> Money:
        currency = self.charter_price_net.currency or "€"
        total = Money.zero(currency)
        for _, m in self.mandatory_advance_items:
            total = total + m
        for _, m in self.mandatory_base_items:
            total = total + m
        return total

    @property
    def grand_total(self) -> Money:
        return self.charter_price_net + self.mandatory_extras_total


def parse_yacht_section(section_html: str) -> YachtEntry:
    soup = BeautifulSoup(section_html, "html.parser")

    def td_text_equals(td, target: str) -> bool:
        return td and isinstance(target, str) and text_of(td).strip().lower() == target.strip().lower()

    # Name: try the big bold title cell first
    name_td = soup.find(
        "td",
        attrs={"style": re.compile(r"font-size:\s*26px;.*font-weight:\s*bold;", re.I)},
    )
    name_text = text_of(name_td)

    # Type / Model / Charter type from three-col block
    three_col = soup.find("div", attrs={"class": "three-col"})
    boat_type = model = charter_type = None
    if three_col:
        ps = three_col.find_all("p")
        if len(ps) >= 1:
            boat_type = text_of(ps[0])
        if len(ps) >= 2:
            model = text_of(ps[1])
        if len(ps) >= 3:
            charter_type = text_of(ps[2])

    if not name_text:
        # Fallback to model
        name_text = model or "Yacht"
    else:
        # If the detected name is unhelpful (pure number or number-word), prefer model as title
        number_words = (
            r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
            r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty"
        )
        if re.fullmatch(rf"(?i)\s*({number_words}|\d+)\s*", name_text or ""):
            if model:
                name_text = model

    # Images: find two 310px images inside an images two-col block; ensure valid URLs
    image_urls: List[str] = []
    for images_block in soup.find_all("div", attrs={"class": "two-col"}):
        imgs = images_block.find_all("img")
        candidate_urls: List[str] = []
        for img in imgs:
            src = (img.get("src") or "").strip()
            width = (img.get("width") or "").strip()
            if not src or "$" in src:
                continue
            if not src.startswith("http"):
                continue
            if "booking-manager.com" not in src:
                continue
            if width == "310" or "documents/image.jpg" in src:
                candidate_urls.append(src)
        if len(candidate_urls) >= 2:
            image_urls = candidate_urls[:2]
            break
    if len(image_urls) == 0:
        # Fallback to first two http images in the section
        for img in soup.find_all("img"):
            src = (img.get("src") or "").strip()
            if src and src.startswith("http") and "booking-manager.com" in src and "$" not in src:
                image_urls.append(src)
            if len(image_urls) >= 2:
                break
    if len(image_urls) == 1:
        image_urls.append(image_urls[0])

    # More info link: anchor containing 'more info'
    more_info_url: Optional[str] = None
    for a in soup.find_all("a"):
        if "more info" in text_of(a).lower():
            more_info_url = a.get("href")
            break

    # Prices: base price (Price), discounts (Discount ...), and net (Price:)
    base_price: Optional[Money] = None
    discount_items: List[Tuple[str, Money]] = []
    charter_price_net = Money.zero()
    def parse_price_table(tbl) -> bool:
        nonlocal base_price, discount_items, charter_price_net
        # Strategy:
        # - Prefer a table that contains a "Price:" (net) row.
        # - If both "Price" and "Price:" exist, treat every intermediate 2-col row as a discount item.
        # - If only "Price:" exists, capture net price and skip discounts.
        rows = [tr for tr in tbl.find_all("tr")]
        if not rows:
            return False
        idx_price = -1
        idx_net = -1
        # Determine indices of "Price" and "Price:" rows
        for i, tr in enumerate(rows):
            tds = tr.find_all("td")
            if len(tds) != 2:
                continue
            left_text = text_of(tds[0]).strip().lower()
            if left_text == "price" and idx_price == -1:
                idx_price = i
            elif left_text == "price:" and idx_net == -1:
                idx_net = i
        if idx_net == -1:
            return False  # no net price in this table
        # Parse net price
        net_tds = rows[idx_net].find_all("td")
        charter_price_net = parse_money(text_of(net_tds[1]))
        # Parse base price and discounts if an initial "Price" exists
        if idx_price != -1 and idx_price < idx_net:
            base_tds = rows[idx_price].find_all("td")
            base_price = parse_money(text_of(base_tds[1]))
            discount_items.clear()
            for tr in rows[idx_price + 1 : idx_net]:
                tds = tr.find_all("td")
                if len(tds) != 2:
                    continue
                left_text_raw = text_of(tds[0])
                right_text = text_of(tds[1])
                discount_items.append((left_text_raw, parse_money(right_text)))
        return charter_price_net.amount > 0
    for table in soup.find_all("table"):
        if parse_price_table(table):
            break

    # Extras - Payable in advance
    mandatory_advance_items: List[Tuple[str, Money]] = []
    for table in soup.find_all("table"):
        header_row = table.find("tr")
        if not header_row:
            continue
        header_tds = header_row.find_all("td")
        if not header_tds:
            continue
        if not td_text_equals(header_tds[0], "Payable in advance:"):
            continue
        for tr in table.find_all("tr")[1:]:
            tds = tr.find_all("td")
            if len(tds) != 2:
                continue
            label = text_of(tds[0])
            if not label or "total" in label.lower():
                continue
            amount = parse_money(text_of(tds[1]), charter_price_net.currency)
            if amount.amount > 0:
                mandatory_advance_items.append((label, amount))
        break

    # Extras - Payable at base
    mandatory_base_items: List[Tuple[str, Money]] = []
    for table in soup.find_all("table"):
        header_row = table.find("tr")
        if not header_row:
            continue
        header_tds = header_row.find_all("td")
        if not header_tds:
            continue
        if not td_text_equals(header_tds[0], "Payable at base:"):
            continue
        for tr in table.find_all("tr")[1:]:
            tds = tr.find_all("td")
            if len(tds) != 2:
                continue
            label = text_of(tds[0])
            if not label or "total" in label.lower():
                continue
            amount = parse_money(text_of(tds[1]), charter_price_net.currency)
            if amount.amount > 0:
                mandatory_base_items.append((label, amount))
        break

    # Extras - Optional extras
    optional_extra_items: List[Tuple[str, Money]] = []
    for table in soup.find_all("table"):
        header_row = table.find("tr")
        if not header_row:
            continue
        header_tds = header_row.find_all("td")
        if not header_tds:
            continue
        if not td_text_equals(header_tds[0], "Optional extras:"):
            continue
        for tr in table.find_all("tr")[1:]:
            tds = tr.find_all("td")
            if len(tds) != 2:
                continue
            label = text_of(tds[0])
            if not label or "total" in label.lower():
                continue
            amount = parse_money(text_of(tds[1]), charter_price_net.currency)
            if amount.amount > 0:
                optional_extra_items.append((label, amount))
        break

    # Deposit
    deposit: Optional[Money] = None
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) != 2:
                continue
            if "security deposit" in text_of(tds[0]).lower():
                deposit = parse_money(text_of(tds[1]), charter_price_net.currency)
                break
        if deposit:
            break

    # Dates, base location, and check-in/out times
    base_location: Optional[str] = None
    date_from_str: Optional[str] = None
    date_to_str: Optional[str] = None
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None

    def format_date_label(raw: str) -> str:
        months = {
            "jan": "January", "feb": "February", "mar": "March", "apr": "April",
            "may": "May", "jun": "June", "jul": "July", "aug": "August",
            "sep": "September", "oct": "October", "nov": "November", "dec": "December",
        }
        m = re.match(r"([A-Za-z]{3})\s+(\d{1,2}),\s*(\d{4})", raw.strip())
        if not m:
            return raw.strip()
        mon = months.get(m.group(1).lower(), m.group(1))
        day = m.group(2)
        year = m.group(3)
        return f"{day} {mon} {year}"

    def extract_from_to_block(four_col_div) -> None:
        nonlocal base_location, date_from_str, date_to_str, check_in_time, check_out_time
        columns = four_col_div.find_all("div", attrs={"class": "column"})
        if len(columns) < 2:
            return
        # Helper to find the detail table that contains the "From" or "to" label (not the calendar box)
        def find_detail_table(col, keyword: str):
            for tbl in col.find_all("table"):
                if keyword.lower() in text_of(tbl).lower():
                    # Ensure the first meaningful row has keyword
                    trs = tbl.find_all("tr")
                    for tr in trs[:2]:
                        if keyword.lower() == text_of(tr).strip().lower():
                            return tbl
            return None
        from_table = find_detail_table(columns[0], "From")
        to_table = find_detail_table(columns[1], "to")
        # Parse base location and start date/time from "From" table
        if from_table:
            trs = [tr for tr in from_table.find_all("tr")]
            # Expected order within this table:
            # 0: "From" label
            # 1: Country
            # 2: Marina
            # 3: Date and bold time labels
            if len(trs) >= 3:
                country_td = trs[1].find("td") if trs[1].find("td") else None
                marina_td = trs[2].find("td") if trs[2].find("td") else None
                country = text_of(country_td) if country_td else ""
                marina = text_of(marina_td) if marina_td else ""
                if country or marina:
                    base_location = ", ".join([p for p in [country, marina] if p])
            # Date and time labels
            labels = from_table.find_all("label")
            for lab in labels:
                style = (lab.get("style") or "").lower().replace(" ", "")
                if "font-weight:bold" in style:
                    check_in_time = text_of(lab).replace("\u00a0", " ").strip()
                else:
                    date_from_str = format_date_label(text_of(lab))
        # Parse end date/time from "to" table
        if to_table:
            labels = to_table.find_all("label")
            for lab in labels:
                style = (lab.get("style") or "").lower().replace(" ", "")
                if "font-weight:bold" in style:
                    check_out_time = text_of(lab).replace("\u00a0", " ").strip()
                else:
                    date_to_str = format_date_label(text_of(lab))

    for four_col in soup.find_all("div", attrs={"class": "four-col"}):
        if "from" in text_of(four_col).lower() and "to" in text_of(four_col).lower():
            extract_from_to_block(four_col)
            break

    # Licence required
    licence_required: Optional[str] = None
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        bold = tds[0].find("b")
        if bold and "skipper licence required" in text_of(bold).lower():
            td_text = text_of(tds[0])
            # Extract text after the bold if present
            m = re.search(r"Skipper licence required\s*:?\s*(.*)$", td_text, re.I)
            licence_required = (m.group(1).strip() if m else "Yes") or "Yes"
            break

    # Equipment tags: strictly from the "Equipment:" table
    equipment_tags: List[str] = []
    for table in soup.find_all("table"):
        header_row = table.find("tr")
        if not header_row:
            continue
        header_td = header_row.find("td")
        if not td_text_equals(header_td, "Equipment:"):
            continue
        for tr in table.find_all("tr")[1:]:
            td = find_first(tr, "td")
            if not td:
                continue
            text = text_of(td)
            if ":" in text:
                text = text.split(":", 1)[1].strip()
            for piece in text.split(","):
                tag = piece.strip(" ,")
                if tag:
                    equipment_tags.append(tag)
        break

    # Yacht specs: parse from six-col
    year = length = berths = cabins = wc_shower = mainsail = None
    six_col = soup.find("div", attrs={"class": "six-col"})
    if six_col:
        cols = six_col.find_all("div", attrs={"class": "column"})
        def val_from(col) -> Optional[str]:
            ps = col.find_all("p")
            return text_of(ps[0]) if ps else None
        if len(cols) >= 1:
            year = val_from(cols[0])
        if len(cols) >= 2:
            length = val_from(cols[1])
        if len(cols) >= 3:
            berths = val_from(cols[2])
        if len(cols) >= 4:
            cabins = val_from(cols[3])
        if len(cols) >= 5:
            wc_shower = val_from(cols[4])
        if len(cols) >= 6:
            mainsail = val_from(cols[5])

    return YachtEntry(
        name=name_text,
        boat_type=boat_type,
        model=model,
        charter_type=charter_type,
        image_urls=image_urls,
        more_info_url=more_info_url,
        base_price=base_price,
        discount_items=discount_items,
        charter_price_net=charter_price_net,
        mandatory_advance_items=mandatory_advance_items,
        mandatory_base_items=mandatory_base_items,
        optional_extra_items=optional_extra_items,
        deposit=deposit,
        check_in_time=check_in_time,
        check_out_time=check_out_time,
        licence_required=licence_required,
        equipment_tags=equipment_tags,
        year=year,
        length=length,
        berths=berths,
        cabins=cabins,
        wc_shower=wc_shower,
        mainsail=mainsail,
        base_location=base_location,
        date_from_str=date_from_str,
        date_to_str=date_to_str,
    )


def build_equipment_pills(tags: Iterable[str]) -> str:
    pills = []
    for tag in tags:
        pills.append(
            f'<span style="display:inline-block;background:{SAILSCANNER_BLUE};color:#ffffff;'
            f'font-size:12px;line-height:1;border-radius:999px;padding:6px 10px;margin:4px 6px 0 0;">'
            f'{html.escape(tag)}</span>'
        )
    return "".join(pills)


def render_yacht_block(y: YachtEntry) -> str:
    # Images
    left_img = html.escape(y.image_urls[0]) if y.image_urls else ""
    right_img = html.escape(y.image_urls[1]) if len(y.image_urls) > 1 else left_img
    more_info_btn = (
        f'<a href="{html.escape(y.more_info_url)}" '
        f'style="background:{SAILSCANNER_BLUE};color:#ffffff;text-decoration:none;'
        f'display:inline-block;padding:12px 16px;border-radius:4px;font-weight:bold;text-transform:uppercase;">'
        f'See more</a>'
        if y.more_info_url
        else ""
    )
    full_width_btn = ""
    if y.more_info_url:
        full_width_btn = (
            f'<a href="{html.escape(y.more_info_url)}" '
            f'style="background:{SAILSCANNER_BLUE};color:#ffffff;text-decoration:none;font-family:Arial, sans-serif;'
            f'display:block;padding:10px 12px;border-radius:4px;font-weight:600;'
            f'text-transform:none;text-align:center;font-size:13px;">More info about this yacht</a>'
        )

    # Price rows
    def render_price_rows() -> str:
        rows: List[str] = []
        if y.base_price:
            rows.append(
                f"<tr><td style='text-align:left;padding:4px 0;'>Price</td>"
                f"<td style='text-align:right;padding:4px 0;white-space:nowrap;'>{y.base_price.format()}</td></tr>"
            )
        for label, amt in y.discount_items:
            rows.append(
                f"<tr><td style='text-align:left;padding:4px 0;color:#374151'>{html.escape(label)}</td>"
                f"<td style='text-align:right;padding:4px 0;white-space:nowrap;color:#374151'>{amt.format()}</td></tr>"
            )
        rows.append(
            f"<tr><td style='text-align:left;padding:6px 0;font-weight:bold;border-top:1px solid #e5e7eb;color:{SAILSCANNER_BLUE};'>Charter price</td>"
            f"<td style='text-align:right;padding:6px 0;white-space:nowrap;font-weight:bold;border-top:1px solid #e5e7eb;color:{SAILSCANNER_BLUE};'>{y.charter_price_net.format()}</td></tr>"
        )
        return "".join(rows)

    # Mandatory extras lists
    def render_items(title: str, items: List[Tuple[str, Money]]) -> str:
        if not items:
            return ""
        rows = "".join(
            f"<tr><td style='text-align:left;padding:4px 0;'>{html.escape(to_sentence_case(label) if is_mostly_uppercase(label) else label)}</td>"
            f"<td style='text-align:right;padding:4px 0;white-space:nowrap;'>{amt.format()}</td></tr>"
            for label, amt in items
        )
        return (
            f"<tr><td colspan='2' style='font-weight:bold;padding-top:8px;color:{SAILSCANNER_BLUE};'>{html.escape(title)}:</td></tr>"
            f"{rows}"
        )

    equip_pills = build_equipment_pills(y.equipment_tags)

    total_html = (
        f"<span style='font-weight:bold;color:{SAILSCANNER_BLUE};'>{y.grand_total.format()}</span>"
    )

    # Title and subtitle construction: prefer model as the title; avoid duplicating model in subtitle
    use_model_as_title = bool(y.model and y.model.strip())
    title_text = (y.model or "").strip() if use_model_as_title else (y.name or "").strip()
    subtitle_parts = [p for p in [y.boat_type, (None if use_model_as_title else y.model), y.charter_type] if p]
    subtitle = " · ".join(subtitle_parts)

    # Specs quick-look: two rows (3 + 3), centered text
    def spec_cell(label: str, value: Optional[str]) -> str:
        val = html.escape(value) if value else "-"
        return (
            f"<td style='padding:8px 10px;border:0;vertical-align:top;font-family:Arial, sans-serif;text-align:center;'>"
            f"<div style='font-size:11px;color:#6b7280;text-transform:uppercase'>{label}</div>"
            f"<div style='font-size:13px;color:{SAILSCANNER_BLUE};font-weight:bold'>{val}</div>"
            f"</td>"
        )
    specs_html = (
        "<div style='margin-top:10px;margin-bottom:12px;padding:10px 12px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px'>"
        "<table role='presentation' cellpadding='0' cellspacing='0' style='border-collapse:collapse;width:100%'>"
        "<tr>"
        f"{spec_cell('Year', y.year)}"
        f"{spec_cell('Length', y.length)}"
        f"{spec_cell('Berths', y.berths)}"
        "</tr>"
        "<tr><td colspan='3' style='height:1px;line-height:1px;background:#e5e7eb;padding:0;margin:0'></td></tr>"
        "<tr>"
        f"{spec_cell('Cabins', y.cabins)}"
        f"{spec_cell('WC / Shower', y.wc_shower)}"
        f"{spec_cell('Mainsail', y.mainsail)}"
        "</tr>"
        "</table>"
        "</div>"
    )

    base_line = f"Base: <strong>{html.escape(y.base_location)}</strong>" if y.base_location else ""
    dates_line = ""
    if y.date_from_str or y.date_to_str or y.check_in_time or y.check_out_time:
        left = ", ".join([p for p in [y.date_from_str, y.check_in_time] if p])
        right = ", ".join([p for p in [y.date_to_str, y.check_out_time] if p])
        dates_line = f"Dates: <strong>{html.escape(left)}</strong> to <strong>{html.escape(right)}</strong>"
    base_dates_html = ""
    if base_line or dates_line:
        base_dates_html = (
            "<div style='margin:8px 0 12px 0;padding:8px 10px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px'>"
            f"<div style='font-family:Arial, sans-serif;font-size:13px;color:{SAILSCANNER_BLUE};margin-bottom:4px'>{base_line}</div>"
            f"<div style='font-family:Arial, sans-serif;font-size:13px;color:{SAILSCANNER_BLUE};'>{dates_line}</div>"
            "</div>"
        )

    return f"""
<!-- SailScanner Yacht Block -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:0 0 24px 0;">
  <tr>
    <td style="padding:16px 0;border-top:1px solid #e5e7eb">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="font-family:Arial, sans-serif;font-size:18px;line-height:24px;font-weight:bold;color:{SAILSCANNER_BLUE};">
            {html.escape(title_text)}
          </td>
        </tr>
        {"<tr><td style='font-family:Arial, sans-serif;font-size:13px;color:#374151;padding-top:2px'>" + html.escape(subtitle) + "</td></tr>" if subtitle else ""}
        {"<tr><td>" + specs_html + "</td></tr>"}
        {"<tr><td>" + base_dates_html + "</td></tr>" if base_dates_html else ""}
        <tr>
          <td style="padding-top:12px">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="width:50%;padding-right:6px"><img src="{left_img}" alt="" width="100%" style="display:block;width:100%;height:auto;border-radius:4px" /></td>
                <td style="width:50%;padding-left:6px"><img src="{right_img}" alt="" width="100%" style="display:block;width:100%;height:auto;border-radius:4px" /></td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding-top:12px">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-family:Arial, sans-serif;font-size:14px;color:#111827;">
              <tr>
                <td style="vertical-align:top;padding-right:12px;width:60%;">
                  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                    <tr><td colspan="2" style="padding-top:8px;font-family:Arial, sans-serif;font-size:12px;color:{SAILSCANNER_BLUE};font-weight:bold">Price</td></tr>
                    {render_price_rows()}
                    {render_items("Mandatory extras", y.mandatory_advance_items + y.mandatory_base_items)}
                    <tr>
                      <td style="text-align:left;padding:8px 0;font-weight:bold;color:{SAILSCANNER_BLUE};">Total</td>
                      <td style="text-align:right;padding:8px 0;">{total_html}</td>
                    </tr>
                    {render_items("Optional extras", y.optional_extra_items)}
                    {"<tr><td colspan='2' style='text-align:left;padding:4px 0;color:#6b7280'>Security deposit: " + (y.deposit.format() if y.deposit else "-") + "</td></tr>"}
                  </table>
                </td>
                <td style="vertical-align:top;padding-left:12px;width:40%;">
                  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-family:Arial, sans-serif;font-size:14px;color:#111827;">
                    <tr><td style="padding-top:8px;font-family:Arial, sans-serif;font-size:12px;color:{SAILSCANNER_BLUE};font-weight:bold">Other details</td></tr>
                    {"<tr><td style='padding:4px 0'>Check-in: " + (html.escape(y.check_in_time) if y.check_in_time else "-") + "</td></tr>"}
                    {"<tr><td style='padding:4px 0'>Check-out: " + (html.escape(y.check_out_time) if y.check_out_time else "-") + "</td></tr>"}
                    {"<tr><td style='padding:4px 0'>Licence required: " + (html.escape(y.licence_required) if y.licence_required else "Yes") + "</td></tr>"}
                    {("<tr><td style='padding-top:8px;font-family:Arial, sans-serif;font-size:12px;color:" + SAILSCANNER_BLUE + ";font-weight:bold'>Equipment</td></tr>" + "<tr><td style='padding-top:6px'>" + equip_pills + "</td></tr>") if equip_pills else ""}
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        {"<tr><td style='padding-top:14px'>" + full_width_btn + "</td></tr>" if full_width_btn else ""}
      </table>
    </td>
  </tr>
</table>
""".strip()


def render_all(yachts: List[YachtEntry]) -> str:
    blocks = [render_yacht_block(y) for y in yachts]
    # Wrap in container for easy paste
    return f"""<!-- BEGIN SailScanner Yachts -->
<div style="width:96%;max-width:620px;margin:0 auto;padding:0;">
{''.join(blocks)}
</div>
<!-- END SailScanner Yachts -->"""


def parse_file(path: Path) -> List[YachtEntry]:
    content = path.read_text(encoding="utf-8", errors="ignore")
    sections = split_sections(content)
    yachts: List[YachtEntry] = []
    for section in sections:
        try:
            yachts.append(parse_yacht_section(section))
        except Exception:
            # Skip malformed section but continue
            continue
    return yachts


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Build SailScanner email HTML block from Booking Manager HTML exports.")
    parser.add_argument(
        "--input",
        "-i",
        dest="inputs",
        action="append",
        required=True,
        help="Path to an HTML export file. Can be used multiple times.",
    )
    args = parser.parse_args(argv)

    all_entries: List[YachtEntry] = []
    for p in args.inputs:
        path = Path(p).expanduser()
        if not path.exists():
            continue
        all_entries.extend(parse_file(path))
    # Drop entries where we failed to parse a net charter price
    all_entries = [y for y in all_entries if y.charter_price_net.amount > 0]
    # Deduplicate by (name, model/make, net price, base)
    def norm(s: Optional[str]) -> str:
        return re.sub(r"\s+", " ", (s or "").strip()).lower()
    seen_keys = set()
    deduped: List[YachtEntry] = []
    for y in all_entries:
        key = (
            norm(y.name),
            norm(y.model or ""),
            str(y.charter_price_net.amount),
            y.charter_price_net.currency,
            norm(y.base_location or ""),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(y)

    html_out = render_all(deduped)
    stem = Path(args.inputs[0]).stem if len(args.inputs) == 1 else "combined"
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-")
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    out_name = f"email_snippet-{safe_stem}-{ts}.html"
    Path(out_name).write_text(html_out, encoding="utf-8")
    print(out_name)


if __name__ == "__main__":
    main()


