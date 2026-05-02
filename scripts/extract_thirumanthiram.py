#!/usr/bin/env python3
"""
Sentamizh Corpus — Thirumanthiram Extraction Pipeline

Extracts structured verse data from Project Madurai Thirumanthiram HTML files.
Produces JSON entries conforming to the Sentamizh Corpus schema (32 fields).

Thirumanthiram is a 3,000-verse Saiva Siddhanta tantric text by Tirumūlar.
It is technically Thirumurai 10 of the broader Thirumurai canon, but the
corpus classifies it as the **Spiritual** layer rather than the **Bhakti**
layer that contains Thevaram.

The HTML markup in PM's Project Madurai version uses:

    <h3>பாயிரம் (1-112)</h3>
    <h3>முதல் தந்திரம் (113-336)</h3>
    ...

    <strong> 1.. SubsectionTitle </strong>
    <br>
    1.<br>
    line_1<br>
    line_2<br>
    line_3<br>
    line_4 ... <em>line-end-marker</em> 1<br>
    <br>
    2.<br>
    ...

Each verse is delimited by `^N.<br>` at the start and `<spaces>N<br>` at the
end (the verse number is repeated as a line-end marker).

Usage:
    python extract_thirumanthiram.py <html_file> [--output <output_file>]
"""

import json
import re
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple


# ─── Data Classes ───────────────────────────────────────────────────────────

@dataclass
class ExtractedVerse:
    verse_number: str = ""
    classical_tamil: str = ""
    tantra: str = ""              # e.g. "Pāyiram", "Tantra 1"
    subsection: str = ""          # e.g. "கடவுள் வாழ்த்து"


# ─── Text Cleaning ──────────────────────────────────────────────────────────

def html_block_to_text(html_chunk: str) -> str:
    text = re.sub(r'<br\s*/?>', '\n', html_chunk, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('\xa0', ' ').replace('&nbsp;', ' ')
    return text


def clean_verse_text(raw: str, expected_n: str) -> str:
    """Strip the trailing verse-number end-marker and surrounding whitespace."""
    text = raw.replace('\xa0', ' ').replace('&nbsp;', ' ')
    lines = []
    for line in text.split('\n'):
        # Drop the verse end-marker line: trailing `... N` where N matches expected.
        line = re.sub(rf'\s+{re.escape(expected_n)}\s*$', '', line)
        line = re.sub(r'\s+\d{1,4}\s*$', '', line)
        line = line.strip()
        if not line:
            continue
        lines.append(line)
    return '\n'.join(lines).strip()


def tamil_char_count(s: str) -> int:
    return sum(1 for c in s if 0x0B80 <= ord(c) <= 0x0BFF)


# ─── Tantra Detection ───────────────────────────────────────────────────────

# Map Tamil ordinal prefix → English tantra label
TANTRA_LABELS = {
    'பாயிரம்': 'Pāyiram',
    'முதல்': 'Tantra 1',
    'இரண்டாந்': 'Tantra 2',
    'இரண்டாம்': 'Tantra 2',
    'மூன்றாந்': 'Tantra 3',
    'மூன்றாம்': 'Tantra 3',
    'நான்காந்': 'Tantra 4',
    'நான்காம்': 'Tantra 4',
    'ஐந்தாந்': 'Tantra 5',
    'ஐந்தாம்': 'Tantra 5',
    'ஆறாந்': 'Tantra 6',
    'ஆறாம்': 'Tantra 6',
    'ஏழாந்': 'Tantra 7',
    'ஏழாம்': 'Tantra 7',
    'எட்டாந்': 'Tantra 8',
    'எட்டாம்': 'Tantra 8',
    'ஒன்பதாந்': 'Tantra 9',
    'ஒன்பதாம்': 'Tantra 9',
}


def parse_tantra_ranges(raw: str) -> List[Tuple[int, int, str]]:
    """Return [(start_n, end_n, label)] derived from <h3> headers like
    `பாயிரம் (1-112)` or `முதல் தந்திரம் (113-336)`."""
    ranges = []
    for m in re.finditer(r'<h3[^>]*>([^<]+)</h3>', raw):
        text = m.group(1).strip().replace('\xa0', ' ')
        rng = re.search(r'\((\d+)[\s\-–—]+(\d+)\)', text)
        if not rng:
            continue
        start_n = int(rng.group(1))
        end_n = int(rng.group(2))
        label = ''
        for tok, lab in TANTRA_LABELS.items():
            if tok in text:
                label = lab
                break
        if not label:
            label = re.sub(r'\(.*?\)', '', text).strip()
        ranges.append((start_n, end_n, label))
    return ranges


def parse_subsections(raw: str) -> List[Tuple[int, str]]:
    """Return [(offset, subsection_title)] from <strong>N.. Title</strong>."""
    out = []
    for m in re.finditer(r'<strong>\s*\.?(\d+)\.+\s*([^<\n]+?)\s*</strong>', raw):
        title = m.group(2).strip().rstrip('.')
        out.append((m.start(), title))
    return out


def tantra_for_verse(verse_n: int, ranges: List[Tuple[int, int, str]]) -> str:
    for start_n, end_n, label in ranges:
        if start_n <= verse_n <= end_n:
            return label
    return ''


def subsection_for_offset(offset: int, subs: List[Tuple[int, str]]) -> str:
    """Find the most recent <strong> subsection header before this offset."""
    title = ''
    for sub_off, sub_title in subs:
        if sub_off <= offset:
            title = sub_title
        else:
            break
    return title


# ─── Verse Extraction ───────────────────────────────────────────────────────

def extract_verses(html_path: str) -> List[ExtractedVerse]:
    with open(html_path, 'r', encoding='utf-8') as f:
        raw = f.read()

    tantra_ranges = parse_tantra_ranges(raw)
    subsections = parse_subsections(raw)

    # Anchor each verse on `(?:<br>|\n)\s*N.<br>` — verse number followed by
    # period and immediate <br>.
    verse_anchor = re.compile(
        r'(?:<br[^>]*>|\n)\s*(\d{1,4})\.\s*<br[^>]*>',
        re.IGNORECASE,
    )
    matches = list(verse_anchor.finditer(raw))

    verses: List[ExtractedVerse] = []
    for i, m in enumerate(matches):
        n = m.group(1)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body = raw[m.end():end]

        # Stop body at next `<strong>` or `<h3>` so we don't run into the
        # next subsection's intro.
        for stop_pat in (r'<strong>', r'<h3', r'<hr'):
            stop_m = re.search(stop_pat, body)
            if stop_m:
                end = m.end() + stop_m.start()
                body = raw[m.end():end]

        verse_text = clean_verse_text(html_block_to_text(body), expected_n=n)

        if verse_text and tamil_char_count(verse_text) >= 30:
            verse_n_int = int(n)
            tantra = tantra_for_verse(verse_n_int, tantra_ranges)
            sub = subsection_for_offset(m.start(), subsections)
            verses.append(ExtractedVerse(
                verse_number=n,
                classical_tamil=verse_text,
                tantra=tantra,
                subsection=sub,
            ))

    # Deduplicate: keep first appearance of each verse_number, sort numerically.
    seen = {}
    for v in verses:
        try:
            key = int(v.verse_number)
        except ValueError:
            key = v.verse_number
        if key not in seen:
            seen[key] = v
    return sorted(seen.values(),
                  key=lambda v: int(v.verse_number) if v.verse_number.isdigit() else 0)


# ─── Schema Mapping ─────────────────────────────────────────────────────────

def map_to_schema(verse: ExtractedVerse, source_url: str = "") -> dict:
    n_padded = verse.verse_number.zfill(4)
    entry = {
        "verse_id": f"THIR-{n_padded}",
        "source_text": "Thirumanthiram",
        "layer": "Spiritual",
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
        "speaker_role": "other",
        "metre": None,
        "pann": None,
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

    context = ["Author: Tirumūlar"]
    if verse.tantra:
        context.append(f"Tantra: {verse.tantra}")
    if verse.subsection:
        context.append(f"Subsection: {verse.subsection}")
    entry["cultural_context"] = '; '.join(context)
    return entry


# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Extract Thirumanthiram verses")
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
    verses = extract_verses(str(html_path))
    print(f"Extracted {len(verses)} verses")

    if args.verbose:
        for v in verses[:5]:
            preview = v.classical_tamil[:60].replace('\n', ' ')
            print(f"  THIR-{v.verse_number} ({v.tantra}, {v.subsection}): {preview}...")

    entries = [map_to_schema(v, args.source_url) for v in verses]

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = html_path.parent.parent / "processed" / f"{html_path.stem}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(entries)} entries to {output_path}")

    if verses:
        with_tantra = sum(1 for v in verses if v.tantra)
        with_sub = sum(1 for v in verses if v.subsection)
        print(f"  Verses with tantra: {with_tantra}/{len(verses)}")
        print(f"  Verses with subsection: {with_sub}/{len(verses)}")


if __name__ == "__main__":
    main()
