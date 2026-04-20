#!/usr/bin/env python3
"""
SailScanner Email Block Builder (Skippered)

Generates a SailScanner-branded HTML snippet from Booking Manager HTML export(s),
including a skipper cost in the breakdown and changing listings from Bareboat to Skippered.

Usage:
  python build_email_block_skippered.py --input /path/to/file.html [--input another.html] > email_snippet.html

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
DEFAULT_SKIPPER_PRICE = Decimal("1500.00")


@dataclass
class Money:
    amount: Decimal
    currency: str

    def format(self) -> str:
        quantized = self.amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
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
    currency_match = re.search(r"(€|EUR|£|GBP|\$|USD)", t)
    currency = currency_match.group(1) if currency_match else default_currency
    cleaned = re.sub(r"[^\d,.\-]", "", t)
    if cleaned.count(",") == 1 and cleaned.count(".") >= 1 and cleaned.rfind(",") > cleaned.rfind("."):
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
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


def split_sections(html_text: str) -> List[str]:
    parts = html_text.split(SECTION_SEPARATOR)
    return [p for p in parts if BeautifulSoup(p, "html.parser").find(True)]

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
    # Capitalize first alphabetic character only
    chars = list(lowered)
    for i, ch in enumerate(chars):
        if ch.isalpha():
            chars[i] = ch.upper()
            break
    return "".join(chars)


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
    mandatory_advance_items: List[Tuple[str, Any]]
    mandatory_base_items: List[Tuple[str, Any]]
    optional_items: List[Tuple[str, Any]]
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
    to_location: Optional[str]
    date_from_str: Optional[str]
    date_to_str: Optional[str]

    @property
    def mandatory_extras_total(self) -> Money:
        currency = self.charter_price_net.currency or "€"
        total = Money.zero(currency)
        for _, m in self.mandatory_advance_items:
            if hasattr(m, "amount"):
                total = total + m
        for _, m in self.mandatory_base_items:
            if hasattr(m, "amount"):
                total = total + m
        return total

    @property
    def grand_total(self) -> Money:
        return self.charter_price_net + self.mandatory_extras_total


def parse_yacht_section(section_html: str) -> YachtEntry:
    soup = BeautifulSoup(section_html, "html.parser")

    def td_text_equals(td, target: str) -> bool:
        return td and isinstance(target, str) and text_of(td).strip().lower() == target.strip().lower()

    name_td = soup.find(
        "td",
        attrs={"style": re.compile(r"font-size:\s*26px;.*font-weight:\s*bold;", re.I)},
    )
    name_text = text_of(name_td)

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
            if charter_type and "bareboat" in charter_type.lower():
                charter_type = "Skippered"
        elif not charter_type:
            charter_type = "Skippered"
    else:
        charter_type = "Skippered"

    if not name_text:
        name_text = model or "Yacht"
    else:
        number_words = (
            r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
            r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty"
        )
        if re.fullmatch(rf"(?i)\s*({number_words}|\d+)\s*", name_text or ""):
            if model:
                name_text = model

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
        for img in soup.find_all("img"):
            src = (img.get("src") or "").strip()
            if src and src.startswith("http") and "booking-manager.com" in src and "$" not in src:
                image_urls.append(src)
            if len(image_urls) >= 2:
                break
    if len(image_urls) == 1:
        image_urls.append(image_urls[0])

    more_info_url: Optional[str] = None
    for a in soup.find_all("a"):
        if "more info" in text_of(a).lower():
            more_info_url = a.get("href")
            break

    base_price: Optional[Money] = None
    discount_items: List[Tuple[str, Money]] = []
    charter_price_net = Money.zero()

    def parse_price_table(tbl) -> bool:
        nonlocal base_price, discount_items, charter_price_net
        found_any = False
        for tr in tbl.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) != 2:
                continue
            left_text = text_of(tds[0]).strip()
            right_text = text_of(tds[1]).strip()
            left_lc = left_text.lower()
            if left_lc == "price":
                base_price = parse_money(right_text)
                found_any = True
                continue
            if left_lc == "price:":
                charter_price_net = parse_money(right_text)
                found_any = True
                continue
            if left_lc.startswith("discount"):
                discount_items.append((left_text, parse_money(right_text)))
                found_any = True
                continue
            # Only treat as a monetary value if a currency symbol is present.
            # Without this guard, strings like "Price Quote (GMM-Yachting) 3 / 10"
            # are incorrectly parsed as -310 € (the "-" from "GMM-Yachting" + "310"
            # from the pagination fraction "3 / 10").
            if re.search(r"(€|EUR|£|GBP|\$|USD)", right_text, re.I):
                amt = parse_money(right_text)
                if amt.amount < 0:
                    discount_items.append((left_text or "Discount", amt))
                    found_any = True
        return found_any

    for table in soup.find_all("table"):
        if parse_price_table(table):
            break
    # Deduplicate discounts by label+amount+currency to avoid repeated entries from noisy tables
    if discount_items:
        unique_discounts: List[Tuple[str, Money]] = []
        seen_keys = set()
        for lbl, amt in discount_items:
            key = (lbl.strip().lower(), str(amt.amount), amt.currency)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            unique_discounts.append((lbl, amt))
        discount_items = unique_discounts

    def _parse_amt(raw: str, currency: str) -> Any:
        """Return a Money if the text has a numeric currency value, else a display string."""
        rl = raw.lower()
        if re.search(r"(€|eur|£|gbp|\$|usd)", raw, re.I):
            m = parse_money(raw, currency)
            if m.amount > 0:
                return m
        if "included" in rl:
            return "Included"
        if "upon request" in rl or "on request" in rl:
            return "Price on request"
        return None

    # Extras - Payable in advance
    mandatory_advance_items: List[Tuple[str, Any]] = []
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
            amt = _parse_amt(text_of(tds[1]), charter_price_net.currency)
            if amt is not None:
                mandatory_advance_items.append((label, amt))
        break

    # Extras - Payable at base
    mandatory_base_items: List[Tuple[str, Any]] = []
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
            amt = _parse_amt(text_of(tds[1]), charter_price_net.currency)
            if amt is not None:
                mandatory_base_items.append((label, amt))
        break

    # Destination and dates/times
    base_location: Optional[str] = None
    to_location: Optional[str] = None
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
        nonlocal base_location, to_location, date_from_str, date_to_str, check_in_time, check_out_time
        columns = four_col_div.find_all("div", attrs={"class": "column"})
        if len(columns) < 2:
            return

        def find_detail_table(col, keyword: str):
            for tbl in col.find_all("table"):
                if keyword.lower() in text_of(tbl).lower():
                    trs = tbl.find_all("tr")
                    for tr in trs[:2]:
                        if keyword.lower() == text_of(tr).strip().lower():
                            return tbl
            return None

        from_table = find_detail_table(columns[0], "From")
        to_table = find_detail_table(columns[1], "to")
        if from_table:
            trs = [tr for tr in from_table.find_all("tr")]
            if len(trs) >= 3:
                country_td = trs[1].find("td") if trs[1].find("td") else None
                marina_td = trs[2].find("td") if trs[2].find("td") else None
                country = text_of(country_td) if country_td else ""
                marina = text_of(marina_td) if marina_td else ""
                if country or marina:
                    base_location = ", ".join([p for p in [country, marina] if p])
            labels = from_table.find_all("label")
            for lab in labels:
                style = (lab.get("style") or "").lower().replace(" ", "")
                if "font-weight:bold" in style:
                    check_in_time = text_of(lab).replace("\u00a0", " ").strip()
                else:
                    date_from_str = format_date_label(text_of(lab))
        if to_table:
            trs_to = [tr for tr in to_table.find_all("tr")]
            if len(trs_to) >= 3:
                country_td_to = trs_to[1].find("td") if trs_to[1].find("td") else None
                marina_td_to = trs_to[2].find("td") if trs_to[2].find("td") else None
                country_to = text_of(country_td_to) if country_td_to else ""
                marina_to = text_of(marina_td_to) if marina_td_to else ""
                if country_to or marina_to:
                    to_location = ", ".join([p for p in [country_to, marina_to] if p])
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

    # Optional extras: capture ALL items (including text-valued ones).
    # Email-specific display filtering (crewed/skipper) happens in render_yacht_block().
    def normalize_label(label: str) -> str:
        return re.sub(r"\s+", " ", (label or "").strip().lower())
    mandatory_label_norms = {
        normalize_label(lbl) for (lbl, _) in (mandatory_advance_items + mandatory_base_items)
    }
    optional_items: List[Tuple[str, Any]] = []
    for table in soup.find_all("table"):
        body = table.find("tbody") or table
        rows = body.find_all("tr", recursive=False)
        if not rows:
            continue
        header_idx = -1
        for idx, tr in enumerate(rows):
            tds = tr.find_all("td", recursive=False)
            if not tds:
                continue
            if any(td_text_equals(td, "Optional extras:") for td in tds):
                header_idx = idx
                break
        if header_idx == -1:
            continue
        for tr in rows[header_idx + 1:]:
            tds = tr.find_all("td")
            if len(tds) != 2:
                continue
            label = text_of(tds[0]).strip()
            ll = label.lower()
            if ll in ("optional extras", "price", "price:"):
                continue
            if ll.startswith("mandatory extras") or ll.startswith("total") or "total (payable" in ll:
                break
            # Exclude items already captured as mandatory / marked obligatory
            norm_lbl = normalize_label(label)
            if "obligatory" in norm_lbl or "mandatory" in norm_lbl:
                continue
            if norm_lbl in mandatory_label_norms:
                continue
            right_text = text_of(tds[1]).strip()
            amt = _parse_amt(right_text, charter_price_net.currency)
            if amt is None:
                continue
            optional_items.append((label, amt))
        break
    # Deduplicate optional items by label + amount string
    if optional_items:
        seen_opt: set = set()
        dedup_opt: List[Tuple[str, Any]] = []
        for lbl, amt in optional_items:
            amt_str = amt.format() if hasattr(amt, "format") else str(amt)
            key = (normalize_label(lbl), amt_str)
            if key in seen_opt:
                continue
            seen_opt.add(key)
            dedup_opt.append((lbl, amt))
        optional_items = dedup_opt

    # Licence required
    licence_required: Optional[str] = None
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        bold = tds[0].find("b")
        if bold and "skipper licence required" in text_of(bold).lower():
            td_text = text_of(tds[0])
            m = re.search(r"Skipper licence required\s*:?\s*(.*)$", td_text, re.I)
            licence_required = (m.group(1).strip() if m else "Yes") or "Yes"
            break

    # Equipment tags
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

    # Specs
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
        optional_items=optional_items,
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
        to_location=to_location,
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
    left_img = html.escape(y.image_urls[0]) if y.image_urls else ""
    right_img = html.escape(y.image_urls[1]) if len(y.image_urls) > 1 else left_img
    full_width_btn = ""
    if y.more_info_url:
        full_width_btn = (
            f'<a href="{html.escape(y.more_info_url)}" '
            f'style="background:{SAILSCANNER_BLUE};color:#ffffff;text-decoration:none;font-family:Arial, sans-serif;'
            f'display:block;padding:10px 12px;border-radius:4px;font-weight:600;'
            f'text-transform:none;text-align:center;font-size:13px;">More info about this yacht</a>'
        )

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

    def render_items(title: str, items: List[Tuple[str, Any]]) -> str:
        if not items:
            return ""
        rows = "".join(
            f"<tr><td style='text-align:left;padding:4px 0;'>{html.escape(to_sentence_case(label) if is_mostly_uppercase(label) else label)}</td>"
            f"<td style='text-align:right;padding:4px 0;white-space:nowrap;'>"
            f"{amt.format() if hasattr(amt, 'format') else html.escape(str(amt))}</td></tr>"
            for label, amt in items
        )
        return (
            f"<tr><td colspan='2' style='font-weight:bold;padding-top:8px;color:{SAILSCANNER_BLUE};'>{html.escape(title)}:</td></tr>"
            f"{rows}"
        )

    # For the email, only show the Skipper line in optional extras (crewed charters
    # have everything bundled; non-crewed need the skipper highlighted).
    # The full optional_items list is preserved on the YachtEntry for the proposal system.
    def _is_label_skipper(lbl: str) -> bool:
        return "skipper" in (lbl or "").lower() and "cook" not in (lbl or "").lower()

    equip_pills = build_equipment_pills(y.equipment_tags)
    is_crewed = y.charter_type and "crewed" in (y.charter_type or "").strip().lower()

    # Build email-specific optional display (crewed: nothing; non-crewed: skipper only)
    skipper_mandatory = any(_is_label_skipper(lbl) for lbl, _ in (y.mandatory_advance_items + y.mandatory_base_items))
    if is_crewed:
        email_optional: List[Tuple[str, Any]] = []
        total_display = y.grand_total
        total_label = "Total"
    else:
        skipper_opts = [(lbl, amt) for lbl, amt in y.optional_items if _is_label_skipper(lbl)]
        if skipper_mandatory:
            email_optional = []
        elif skipper_opts:
            email_optional = [skipper_opts[0]]
        else:
            email_optional = [("Skipper", Money(DEFAULT_SKIPPER_PRICE, y.charter_price_net.currency or "€"))]
        skipper_money = email_optional[0][1] if email_optional and hasattr(email_optional[0][1], "amount") else Money.zero(y.charter_price_net.currency or "€")
        total_display = y.grand_total + skipper_money
        total_label = "Total with Skipper"
    total_html = (
        f"<span style='font-weight:bold;color:{SAILSCANNER_BLUE};'>{total_display.format()}</span>"
    )

    use_model_as_title = bool(y.model and y.model.strip())
    title_text = (y.model or "").strip() if use_model_as_title else (y.name or "").strip()
    subtitle_parts = [p for p in [y.boat_type, (None if use_model_as_title else y.model), y.charter_type] if p]
    subtitle = " · ".join(subtitle_parts)

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
    to_line = f"To: <strong>{html.escape(y.to_location)}</strong>" if getattr(y, 'to_location', None) else ""
    dates_line = ""
    if y.date_from_str or y.date_to_str or y.check_in_time or y.check_out_time:
        left = ", ".join([p for p in [y.date_from_str, y.check_in_time] if p])
        right = ", ".join([p for p in [y.date_to_str, y.check_out_time] if p])
        dates_line = f"Dates: <strong>{html.escape(left)}</strong> to <strong>{html.escape(right)}</strong>"
    base_dates_html = ""
    if base_line or to_line or dates_line:
        callout_lines: List[str] = []
        if base_line:
            callout_lines.append(
                f"<div style='font-family:Arial, sans-serif;font-size:13px;color:{SAILSCANNER_BLUE};margin-bottom:4px'>{base_line}</div>"
            )
        if to_line:
            callout_lines.append(
                f"<div style='font-family:Arial, sans-serif;font-size:13px;color:{SAILSCANNER_BLUE};margin-bottom:4px'>{to_line}</div>"
            )
        if dates_line:
            callout_lines.append(
                f"<div style='font-family:Arial, sans-serif;font-size:13px;color:{SAILSCANNER_BLUE};'>{dates_line}</div>"
            )
        base_dates_html = (
            "<div style='margin:8px 0 12px 0;padding:8px 10px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px'>"
            + "".join(callout_lines)
            + "</div>"
        )

    return f"""
<!-- SailScanner Yacht Block (Skippered) -->
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
                    {render_items("Optional extras", email_optional) if email_optional else ""}
                    <tr>
                      <td style="text-align:left;padding:8px 0;font-weight:bold;color:{SAILSCANNER_BLUE};">{total_label}</td>
                      <td style="text-align:right;padding:8px 0;">{total_html}</td>
                    </tr>
                    {"<tr><td colspan='2' style='text-align:left;padding:4px 0;color:#6b7280'>Security deposit: " + (y.deposit.format() if y.deposit else "-") + "</td></tr>"}
                  </table>
                </td>
                <td style="vertical-align:top;padding-left:12px;width:40%;">
                  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-family:Arial, sans-serif;font-size:14px;color:#111827;">
                    <tr><td style="padding-top:8px;font-family:Arial, sans-serif;font-size:12px;color:{SAILSCANNER_BLUE};font-weight:bold">Other details</td></tr>
                    {"<tr><td style='padding:4px 0'>Check-in: " + (html.escape(y.check_in_time) if y.check_in_time else "-") + "</td></tr>"}
                    {"<tr><td style='padding:4px 0'>Check-out: " + (html.escape(y.check_out_time) if y.check_out_time else "-") + "</td></tr>"}
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
    return f"""<!-- BEGIN SailScanner Yachts (Skippered) -->
<div style="width:96%;max-width:620px;margin:0 auto;padding:0;">
{''.join(blocks)}
</div>
<!-- END SailScanner Yachts (Skippered) -->"""


def parse_file(path: Path) -> List[YachtEntry]:
    content = path.read_text(encoding="utf-8", errors="ignore")
    sections = split_sections(content)
    yachts: List[YachtEntry] = []
    for section in sections:
        try:
            yachts.append(parse_yacht_section(section))
        except Exception:
            continue
    return yachts


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Build SailScanner (Skippered) email HTML block from Booking Manager HTML exports.")
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

    html_out = render_all(all_entries)
    stem = Path(args.inputs[0]).stem if len(args.inputs) == 1 else "combined"
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-")
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    out_name = f"email_snippet-{safe_stem}-{ts}.html"
    Path(out_name).write_text(html_out, encoding="utf-8")
    print(out_name)


if __name__ == "__main__":
    main()


