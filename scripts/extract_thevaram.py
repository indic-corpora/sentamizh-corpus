#!/usr/bin/env python3
"""
Sentamizh Corpus — Thevaram Extraction Pipeline

Extracts structured verse data from Project Madurai Thevaram HTML files.
Produces JSON entries conforming to the Sentamizh Corpus schema (32 fields).

The currently-bundled Thevaram is the Sambandar Tēvāram (Thirumurai 1-3),
which is split across six files:

    Thevaram_Thirumurai1_Part1.html   verses 1-721
    Thevaram_Thirumurai1_Part2.html   verses 722-1469
    Thevaram_Thirumurai2_Part1.html   verses 1-654
    Thevaram_Thirumurai2_Part2.html   verses 655-1331
    Thevaram_Thirumurai3_Part1.html   verses 1-713
    Thevaram_Thirumurai3_Part2.html   verses 714-end

Each file is organised as a sequence of pathigams (decades — sets of ~10
verses on a single deity / shrine). Each pathigam has the structure:

    <h3><font color="blue">P.D Title</font></h3>
    <dd><b>பண் - PannName</b><p>
    <table border=0>
    <tr><td valign=top>N <td>VERSE_LINES <td valign=bottom>P.D.V
        <td valign=top>N+1 <td>VERSE_LINES <td valign=bottom>P.D.V+1
        ...
    </table>

Some pathigams use position-within-decade in <td valign=bottom> (just "01",
"02", ...) instead of the full P.D.V triple.

Verse IDs use a global running count across the entire Thevaram (not per
file or per Thirumurai), with offsets hardcoded so each per-file extract
produces unique IDs after merge.

Usage:
    python extract_thevaram.py <html_file> [--output <output_file>]
"""

import json
import re
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict


# ─── Data Classes ───────────────────────────────────────────────────────────

@dataclass
class ExtractedVerse:
    """Raw extracted Thevaram verse data."""
    verse_number: str = ""           # Within-Thirumurai absolute (e.g. "722")
    global_n: int = 0                # Global running count across all of Thevaram
    classical_tamil: str = ""
    pann: str = ""
    pathigam: str = ""               # e.g. "1.1", "3.067"
    pathigam_title: str = ""
    poet: str = ""


# ─── Configuration ──────────────────────────────────────────────────────────

# Cumulative verses BEFORE this Thirumurai. Verified by inspection of the
# six Project Madurai files: TM1 ends at 1469, TM2 ends at 1331 → TM2 starts
# at global 1470, TM3 starts at global 2801.
TM_OFFSETS = {1: 0, 2: 1469, 3: 2800}


# ─── Text Cleaning ──────────────────────────────────────────────────────────

def html_block_to_text(html_chunk: str) -> str:
    """Convert HTML chunk → plain text, preserving line structure via <br>."""
    text = re.sub(r'<br\s*/?>', '\n', html_chunk, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('\xa0', ' ').replace('&nbsp;', ' ')
    return text


def clean_verse_text(raw: str) -> str:
    """Strip line numbers, attribution, and other extraneous markup."""
    text = raw.replace('\xa0', ' ').replace('&nbsp;', ' ')
    lines = []
    for line in text.split('\n'):
        # Strip trailing line numbers like "    01" or "    1.1.1"
        line = re.sub(r'\s+\d+(?:\.\d+){0,2}\s*$', '', line)
        line = line.strip()
        if line and not re.match(r'^-{3,}$', line):
            lines.append(line)
    return '\n'.join(lines).strip()


def tamil_char_count(s: str) -> int:
    return sum(1 for c in s if 0x0B80 <= ord(c) <= 0x0BFF)


# ─── Extraction ─────────────────────────────────────────────────────────────

def detect_thirumurai(filename: str) -> int:
    """Return Thirumurai number (1, 2, or 3) from filename."""
    m = re.search(r'Thirumurai(\d)', filename)
    return int(m.group(1)) if m else 1


def detect_poet(thirumurai: int) -> str:
    """Sambandar wrote Thirumurai 1-3."""
    return 'Sambandar' if 1 <= thirumurai <= 3 else ''


# Match a pathigam header: <h3><font color="blue">P.D[D]. Title</h3>
PATHIGAM_HEADER = re.compile(
    r'<h3[^>]*>\s*(?:<font[^>]*>\s*)?\s*(\d+)\.\s*(\d+)[\s\.]*([^<\n]+?)\s*<',
    re.DOTALL,
)

# Match a single verse: top-cell with verse-number, content cell, bottom cell.
# Tolerant of trailing dot on verse number (TM3 quirk), unquoted attributes,
# missing width attrs, and stray </tr> tags.
VERSE_PATTERN = re.compile(
    r'<td[^>]*valign\s*=\s*["\']?top["\']?[^>]*>\s*(\d+)\.?\s*'
    r'<td[^>]*>\s*(.*?)\s*'
    r'<td[^>]*valign\s*=\s*["\']?bottom["\']?[^>]*>\s*([0-9.]+)',
    re.DOTALL | re.IGNORECASE,
)

# Match the pann line: <dd><b>பண் - PannName</b> or <b>பண் - PannName</b>
PANN_PATTERN = re.compile(
    r'<b>\s*பண்\s*[-\s]*\s*([^<\n]+?)\s*</b>',
    re.DOTALL,
)


def extract_verses(html_path: str) -> List[ExtractedVerse]:
    with open(html_path, 'r', encoding='utf-8') as f:
        raw = f.read()

    tm = detect_thirumurai(Path(html_path).name)
    tm_offset = TM_OFFSETS.get(tm, 0)

    verses: List[ExtractedVerse] = []

    # Slice into pathigams
    headers = list(PATHIGAM_HEADER.finditer(raw))
    if not headers:
        return verses

    # Skip pathigams whose decade doesn't match TM (e.g. TOC entries with
    # `<h3>` that point to different sections). Typical decade range is
    # 1-200; anything outside is a false positive.
    valid_headers = []
    for h in headers:
        try:
            tm_n = int(h.group(1))
            d_n = int(h.group(2))
            if tm_n == tm and 1 <= d_n <= 250:
                valid_headers.append(h)
        except ValueError:
            continue

    for i, h in enumerate(valid_headers):
        tm_n = h.group(1)
        d_n = h.group(2).lstrip('0') or '0'
        title = h.group(3).strip().rstrip('.')
        pathigam_id = f"{tm_n}.{int(d_n)}"

        end = valid_headers[i + 1].start() if i + 1 < len(valid_headers) else len(raw)
        body = raw[h.end():end]

        # Pann (search in first ~600 chars to avoid catching commentary)
        pann_m = PANN_PATTERN.search(body[:1000])
        pann = pann_m.group(1).strip() if pann_m else ''

        # Find all verses in this pathigam
        for vm in VERSE_PATTERN.finditer(body):
            try:
                n_in_tm = int(vm.group(1))
            except ValueError:
                continue
            if n_in_tm < 1 or n_in_tm > 2000:
                continue

            verse_text = clean_verse_text(html_block_to_text(vm.group(2)))
            if not verse_text or tamil_char_count(verse_text) < 30:
                continue

            global_n = tm_offset + n_in_tm
            verses.append(ExtractedVerse(
                verse_number=str(n_in_tm),
                global_n=global_n,
                classical_tamil=verse_text,
                pann=pann,
                pathigam=pathigam_id,
                pathigam_title=title,
            ))

    # Sort by global verse counter
    verses.sort(key=lambda v: v.global_n)
    return verses


# ─── Schema Mapping ─────────────────────────────────────────────────────────

def map_to_schema(verse: ExtractedVerse, poet: str = "", source_url: str = "") -> dict:
    """Map extracted verse to the 32-field Sentamizh Corpus schema."""
    entry = {
        "verse_id": f"THEV-{verse.global_n:04d}",
        "source_text": "Thevaram",
        "layer": "Bhakti",
        "period": "6th–10th century CE",
        "verse_number": verse.verse_number,
        "classical_tamil": verse.classical_tamil,
        "modern_tamil": None,
        "english": None,
        "source_url": source_url if source_url else None,
        "difficulty": "classical",

        "thinai": None,
        "turai": None,
        "akam_or_puram": None,
        "karu": None,
        "uri": None,
        "ullurai": None,
        "speaker_role": "devotee",
        "metre": None,
        "pann": verse.pann if verse.pann else None,
        "dhvani_layer": None,

        "rasa_primary": "Shanta",
        "rasa_secondary": None,
        "themes": None,
        "philosophical_concept": None,
        "cultural_context": None,
        "storytelling_seed_narrative": None,
        "storytelling_seed_emotional": None,

        "nayika_bheda": None,
        "visual_imagery": None,
        "emotional_valence": None,

        "annotator": "extraction-pipeline-v1",
        "annotation_confidence": "medium",
    }

    context = []
    if poet:
        context.append(f"Poet: {poet}")
    if verse.pathigam:
        context.append(f"Pathigam: {verse.pathigam}")
    if verse.pathigam_title:
        context.append(f"Shrine/Title: {verse.pathigam_title}")
    if verse.pann:
        context.append(f"Pann: {verse.pann}")
    if context:
        entry["cultural_context"] = '; '.join(context)
    return entry


# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Extract Thevaram verses")
    parser.add_argument("html_file")
    parser.add_argument("--output", "-o")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    html_path = Path(args.html_file)
    if not html_path.exists():
        print(f"Error: File not found: {html_path}")
        sys.exit(1)

    print(f"Extracting from: {html_path.name}")
    tm = detect_thirumurai(html_path.name)
    poet = detect_poet(tm)
    print(f"Thirumurai: {tm} (poet: {poet})")

    verses = extract_verses(str(html_path))
    print(f"Extracted {len(verses)} verses")

    if args.verbose:
        for v in verses[:3]:
            preview = v.classical_tamil[:60].replace('\n', ' ')
            print(f"  THEV-{v.global_n:04d} (TM{tm} #{v.verse_number}, {v.pathigam}): {preview}...")

    entries = [map_to_schema(v, poet, args.source_url) for v in verses]

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = html_path.parent.parent / "processed" / f"{html_path.stem}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(entries)} entries to {output_path}")

    if verses:
        with_pann = sum(1 for v in verses if v.pann)
        unique_pathigams = len(set(v.pathigam for v in verses))
        print(f"  Verses with pann: {with_pann}/{len(verses)}")
        print(f"  Unique pathigams: {unique_pathigams}")


if __name__ == "__main__":
    main()
