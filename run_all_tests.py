#!/usr/bin/env python3
"""
run_all_tests.py
================
Runs every test-*.json lead against the local server, uploads proposals to WordPress,
then generates a dated test-results .docx report.

Usage (run from the Proposals directory with the server already running):
    python3 run_all_tests.py [--server http://127.0.0.1:8000] [--out /path/to/results.json]

The server must be running first:
    uvicorn app:app --reload
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
API_SECRET = os.environ.get("SAILSCANNER_API_SECRET", "")

# ── Config ─────────────────────────────────────────────────────────────────────

DEFAULT_SERVER  = "http://127.0.0.1:8000"
INPUT_DIR       = Path(__file__).parent / "input_files"
OUTPUT_DIR      = Path(__file__).parent / "output_files"
SCRIPT_DIR      = Path(__file__).parent / "scripts"
TODAY           = date.today().isoformat()

# ── Helpers ────────────────────────────────────────────────────────────────────

def find_test_leads():
    files = sorted(INPUT_DIR.glob("test-*.json"))
    # exclude non-numbered helpers
    return [f for f in files if f.stem.split("-")[1].isdigit()]

def run_lead(lead_path: Path, server: str, timeout: int = 300) -> dict:
    lead = json.loads(lead_path.read_text())
    answers = lead.get("answers", {})
    contact = answers.get("contact", {})
    region_raw = answers.get("region") or answers.get("country") or ""
    region = (region_raw[0] if isinstance(region_raw, list) else region_raw).strip()

    print(f"\n{'─'*60}")
    print(f"▶  {lead_path.stem}")
    print(f"   {contact.get('firstName')} {contact.get('lastName')} | {region} | "
          f"{answers.get('boatType','?')} | {answers.get('size','?')}ft | "
          f"budget={answers.get('budget','?')} | "
          f"{answers.get('dates',{}).get('start','?')} → {answers.get('dates',{}).get('end','?')}")

    t0 = time.time()
    try:
        headers = {}
        if API_SECRET:
            headers["X-Api-Secret"] = API_SECRET
        resp = requests.post(
            f"{server}/build-proposal",
            json=lead,
            headers=headers,
            timeout=timeout,
        )
        elapsed = round(time.time() - t0, 1)

        if resp.status_code == 200:
            data = resp.json()
        else:
            try:
                data = resp.json()
            except Exception:
                data = {"status": "error", "detail": resp.text[:500]}

        data["_lead_id"]   = lead_path.stem
        data["_elapsed"]   = elapsed
        data["_region"]    = region
        data["_boat_type"] = answers.get("boatType", "")
        data["_size"]      = answers.get("size", "")
        data["_budget"]    = answers.get("budget", "")
        data["_dates"]     = f"{answers.get('dates',{}).get('start','')} – {answers.get('dates',{}).get('end','')}"
        data["_name"]      = f"{contact.get('firstName','')} {contact.get('lastName','')}".strip()
        data["_http_status"] = resp.status_code

        status = data.get("status", "error")
        url    = data.get("proposal_url", "")
        print(f"   status={status}  elapsed={elapsed}s")
        if url:
            print(f"   url={url}")
        if data.get("relaxation_applied"):
            print(f"   relaxation: {data['relaxation_applied']}")
        return data

    except requests.exceptions.Timeout:
        elapsed = round(time.time() - t0, 1)
        print(f"   TIMEOUT after {elapsed}s")
        return {
            "_lead_id":    lead_path.stem,
            "_elapsed":    elapsed,
            "_region":     region,
            "_boat_type":  answers.get("boatType", ""),
            "_size":       answers.get("size", ""),
            "_budget":     answers.get("budget", ""),
            "_dates":      f"{answers.get('dates',{}).get('start','')} – {answers.get('dates',{}).get('end','')}",
            "_name":       f"{contact.get('firstName','')} {contact.get('lastName','')}".strip(),
            "_http_status": 0,
            "status": "error",
            "detail": f"Request timed out after {elapsed}s",
        }
    except Exception as exc:
        elapsed = round(time.time() - t0, 1)
        print(f"   ERROR: {exc}")
        return {
            "_lead_id":    lead_path.stem,
            "_elapsed":    elapsed,
            "_region":     region,
            "_boat_type":  answers.get("boatType", ""),
            "_size":       answers.get("size", ""),
            "_budget":     answers.get("budget", ""),
            "_dates":      f"{answers.get('dates',{}).get('start','')} – {answers.get('dates',{}).get('end','')}",
            "_name":       f"{contact.get('firstName','')} {contact.get('lastName','')}".strip(),
            "_http_status": 0,
            "status": "error",
            "detail": str(exc),
        }

# ── Report generation ──────────────────────────────────────────────────────────

DOCX_SCRIPT = Path(__file__).parent / "scripts" / "make_test_results_docx.js"

def generate_docx(results: list[dict], out_path: Path):
    """Write results JSON to a temp file, then call the Node.js docx builder."""
    tmp = Path(__file__).parent / "output_files" / f"_test_results_{TODAY}.json"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_text(json.dumps(results, indent=2))
    print(f"\nGenerating docx → {out_path}")
    try:
        subprocess.run(
            ["node", str(DOCX_SCRIPT), str(tmp), str(out_path)],
            check=True,
            cwd=str(Path(__file__).parent),  # run from Proposals dir so node_modules is found
        )
        print(f"✓ Report saved: {out_path}")
    except subprocess.CalledProcessError as e:
        print(f"✗ docx generation failed: {e}")
    finally:
        tmp.unlink(missing_ok=True)

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--out", default=None, help="Output .docx path")
    args = parser.parse_args()

    leads = find_test_leads()
    if not leads:
        print(f"No test-*.json files found in {INPUT_DIR}")
        sys.exit(1)

    print(f"Found {len(leads)} test leads. Server: {args.server}")
    print("Make sure the server is running: uvicorn app:app --reload\n")

    # Check server is up
    try:
        r = requests.get(f"{args.server}/health", timeout=5)
        if r.status_code != 200:
            raise Exception(f"Health check returned {r.status_code}")
    except Exception as e:
        print(f"ERROR: Cannot reach server at {args.server}/health — {e}")
        print("Start it with:  uvicorn app:app --reload")
        sys.exit(1)

    results = []
    for lead_path in leads:
        r = run_lead(lead_path, args.server)
        results.append(r)
        time.sleep(1)  # brief pause between leads

    # Summary
    ok      = [r for r in results if r.get("status") == "ok"]
    manual  = [r for r in results if r.get("status") == "manual_required"]
    errors  = [r for r in results if r.get("status") == "error"]
    relaxed = [r for r in ok if r.get("relaxation_applied")]

    print(f"\n{'='*60}")
    print(f"SUMMARY  ({len(results)} leads)")
    print(f"  ✓ OK:             {len(ok)}")
    print(f"  ⚠ Manual reqd:   {len(manual)}")
    print(f"  ✗ Errors:         {len(errors)}")
    print(f"  ~ Filters relaxed:{len(relaxed)}")
    avg_elapsed = round(sum(r.get("_elapsed", 0) for r in results) / len(results), 1)
    print(f"  ⏱ Avg time:      {avg_elapsed}s")
    print(f"{'='*60}\n")

    out_path = Path(args.out) if args.out else (
        OUTPUT_DIR / f"test-results-{TODAY}.docx"
    )
    out_path.parent.mkdir(exist_ok=True)
    generate_docx(results, out_path)


if __name__ == "__main__":
    main()
