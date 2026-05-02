#!/usr/bin/env python3
"""
Sentamizh Corpus — Divya Prabandham Extraction Pipeline

Extracts structured verse data from Project Madurai Divya Prabandham HTML
files. Produces JSON entries conforming to the Sentamizh Corpus schema
(32 fields).

Nalāyira Divya Prabandham — 4,000 verses of Vaishnava Bhakti hymns by the
twelve Āḻvārs, plus the Iramanusa Nūṟṟantāti by Thiruvaranga Amudhanār.
PM splits the corpus into seven HTML files:

    Mudhal_Ayiram_1     verses 1-473
    Mudhal_Ayiram_2     verses 474-947
    Periya_Thirumozhi_1 verses 948-1447   (Thirumangai)
    Periya_Thirumozhi_2 verses 1448-2031  (Thirumangai)
    Siru_Thirumurai     verses 2032-2790  (Thirumangai short hymns + Iramanusa Nūṟṟantāti)
    Iramanusa_1         verses 2791-3342  (Nammāḻvār Tiruvāymoḻi pt 1)
    Iramanusa_2         verses 3343-4000  (Nammāḻvār Tiruvāymoḻi pt 2)

Verse markup is consistent across all files — each verse begins with
`<br>N <br>` (or `N: <br>`) and is followed by 4-12 lines of Tamil text
ending in another `<br>` separator before the next verse anchor.

Usage:
    python extract_divya_prabandham.py <html_file> [--output <output_file>]
"""

import json
import re
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class ExtractedVerse:
    verse_number: str = ""
    classical_tamil: str = ""
    section_title: str = ""
    poet: str = ""


# ─── Text Cleaning ──────────────────────────────────────────────────────────

def html_block_to_text(html_chunk: str) -> str:
    text = re.sub(r'<br\s*/?>', '\n', html_chunk, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('\xa0', ' ').replace('&nbsp;', ' ')
    return text


def clean_verse_text(raw: str) -> str:
    """Strip trailing line numbers (Arabic and pathigam-decade-position
    triples like `1.1.3`) and other noise."""
    text = raw.replace('\xa0', ' ').replace('&nbsp;', ' ')
    lines = []
    for line in text.split('\n'):
        # Strip trailing pathigam markers like "1.1.3"
        line = re.sub(r'\s+\d+(?:\.\d+){1,2}\s*$', '', line)
        # Strip trailing single line-numbers
        line = re.sub(r'\s+\d{1,4}\.?\s*$', '', line)
        line = line.strip()
        if not line:
            continue
        if re.match(r'^[\(\)\[\]\.\,]+$', line):
            continue
        lines.append(line)
    return '\n'.join(lines).strip()


def tamil_char_count(s: str) -> int:
    return sum(1 for c in s if 0x0B80 <= ord(c) <= 0x0BFF)


# ─── File-Specific Configuration ────────────────────────────────────────────

# Plausible verse-number range for each file. Values outside the range are
# false positives (typically `(2)` repetition markers or pathigam.decade.pos
# triples that look like single numbers).
FILE_RANGES = {
    'Divya_Prabandham_Mudhal_Ayiram_1':     (1, 473),
    'Divya_Prabandham_Mudhal_Ayiram_2':     (474, 947),
    'Divya_Prabandham_Periya_Thirumozhi_1': (948, 1447),
    'Divya_Prabandham_Periya_Thirumozhi_2': (1448, 2031),
    'Divya_Prabandham_Siru_Thirumurai':     (2032, 2790),
    'Divya_Prabandham_Iramanusa_1':         (2791, 3342),
    'Divya_Prabandham_Iramanusa_2':         (3343, 4000),
}


def file_verse_range(filename: str) -> Tuple[int, int]:
    stem = Path(filename).stem
    return FILE_RANGES.get(stem, (1, 4000))


# ─── Verse Extraction ───────────────────────────────────────────────────────

# Anchor: `<br>N <br>` or `<br>N. <br>` or `N: <br>` — number alone on a line
# followed by a <br>. Tolerates optional `:` or `.` suffix.
VERSE_ANCHOR = re.compile(
    r'(?:<br[^>]*>|\n)\s*(\d{1,4})[:\.]?\s*<br[^>]*>',
    re.DOTALL,
)


# A section title is typically the most recent <h3> or <strong>...</strong>
# preceding a verse. We collect both as candidate titles.
SECTION_HEADERS = re.compile(
    r'<h3[^>]*>(.*?)</h3>|<strong>([^<]+)</strong>',
    re.DOTALL,
)


def section_title_at(offset: int, headers: List[Tuple[int, str]]) -> str:
    """Return the most recent header before this offset."""
    title = ''
    for h_offset, h_title in headers:
        if h_offset <= offset:
            title = h_title
        else:
            break
    return title


def extract_verses(html_path: str) -> List[ExtractedVerse]:
    with open(html_path, 'r', encoding='utf-8') as f:
        raw = f.read()

    fname = Path(html_path).name
    n_min, n_max = file_verse_range(fname)

    # Collect headers (h3 or <strong>) for cultural_context
    headers: List[Tuple[int, str]] = []
    for m in SECTION_HEADERS.finditer(raw):
        text = m.group(1) or m.group(2) or ''
        text = re.sub(r'<[^>]+>', '', text).strip().replace('\xa0', ' ')
        text = re.sub(r'\s+', ' ', text)
        if text:
            headers.append((m.start(), text))

    # Find verse anchors and slice into bodies
    matches = list(VERSE_ANCHOR.finditer(raw))
    valid = []
    for m in matches:
        try:
            n = int(m.group(1))
        except ValueError:
            continue
        if n_min <= n <= n_max:
            valid.append(m)

    verses: List[ExtractedVerse] = []
    for i, m in enumerate(valid):
        n = int(m.group(1))
        end = valid[i + 1].start() if i + 1 < len(valid) else len(raw)
        body = raw[m.end():end]

        # Stop at the next <h3>/<hr> if it falls before the next verse anchor
        for stop_pat in (r'<h3', r'<hr'):
            stop_m = re.search(stop_pat, body)
            if stop_m:
                end = m.end() + stop_m.start()
                body = raw[m.end():end]

        verse_text = clean_verse_text(html_block_to_text(body))
        if not verse_text or tamil_char_count(verse_text) < 20:
            continue

        section = section_title_at(m.start(), headers)
        verses.append(ExtractedVerse(
            verse_number=str(n),
            classical_tamil=verse_text,
            section_title=section,
        ))

    # Dedup by verse_number, sort
    seen = {}
    for v in verses:
        key = int(v.verse_number)
        if key not in seen:
            seen[key] = v
    return sorted(seen.values(), key=lambda v: int(v.verse_number))


# ─── Schema Mapping ─────────────────────────────────────────────────────────

def map_to_schema(verse: ExtractedVerse, source_url: str = "") -> dict:
    n_padded = verse.verse_number.zfill(4)
    entry = {
        "verse_id": f"DIVA-{n_padded}",
        "source_text": "Divya Prabandham",
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

    context = []
    if verse.section_title:
        context.append(f"Section: {verse.section_title}")
    if verse.poet:
        context.append(f"Poet: {verse.poet}")
    if context:
        entry["cultural_context"] = '; '.join(context)
    return entry


# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Extract Divya Prabandham verses")
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
    n_min, n_max = file_verse_range(html_path.name)
    print(f"Expected verse range: {n_min}-{n_max}")

    verses = extract_verses(str(html_path))
    print(f"Extracted {len(verses)} verses")

    if args.verbose:
        for v in verses[:3]:
            preview = v.classical_tamil[:60].replace('\n', ' ')
            print(f"  DIVA-{v.verse_number} ({v.section_title[:40]}): {preview}...")

    entries = [map_to_schema(v, args.source_url) for v in verses]

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = html_path.parent.parent / "processed" / f"{html_path.stem}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(entries)} entries to {output_path}")


if __name__ == "__main__":
    main()
