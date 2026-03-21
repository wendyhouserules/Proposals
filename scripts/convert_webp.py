#!/usr/bin/env python3
"""
Convert WebP images to JPEG for WordPress upload.

WordPress on this server uses ImageMagick (which lacks WebP support) as its
primary image editor. Converting to JPEG before uploading avoids thumbnail
generation failures in the WP media library.

Usage:
  # Convert all .webp files in a folder (saves .jpg alongside originals):
  python scripts/convert_webp.py /path/to/folder

  # Convert a single file:
  python scripts/convert_webp.py /path/to/image.webp

  # Convert folder and save JPEGs into a separate output folder:
  python scripts/convert_webp.py /path/to/folder --out /path/to/output

  # Set JPEG quality (default: 90):
  python scripts/convert_webp.py /path/to/folder --quality 85

Requires: macOS sips (built-in, no install needed) OR Pillow (pip install Pillow).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _convert_with_sips(src: Path, dst: Path, quality: int) -> bool:
    """Use macOS built-in sips. Returns True on success."""
    try:
        result = subprocess.run(
            ["sips", "-s", "format", "jpeg", "-s", "formatOptions", str(quality),
             str(src), "--out", str(dst)],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False  # sips not available (non-macOS)


def _convert_with_pillow(src: Path, dst: Path, quality: int) -> bool:
    """Use Pillow. Returns True on success."""
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return False
    try:
        with Image.open(src) as img:
            rgb = img.convert("RGB")  # WebP may have transparency; JPEG needs RGB
            rgb.save(dst, "JPEG", quality=quality, optimize=True)
        return True
    except Exception as exc:
        print(f"  Pillow error: {exc}", file=sys.stderr)
        return False


def convert_file(src: Path, out_dir: Path | None, quality: int) -> Path | None:
    dst_dir = out_dir if out_dir else src.parent
    dst = dst_dir / (src.stem + ".jpg")

    if dst.exists():
        print(f"  ⏭  Skip (already exists): {dst.name}")
        return dst

    # Try sips first (no dependencies, macOS only), then Pillow.
    ok = _convert_with_sips(src, dst, quality) or _convert_with_pillow(src, dst, quality)

    if ok and dst.exists() and dst.stat().st_size > 0:
        size_kb = dst.stat().st_size / 1024
        print(f"  ✓  {src.name}  →  {dst.name}  ({size_kb:.0f} KB)")
        return dst
    else:
        if dst.exists():
            dst.unlink(missing_ok=True)
        print(f"  ✗  Failed: {src.name}  (is sips or Pillow available?)", file=sys.stderr)
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert WebP images to JPEG.")
    parser.add_argument("input", help="WebP file or folder containing WebP files.")
    parser.add_argument("--out", metavar="DIR",
                        help="Output folder for JPEGs (default: same folder as source).")
    parser.add_argument("--quality", type=int, default=90, metavar="N",
                        help="JPEG quality 1-100 (default: 90).")
    args = parser.parse_args()

    src_path = Path(args.input).expanduser().resolve()
    out_dir  = Path(args.out).expanduser().resolve() if args.out else None

    if not src_path.exists():
        print(f"ERROR: Path not found: {src_path}", file=sys.stderr)
        sys.exit(1)

    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    if src_path.is_file():
        if src_path.suffix.lower() != ".webp":
            print(f"ERROR: Not a .webp file: {src_path.name}", file=sys.stderr)
            sys.exit(1)
        files = [src_path]
    else:
        files = sorted(src_path.glob("*.webp")) + sorted(src_path.glob("*.WEBP"))
        if not files:
            print(f"No .webp files found in: {src_path}")
            sys.exit(0)

    print(f"\nConverting {len(files)} file(s) → JPEG (quality {args.quality})\n")
    ok_count = 0
    for f in files:
        result = convert_file(f, out_dir, args.quality)
        if result:
            ok_count += 1

    print(f"\n{'✓' if ok_count == len(files) else '⚠'} Done: {ok_count}/{len(files)} converted.")
    if ok_count < len(files):
        print("  Install Pillow if sips is unavailable: pip install Pillow", file=sys.stderr)


if __name__ == "__main__":
    main()
