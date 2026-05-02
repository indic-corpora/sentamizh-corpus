#!/usr/bin/env python3
"""
Sentamizh Corpus — Project Madurai Source Downloader

Downloads all source HTML files from Project Madurai needed for the corpus.
Run this on your LOCAL machine (not in Cowork sandbox).

Usage:
    python3 download_sources.py
    python3 download_sources.py --output-dir ../data/raw
    python3 download_sources.py --dry-run          # Show what would be downloaded
    python3 download_sources.py --text purananuru   # Download only Purananuru files

Requirements:
    Python 3.7+ (no external packages needed — uses only stdlib)
"""

import os
import sys
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path


# ─── Source File Definitions ─────────────────────────────────────────────────
# Each entry: (filename_to_save, URL, description)
# URLs from Project Madurai UTF-8 collection

SOURCES = [
    # ═══ SANGAM LAYER ═══
    # All URLs verified against projectmadurai.org/pmworks.html on 2026-04-11

    # Purananuru — 6 files across 2 editions
    # Edition 1 (PM #494): verses 1-200, Auvai Duraisamy Pillai commentary
    ("Purananuru_Ed1_Part1.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0494_01.html",
     "Purananuru verses 1-200 (edition 1, section 1) — Auvai Duraisamy Pillai commentary"),
    ("Purananuru_Ed1_Part2.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0494_02.html",
     "Purananuru verses 1-200 (edition 1, section 2)"),
    ("Purananuru_Ed1_Part3.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0494_03.html",
     "Purananuru verses 1-200 (edition 1, section 3)"),
    # Edition 2 (PM #531): verses 201-400, with explanatory commentary
    ("Purananuru_Ed2_Part1.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0531_01.html",
     "Purananuru verses 201-400 (edition 2, section 1)"),
    ("Purananuru_Ed2_Part2.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0531_02.html",
     "Purananuru verses 201-400 (edition 2, section 2)"),
    ("Purananuru_Ed2_Part3.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0531_03.html",
     "Purananuru verses 201-400 (edition 2, section 3)"),

    # Akananuru — 5 files across 3 editions
    # Edition 1 (PM #490): Kalittriyanai Nirai, verses 1-120
    ("Akananuru_Ed1_Part1.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0490_01.html",
     "Akananuru verses 1-120 (Kalittriyanai Nirai, section 1)"),
    ("Akananuru_Ed1_Part2.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0490_02.html",
     "Akananuru verses 1-120 (Kalittriyanai Nirai, section 2)"),
    # Edition 2 (PM #523): verses 121-300, Nattar commentary
    ("Akananuru_Ed2_Part1.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0523_01.html",
     "Akananuru verses 121-300 (Nattar commentary, section 1)"),
    ("Akananuru_Ed2_Part2.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0523_02.html",
     "Akananuru verses 121-300 (Nattar commentary, section 2)"),
    # Edition 3 (PM #534): verses 301-400
    ("Akananuru_Ed3.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0534.html",
     "Akananuru verses 301-400 (with explanatory commentary)"),

    # NOTE: Kuruntokai and Natrinai are NOT available on Project Madurai.
    # These texts will need to be sourced from:
    #   - HuggingFace datasets (PaaPeyarchi has Kuruntokai/Natrinai pairs)
    #   - Internet Archive (archive.org/details/project-madurai-pm-all-works)
    #   - Tamil Virtual Academy or other digital libraries

    # ═══ BHAKTI LAYER ═══

    # Thirumanthiram (PM #4) — Thirumular
    ("Thirumanthiram.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0004.html",
     "Thirumanthiram of Thirumular"),

    # Thevaram — First 3 Thirumurai (6 files)
    ("Thevaram_Thirumurai1_Part1.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0150.html",
     "Thevaram - First Thirumurai Part 1 (Songs 1-721) — Thirugnana Sambandar"),
    ("Thevaram_Thirumurai1_Part2.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0151.html",
     "Thevaram - First Thirumurai Part 2 (Songs 722-1469)"),
    ("Thevaram_Thirumurai2_Part1.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0157.html",
     "Thevaram - Second Thirumurai Part 1 (Songs 1-654) — Thirunavukkarasar (Appar)"),
    ("Thevaram_Thirumurai2_Part2.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0162.html",
     "Thevaram - Second Thirumurai Part 2 (Songs 655-1331)"),
    ("Thevaram_Thirumurai3_Part1.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0173.html",
     "Thevaram - Third Thirumurai Part 1 (Songs 1-713) — Sundarar"),
    ("Thevaram_Thirumurai3_Part2.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0179.html",
     "Thevaram - Third Thirumurai Part 2 (Songs 714-1347)"),

    # Nalayira Divya Prabandham (PM #5-8) — 7 files
    ("Divya_Prabandham_Mudhal_Ayiram_1.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0005_01.html",
     "Nalayira Divya Prabandham — Mudhal Ayiram Part 1 (Thiruppallandu, Thirumozhi)"),
    ("Divya_Prabandham_Mudhal_Ayiram_2.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0005_02.html",
     "Nalayira Divya Prabandham — Mudhal Ayiram Part 2 (Thirupavai, Nachiyar Thirumozhi, etc.)"),
    ("Divya_Prabandham_Periya_Thirumozhi_1.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0006_01.html",
     "Nalayira Divya Prabandham — Periya Thirumozhi Part 1"),
    ("Divya_Prabandham_Periya_Thirumozhi_2.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0006_02.html",
     "Nalayira Divya Prabandham — Periya Thirumozhi Part 2"),
    ("Divya_Prabandham_Siru_Thirumurai.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0007.html",
     "Nalayira Divya Prabandham — Siru Thirumurai (Thirukurundhangam, Thirunedunthandakam)"),
    ("Divya_Prabandham_Iramanusa_1.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0008_01.html",
     "Nalayira Divya Prabandham — Iramanusa Nutrantadi Part 1"),
    ("Divya_Prabandham_Iramanusa_2.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0008_02.html",
     "Nalayira Divya Prabandham — Iramanusa Nutrantadi Part 2"),

    # ═══ EPIC LAYER ═══

    # Silappatikaram (PM #451) — Pukar Kandam only (Madurai/Vanji Kandams not on PM)
    ("Silappatikaram_Pukar_Part1.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0451_01.html",
     "Silappatikaram — Pukar Kandam with commentary, Part 1"),
    ("Silappatikaram_Pukar_Part2.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0451_02.html",
     "Silappatikaram — Pukar Kandam with commentary, Part 2"),
    ("Silappatikaram_Pukar_Part3.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0451_03.html",
     "Silappatikaram — Pukar Kandam with commentary, Part 3"),

    # Manimekalai (PM #141) — Tamil original by Seethalachadhanar
    ("Manimekalai.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0141.html",
     "Manimekalai — Tamil original by Seethalachadhanar"),
    # Manimekalai summary with notes (PM #818)
    ("Manimekalai_Summary_Part1.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0818_01.html",
     "Manimekalai — Summary with explanatory notes, Part 1"),
    ("Manimekalai_Summary_Part2.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0818_02.html",
     "Manimekalai — Summary with explanatory notes, Part 2"),

    # ═══ DIDACTIC LAYER ═══

    # Naladiyar (PM #518) — Tamil with commentary
    ("Naladiyar.html",
     "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0518.html",
     "Naladiyar — Tamil text with explanatory commentary"),

    # NOTE: Pazhamozhi Nanuru not found on Project Madurai.
    # Kuruntokai, Natrinai, Silappatikaram (Madurai/Vanji Kandams),
    # and Pazhamozhi will need alternative sources.
]

# Text name → filename prefix mapping for --text filter
TEXT_PREFIXES = {
    'purananuru': 'Purananuru',
    'akananuru': 'Akananuru',
    'thirumanthiram': 'Thirumanthiram',
    'thevaram': 'Thevaram',
    'divya': 'Divya_Prabandham',
    'silappatikaram': 'Silappatikaram',
    'manimekalai': 'Manimekalai',
    'naladiyar': 'Naladiyar',
}


# ─── Download Logic ──────────────────────────────────────────────────────────

def download_file(url: str, output_path: Path, retries: int = 3) -> bool:
    """Download a single file with retry logic and polite delay."""
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'SentamizhCorpus/1.0 (Academic research; Classical Tamil literature corpus)',
                'Accept': 'text/html,application/xhtml+xml,*/*',
            })
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read()

            # Verify it looks like HTML with Tamil content
            text = data.decode('utf-8', errors='replace')
            if len(data) < 1000:
                print(f"  WARNING: File seems too small ({len(data)} bytes)")
            if '<html' not in text.lower()[:500]:
                print(f"  WARNING: Doesn't look like HTML")

            # Save
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(data)

            return True

        except urllib.error.HTTPError as e:
            print(f"  HTTP Error {e.code}: {e.reason} (attempt {attempt}/{retries})")
            if e.code == 404:
                print(f"  File not found at this URL — may need to verify")
                return False
            if attempt < retries:
                time.sleep(5 * attempt)

        except urllib.error.URLError as e:
            print(f"  URL Error: {e.reason} (attempt {attempt}/{retries})")
            if attempt < retries:
                time.sleep(5 * attempt)

        except Exception as e:
            print(f"  Error: {e} (attempt {attempt}/{retries})")
            if attempt < retries:
                time.sleep(5 * attempt)

    return False


def main():
    parser = argparse.ArgumentParser(
        description="Download Project Madurai source files for Sentamizh Corpus"
    )
    parser.add_argument("--output-dir", "-o", default=None,
                       help="Output directory (default: data/raw/ relative to script)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be downloaded without downloading")
    parser.add_argument("--text", "-t",
                       help="Download only files for a specific text (e.g., 'purananuru', 'akananuru')")
    parser.add_argument("--delay", type=float, default=2.0,
                       help="Delay between downloads in seconds (default: 2.0, be polite!)")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                       help="Skip files that already exist (default: True)")

    args = parser.parse_args()

    # Determine output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        script_dir = Path(__file__).parent
        output_dir = script_dir.parent / "data" / "raw"

    output_dir.mkdir(parents=True, exist_ok=True)

    # Filter sources if --text specified
    sources = SOURCES
    if args.text:
        text_key = args.text.lower()
        if text_key in TEXT_PREFIXES:
            prefix = TEXT_PREFIXES[text_key]
            sources = [(f, u, d) for f, u, d in SOURCES if f.startswith(prefix)]
            if not sources:
                print(f"No sources found for '{args.text}'")
                sys.exit(1)
        else:
            print(f"Unknown text: '{args.text}'")
            print(f"Available: {', '.join(sorted(TEXT_PREFIXES.keys()))}")
            sys.exit(1)

    # Summary
    print(f"Sentamizh Corpus — Source Downloader")
    print(f"Output directory: {output_dir.resolve()}")
    print(f"Files to download: {len(sources)}")
    if args.text:
        print(f"Filtered to: {args.text}")
    print()

    if args.dry_run:
        print("DRY RUN — showing what would be downloaded:\n")
        for filename, url, desc in sources:
            exists = (output_dir / filename).exists()
            status = " [EXISTS]" if exists else ""
            print(f"  {filename}{status}")
            print(f"    URL: {url}")
            print(f"    {desc}")
            print()
        print("Run without --dry-run to download.")
        return

    # Download
    success = 0
    skipped = 0
    failed = 0

    for i, (filename, url, desc) in enumerate(sources, 1):
        output_path = output_dir / filename

        print(f"[{i}/{len(sources)}] {filename}")
        print(f"  {desc}")

        if args.skip_existing and output_path.exists():
            size = output_path.stat().st_size
            print(f"  SKIPPED (already exists, {size:,} bytes)")
            skipped += 1
            continue

        print(f"  Downloading from: {url}")
        if download_file(url, output_path):
            size = output_path.stat().st_size
            print(f"  OK ({size:,} bytes)")
            success += 1
        else:
            print(f"  FAILED")
            failed += 1

        # Polite delay between requests
        if i < len(sources):
            time.sleep(args.delay)

    # Summary
    print(f"\n{'='*50}")
    print(f"Download complete!")
    print(f"  Success: {success}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed:  {failed}")
    print(f"  Total:   {len(sources)}")

    if failed > 0:
        print(f"\nSome downloads failed. You can re-run the script — it will skip existing files.")
        sys.exit(1)


if __name__ == "__main__":
    main()
