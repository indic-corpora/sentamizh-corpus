#!/usr/bin/env python3
"""
Sentamizh Corpus — Silappatikaram Extraction Pipeline

Extracts structured verse data from Project Madurai Silappatikaram HTML files.
Produces JSON entries conforming to the Sentamizh Corpus schema (32 fields).

Silappatikaram is a Classical Tamil epic. Pukar Kandam (Book 1) has 10
chapters (kaathai), each a continuous narrative passage rather than a
collection of independent lyric verses. We treat each chapter as a single
entry — the deliverable is one annotated narrative segment per kaathai.

Project Madurai's HTML mixes two markup styles:

    1. <h3>N. ChapterName காதை</h3>          (Chs 2-7, 9-10)
    2. plain  N. ChapterName<br>             (Chs 1, 8 — no <h3> wrapper)

Both styles are followed by a <ul> containing the chapter's verse text.

Usage:
    python extract_silappatikaram.py <html_file> [--output <output_file>]
"""

import json
import re
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple


# ─── Data Classes ───────────────────────────────────────────────────────────

@dataclass
class ExtractedChapter:
    chapter_number: str = ""
    chapter_name: str = ""
    classical_tamil: str = ""


# ─── Text Cleaning ──────────────────────────────────────────────────────────

def html_block_to_text(html_chunk: str) -> str:
    """HTML chunk → plain text with line breaks preserved."""
    text = re.sub(r'<br\s*/?>', '\n', html_chunk, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('\xa0', ' ').replace('&nbsp;', ' ')
    return text


# Tamil numerals (used as line-range markers like ௧-௭ or ௮-௧௧).
TAMIL_DIGITS = '௦௧௨௩௪௫௬௭௮௯'


def clean_chapter_text(raw: str) -> str:
    """Drop line numbers and inline citation prose, keep verse lines."""
    text = raw.replace('\xa0', ' ').replace('&nbsp;', ' ')

    lines = []
    for line in text.split('\n'):
        # Strip trailing line numbers (Arabic or Tamil)
        line = re.sub(r'\s+\d{1,4}\s*$', '', line)
        line = re.sub(rf'\s+[{TAMIL_DIGITS}]+\s*$', '', line)
        # Strip a leading "௧-௭." line-range marker that PM's print edition
        # uses to chunk the chapter into stanzas.
        line = re.sub(rf'^\s*[{TAMIL_DIGITS}]+\s*-\s*[{TAMIL_DIGITS}]+\s*\.\s*', '', line)
        line = line.strip()
        if not line:
            continue
        if re.match(r'^-{3,}$', line):
            continue
        lines.append(line)
    return '\n'.join(lines).strip()


def tamil_char_count(s: str) -> int:
    return sum(1 for c in s if 0x0B80 <= ord(c) <= 0x0BFF)


# ─── Chapter Header Detection ───────────────────────────────────────────────

# Headers wrapped in <h3>: "<h3><font...>2. மனையறம்படுத்த காதை</h3>"
H3_HEADER = re.compile(
    r'<h3[^>]*>\s*(?:<font[^>]*>)?\s*(\d+)\.\s*([^<\n]+?)\s*(?:</font>)?\s*</h3>',
    re.DOTALL,
)

# Plain headers: "\n1. மங்கல வாழ்த்துப் பாடல்<br>" or "\n8. வேனிற்காதை<br>"
PLAIN_HEADER = re.compile(
    r'(?:<br\s*/?>|<hr[^>]*>|\n)\s*(\d+)\.\s+([^<\n]{4,80}?)\s*<br',
    re.DOTALL,
)


def find_toc_end(raw: str) -> int:
    """Return the byte offset where the table-of-contents ends.

    PM lays out the TOC as a tight cluster of `<br>N. Title<br>` lines.
    We detect the cluster by walking the first ~8000 bytes and stopping
    when we hit a gap > 300 chars between consecutive plain numbered
    headers. The cutoff is set to the END of the last TOC entry's line —
    just before the next major HTML break — so that real `<h3>` chapter
    headers immediately following the TOC are not accidentally filtered."""
    entries = []
    pat = re.compile(r'(?:<br[^>]*>|\n)\s*(\d+)\.\s+\S')
    for m in pat.finditer(raw[:8000]):
        entries.append(m)
    if len(entries) < 3:
        return 0
    last = entries[0]
    for m in entries[1:]:
        if m.start() - last.start() < 300:
            last = m
        else:
            break
    # End the TOC at the end-of-line `<br>` after the last TOC entry's title.
    after = raw.find('<br', last.end())
    if after != -1 and after - last.end() < 200:
        return after + len('<br>')
    return last.end()


def find_chapters(raw: str) -> List[Tuple[int, int, str, str]]:
    """Return [(start_offset, end_offset, chapter_number, chapter_name)],
    one tuple per chapter present in this file. Detects both <h3>-wrapped
    headers (Chs 2-7, 9-10) and plain `\\nN. ...<br>` headers (Chs 1, 8).
    TOC entries at the top of the file are skipped."""
    toc_end = find_toc_end(raw)

    candidates = []
    for m in H3_HEADER.finditer(raw):
        try:
            n = int(m.group(1))
        except ValueError:
            continue
        if not (1 <= n <= 12):
            continue
        if m.start() <= toc_end:
            continue
        candidates.append((m.start(), n, m.group(2).strip().rstrip('.'), 'h3'))

    # Plain `N. காதை`-style headers: same offset filter
    chapter_word = re.compile(r'காதை|வரி|பாடல்|kaathai', re.IGNORECASE)
    for m in PLAIN_HEADER.finditer(raw):
        try:
            n = int(m.group(1))
        except ValueError:
            continue
        if not (1 <= n <= 12):
            continue
        if m.start() <= toc_end:
            continue
        title = m.group(2).strip().rstrip('.')
        if not chapter_word.search(title):
            continue
        candidates.append((m.start(), n, title, 'plain'))

    # Deduplicate: prefer h3 over plain, then earliest offset
    candidates.sort(key=lambda c: (c[1], c[3] != 'h3', c[0]))
    seen = {}
    for offset, n, name, kind in candidates:
        if n not in seen:
            seen[n] = (offset, name, kind)

    sorted_chs = sorted(seen.items(), key=lambda kv: kv[1][0])
    result = []
    for i, (n, (offset, name, kind)) in enumerate(sorted_chs):
        next_offset = sorted_chs[i + 1][1][0] if i + 1 < len(sorted_chs) else len(raw)
        result.append((offset, next_offset, str(n), name))
    return result


# ─── Verse Extraction ───────────────────────────────────────────────────────

def extract_chapter_text(body: str) -> str:
    """Pull the verse text out of the chapter body. PM lays the verse out in
    one or more <ul> blocks; the FIRST <ul> contains the unbroken Tamil
    verse, while subsequent <ul>s contain commentary citations and re-quoted
    line ranges. We return the first substantial Tamil-heavy <ul>."""
    # Try the first <ul> that has substantial Tamil content.
    best_text = ''
    best_score = 0
    for ul_match in re.finditer(r'<ul\b[^>]*>(.*?)</ul>', body, re.DOTALL):
        chunk = ul_match.group(1)
        text = clean_chapter_text(html_block_to_text(chunk))
        score = tamil_char_count(text)
        if score > best_score and score >= 60:
            best_text = text
            best_score = score
            # Most chapters' first big <ul> is the verse body — once we find
            # a long enough one we stop, to avoid pulling in commentary.
            if score >= 500:
                break
    return best_text


def extract_chapters(html_path: str) -> List[ExtractedChapter]:
    with open(html_path, 'r', encoding='utf-8') as f:
        raw = f.read()

    chapters = find_chapters(raw)
    extracted: List[ExtractedChapter] = []
    for start, end, n, name in chapters:
        body = raw[start:end]
        verse = extract_chapter_text(body)
        if verse and tamil_char_count(verse) >= 60:
            extracted.append(ExtractedChapter(
                chapter_number=n,
                chapter_name=name,
                classical_tamil=verse,
            ))
    return extracted


# ─── Schema Mapping ─────────────────────────────────────────────────────────

def map_to_schema(ch: ExtractedChapter, source_url: str = "") -> dict:
    n_padded = ch.chapter_number.zfill(3)
    entry = {
        "verse_id": f"SILA-{n_padded}",
        "source_text": "Silappatikaram",
        "layer": "Epic",
        "period": "2nd–6th century CE",
        "verse_number": ch.chapter_number,
        "classical_tamil": ch.classical_tamil,
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

    context = []
    if ch.chapter_name:
        context.append(f"Kaathai (chapter): {ch.chapter_name}")
    context.append(f"Book: Pukar Kandam (1 of 3)")
    context.append("Author: Ilango Adigal")
    entry["cultural_context"] = '; '.join(context)

    return entry


# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Extract Silappatikaram chapters")
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
    chapters = extract_chapters(str(html_path))
    print(f"Extracted {len(chapters)} chapters")

    if args.verbose:
        for ch in chapters:
            preview = ch.classical_tamil[:80].replace('\n', ' ')
            print(f"  Ch {ch.chapter_number} ({ch.chapter_name}): {preview}...")

    entries = [map_to_schema(ch, args.source_url) for ch in chapters]

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
