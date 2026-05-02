#!/usr/bin/env python3
"""
Sentamizh Corpus — Manimekalai Extraction Pipeline

Extracts structured verse data from Project Madurai Manimekalai HTML files.
Produces JSON entries conforming to the Sentamizh Corpus schema (32 fields).

Manimekalai is a 5,000-line Buddhist epic by Cīttalai Cāttanār. PM ships it
as three files:

    Manimekalai.html               the main poem text (30 chapters/kāthais
                                   plus a 00-prologue, ~490 stanzas total)
    Manimekalai_Summary_Part1.html scholarly research summaries (prose,
                                   not verse — extractor produces no entries)
    Manimekalai_Summary_Part2.html more scholarly summaries (likewise)

Within Manimekalai.html each chapter follows the structure:

    <h3><font color="blue"> N. ChapterName</font></h3>
    <table border=0>
      <tr><td width=450>
      verse_line<br>
      verse_line<br>
      ...
      verse_line  <td valign=bottom> CC-LLL</tr>
      <tr><td>...next stanza...<td valign=bottom> CC-LLL+10</tr>
      ...
    </table>

Each <tr> is one stanza of ~10 lines. The trailing `CC-LLL` marker gives
the chapter number and the running line-end position within the chapter.
We treat each stanza as one corpus entry.

Usage:
    python extract_manimekalai.py <html_file> [--output <output_file>]
"""

import json
import re
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class ExtractedStanza:
    chapter_number: str = ""
    chapter_name: str = ""
    line_end: str = ""               # e.g. "010", "072"
    classical_tamil: str = ""


# ─── Text Cleaning ──────────────────────────────────────────────────────────

def html_block_to_text(html_chunk: str) -> str:
    text = re.sub(r'<br\s*/?>', '\n', html_chunk, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('\xa0', ' ').replace('&nbsp;', ' ')
    return text


def clean_stanza_text(raw: str) -> str:
    text = raw.replace('\xa0', ' ').replace('&nbsp;', ' ')
    lines = []
    for line in text.split('\n'):
        # Strip trailing CC-LLL line markers
        line = re.sub(r'\s+\d{2}-\d{3}\s*$', '', line)
        # Strip trailing single-line numbers
        line = re.sub(r'\s+\d{1,4}\.?\s*$', '', line)
        line = line.strip()
        if line and not re.match(r'^-{3,}$', line):
            lines.append(line)
    return '\n'.join(lines).strip()


def tamil_char_count(s: str) -> int:
    return sum(1 for c in s if 0x0B80 <= ord(c) <= 0x0BFF)


# ─── Chapter Detection ──────────────────────────────────────────────────────

# Permissive h3 chapter header — handles "N. Title", "N Title" (no dot), and
# embedded <font> tags. Matches multi-line bodies inside <h3>.
H3_CHAPTER = re.compile(
    r'<h3[^>]*>\s*(?:<font[^>]*>)?\s*(\d{1,2})[.\s]+([^<\n]+?)(?:</font>)?\s*</h3>',
    re.DOTALL,
)

# Some chapter h3s drop the leading number entirely (Project Madurai source
# inconsistency: chapters 9, 14, 26 in the current Manimekalai.html). Match
# any <h3> whose text contains "காதை" (chapter) so we can still claim the
# region for chapter detection.
H3_CHAPTER_NAMED = re.compile(
    r'<h3[^>]*>\s*(?:<font[^>]*>)?\s*([^<\n]*?காதை[^<\n]*?)(?:</font>)?\s*</h3>',
    re.DOTALL,
)

# Stanza pattern: a <tr> ending in <td valign=bottom> CC-LLL marker.
STANZA_PATTERN = re.compile(
    r'<tr>?\s*<td[^>]*>\s*(.*?)\s*<td\s+valign=bottom[^>]*>\s*(\d{2})-(\d{3})',
    re.DOTALL | re.IGNORECASE,
)


# ─── Main Extraction ────────────────────────────────────────────────────────

def is_summary_file(filename: str) -> bool:
    """Summary parts contain only prose research, no verse content."""
    return 'Summary' in filename


def extract_stanzas(html_path: str) -> List[ExtractedStanza]:
    if is_summary_file(Path(html_path).name):
        # Skip — these contain prose research, not verses.
        return []

    with open(html_path, 'r', encoding='utf-8') as f:
        raw = f.read()

    # Slice on chapter headers — first pass picks up `<h3>N. Title</h3>`.
    chapter_headers = []
    numbered_offsets = set()
    for m in H3_CHAPTER.finditer(raw):
        try:
            n = int(m.group(1))
        except ValueError:
            continue
        if 0 <= n <= 30:
            title = m.group(2).strip().rstrip('.')
            chapter_headers.append((m.start(), m.end(), str(n).zfill(2), title))
            numbered_offsets.add(m.start())

    # Second pass: catch chapters whose h3 dropped the number ("காதை"-only).
    # Infer the chapter number from the chapter immediately before/after this
    # h3 in document order — Manimekalai chapters appear sequentially.
    chapter_headers.sort(key=lambda c: c[0])
    inferred = []
    for m in H3_CHAPTER_NAMED.finditer(raw):
        if m.start() in numbered_offsets:
            continue
        title_raw = m.group(1).strip()
        # Skip h3s whose title still has a number prefix (already captured)
        if re.match(r'^\s*\d', title_raw):
            continue
        # Skip the document title (matches "சீத்தலைச்சாத்தனார்" etc.)
        if 'அருளிய' in title_raw or 'ஆசிரியர்' in title_raw or 'cIttalai' in title_raw:
            continue
        # Find the previous chapter number in document order
        prev_n = -1
        for ch_start, _, ch_n, _ in chapter_headers:
            if ch_start < m.start():
                prev_n = int(ch_n)
            else:
                break
        if prev_n >= 0 and prev_n + 1 <= 30:
            inferred.append((m.start(), m.end(), str(prev_n + 1).zfill(2), title_raw.rstrip('.')))

    chapter_headers.extend(inferred)
    chapter_headers.sort(key=lambda c: c[0])

    if not chapter_headers:
        return []

    stanzas: List[ExtractedStanza] = []

    # Chapter 00 (prologue / patikam) appears BEFORE the first <h3> chapter
    # header — it has no h3, just stanzas with `00-NNN` markers. Carve out
    # the prologue region from the start of the file to the first h3.
    pre_first = raw[:chapter_headers[0][0]]
    for vm in STANZA_PATTERN.finditer(pre_first):
        chap, line_end = vm.group(2), vm.group(3)
        if chap != '00':
            continue
        stanza_text = clean_stanza_text(html_block_to_text(vm.group(1)))
        if stanza_text and tamil_char_count(stanza_text) >= 30:
            stanzas.append(ExtractedStanza(
                chapter_number='00',
                chapter_name='பதிகம் (Prologue)',
                line_end=line_end,
                classical_tamil=stanza_text,
            ))

    # Per-chapter stanzas
    for i, (start, end_h3, n, title) in enumerate(chapter_headers):
        next_start = chapter_headers[i + 1][0] if i + 1 < len(chapter_headers) else len(raw)
        body = raw[end_h3:next_start]

        for vm in STANZA_PATTERN.finditer(body):
            chap = vm.group(2)
            line_end = vm.group(3)
            # If the chapter marker on this row doesn't match the h3, skip
            # — most likely a stray pattern from a different region.
            if chap != n:
                continue
            stanza_text = clean_stanza_text(html_block_to_text(vm.group(1)))
            if stanza_text and tamil_char_count(stanza_text) >= 30:
                stanzas.append(ExtractedStanza(
                    chapter_number=n,
                    chapter_name=title,
                    line_end=line_end,
                    classical_tamil=stanza_text,
                ))

    return stanzas


# ─── Schema Mapping ─────────────────────────────────────────────────────────

def map_to_schema(stanza: ExtractedStanza, running_n: int, source_url: str = "") -> dict:
    entry = {
        "verse_id": f"MANI-{running_n:04d}",
        "source_text": "Manimekalai",
        "layer": "Epic",
        "period": "2nd–6th century CE",
        "verse_number": f"{stanza.chapter_number}.{stanza.line_end}",
        "classical_tamil": stanza.classical_tamil,
        "modern_tamil": None,
        "english": None,
        "source_url": source_url if source_url else None,
        "difficulty": "archaic",

        "thinai": None,
        "turai": None,
        "akam_or_puram": None,
        "karu": None,
        "uri": None,
        "ullurai": None,
        "speaker_role": "narrator",
        "metre": None,
        "pann": None,
        "dhvani_layer": None,

        "rasa_primary": None,
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

    context = ["Author: Cīttalai Cāttanār"]
    if stanza.chapter_name:
        context.append(f"Chapter {stanza.chapter_number}: {stanza.chapter_name}")
    if stanza.line_end:
        context.append(f"Lines: ending at {stanza.line_end}")
    entry["cultural_context"] = '; '.join(context)
    return entry


# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Extract Manimekalai stanzas")
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
    if is_summary_file(html_path.name):
        print("  (Summary file — contains scholarly prose, not verse; skipping.)")
    stanzas = extract_stanzas(str(html_path))
    print(f"Extracted {len(stanzas)} stanzas")

    if args.verbose:
        for s in stanzas[:3]:
            preview = s.classical_tamil[:60].replace('\n', ' ')
            print(f"  Ch {s.chapter_number} ({s.chapter_name}, l. {s.line_end}): {preview}...")

    entries = [map_to_schema(s, i + 1, args.source_url) for i, s in enumerate(stanzas)]

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = html_path.parent.parent / "processed" / f"{html_path.stem}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(entries)} entries to {output_path}")

    if stanzas:
        chapters = sorted(set(s.chapter_number for s in stanzas))
        print(f"  Chapters covered: {len(chapters)} ({chapters[0]} - {chapters[-1]})")


if __name__ == "__main__":
    main()
