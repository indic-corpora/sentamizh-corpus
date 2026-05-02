#!/usr/bin/env python3
"""
build_annotator_data.py — Populate annotator/data/ from data/processed/.

The annotator's static site references corpus JSONs at predictable filenames
(e.g. annotator/data/Kuruntokai.json), while the canonical corpus lives at
data/processed/Kuruntokai_Vaidehi_All.json. This script bridges the two:
it reads annotator/data/manifest.json, finds the corresponding canonical
file in data/processed/, and copies it under the annotator's expected name.

Run at deploy time. Netlify invokes this via netlify.toml's build command;
the Makefile invokes it before `netlify deploy --prod` for local deploys.

This script does NOT regenerate the manifest — manifest.json is the
annotator-specific source of truth and is committed to git. Only the
corpus JSON files are derived.

Usage:
    python3 scripts/build_annotator_data.py
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "annotator" / "data" / "manifest.json"
SOURCE_DIR = ROOT / "data" / "processed"
TARGET_DIR = ROOT / "annotator" / "data"

# Map the annotator-side filename (in manifest.json) to the canonical
# data/processed/ filename. Edit this mapping when adding a new text.
SOURCE_MAP = {
    "Purananuru.json": "Purananuru_All.json",
    "Akananuru.json": "Akananuru_All.json",
    "Kuruntokai.json": "Kuruntokai_Vaidehi_All.json",
    "Natrinai.json": "Natrinai_Vaidehi_All.json",
    "Thevaram.json": "Thevaram_All.json",
    "Divya_Prabandham.json": "Divya_Prabandham_All.json",
    "Silappatikaram.json": "Silappatikaram_All.json",
    "Manimekalai.json": "Manimekalai_All.json",
    "Thirumanthiram.json": "Thirumanthiram_All.json",
}


def main() -> int:
    if not MANIFEST_PATH.exists():
        print(f"  error: manifest not found at {MANIFEST_PATH}", file=sys.stderr)
        return 1

    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    with open(MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f)

    copied = 0
    missing_source = []
    missing_mapping = []

    for entry in manifest.get("texts", []):
        target_name = entry.get("file")
        if not target_name:
            continue
        source_name = SOURCE_MAP.get(target_name)
        if source_name is None:
            missing_mapping.append(target_name)
            continue
        source_path = SOURCE_DIR / source_name
        target_path = TARGET_DIR / target_name
        if not source_path.exists():
            missing_source.append(source_name)
            continue
        shutil.copy2(source_path, target_path)
        size_mb = source_path.stat().st_size / (1024 * 1024)
        print(f"  {source_name:40s} -> annotator/data/{target_name:30s} ({size_mb:.1f} MB)")
        copied += 1

    print(f"\nCopied {copied} corpus file(s) to annotator/data/.")

    if missing_mapping:
        print(f"WARNING: no source mapping for: {', '.join(missing_mapping)}", file=sys.stderr)
    if missing_source:
        print(f"WARNING: source file(s) not found in data/processed/: {', '.join(missing_source)}", file=sys.stderr)

    # Non-zero exit if anything was missing — Netlify build should fail
    # so a broken deploy doesn't ship.
    if missing_mapping or missing_source:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
