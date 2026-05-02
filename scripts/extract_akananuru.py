#!/usr/bin/env python3
"""
Sentamizh Corpus — Akananuru Extraction Pipeline

Extracts structured verse data from Project Madurai Akananuru HTML files.
Produces JSON entries conforming to the Sentamizh Corpus schema (32 fields).

Akananuru is Sangam Akam (interior love) poetry, 400 verses.

Three editions, three different markups (Project Madurai inconsistency):

  Ed1 (verses 1-120, Po.Vé. Cōmacuntaranār commentary):
    <center><h3>செய்யுள் N</h3></center>
    திணை: ...
    துறை: ...
    [prose intro]
    <ul>verse_text</ul>
    [commentary]

  Ed2 (verses 121-300, Nāṭṭār commentary):
    <strong>N. tinai[turai]</strong>
    <ul>verse_text</ul>
    [commentary]

  Ed3 (verses 301-400, Nāṭṭār commentary):
    <strong>N. tinai</strong>
    <ul>verse_text</ul>
    [commentary]

Usage:
    python extract_akananuru.py <html_file> [--output <output_file>]
"""

import json
import re
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:
    print("Installing beautifulsoup4...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "beautifulsoup4", "--break-system-packages", "-q"])
    from bs4 import BeautifulSoup, NavigableString, Tag


# ─── Data Classes ───────────────────────────────────────────────────────────

@dataclass
class ExtractedVerse:
    """Raw extracted verse data, before schema mapping."""
    verse_number: str = ""
    classical_tamil: str = ""
    tinai: str = ""
    turai: str = ""
    poet: str = ""
    title: str = ""


# ─── Text Cleaning ──────────────────────────────────────────────────────────

def html_block_to_text(html_chunk: str) -> str:
    """Convert an HTML chunk (typically a <ul> body) to plain text with
    line breaks preserved. Strips embedded line numbers and the trailing
    poet attribution that often follows the verse body in Ed2."""
    # Replace <br> with newlines before stripping tags so the line structure
    # of the verse is preserved.
    text = re.sub(r'<br\s*/?>', '\n', html_chunk, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('\xa0', ' ').replace('&nbsp;', ' ')
    return text


def clean_verse_text(raw: str) -> str:
    """Strip line numbers, leading verse-number markers, and poet attribution."""
    text = raw.replace('\xa0', ' ').replace('&nbsp;', ' ')

    # Drop the poet attribution line ("- Poet name." or "-Poet name.") that
    # Ed2 appends after the verse body. Detected by leading whitespace + dash.
    text = re.sub(r'\n\s*-\s*[^\n]+\.\s*$', '', text)

    lines = []
    for line in text.split('\n'):
        # Strip embedded right-side line numbers like "  10" / "    5".
        line = re.sub(r'\s+\d{1,3}\s*$', '', line)
        # Strip leading line-number prefixes like "1நாம்நகை..." (Ed2 quirk:
        # textual variants are flagged with a small superscript-style digit
        # prepended to the word; only strip when the digit is 1-3).
        line = re.sub(r'^\s*[1-3](?=[\u0B80-\u0BFF])', '', line)
        line = line.strip()
        # Filter (N) trailing markers
        line = re.sub(r'^\(\d+\)\s*$', '', line)
        if line and not re.match(r'^-{3,}$', line):
            lines.append(line)
    return '\n'.join(lines).strip()


def parse_tinai_turai(raw: str) -> Tuple[str, str]:
    """Parse a tinai/turai header line. Used for Ed2 (N. tinai[turai])."""
    raw = raw.replace('\xa0', ' ').strip()
    tinai = ''
    turai = ''

    # Ed2 / Ed3 style: "N. tinai" or "N. tinai[turai]"
    m = re.match(r'^\s*\d+\.\s*([^\[]+?)\s*\[([^\]]+)\]', raw)
    if m:
        tinai = m.group(1).strip().rstrip('.')
        turai = m.group(2).strip().rstrip('.')
        return tinai, turai
    m = re.match(r'^\s*\d+\.\s*(.+)$', raw)
    if m:
        tinai = m.group(1).strip().rstrip('.')
        return tinai, ''

    # Ed1 style: separate "திணை: X" and "துறை: Y" lines.
    # Some PM transcriptions spell tiṇai as "திணை" (retroflex ண) and others
    # as "தினை" (alveolar ன); accept either.
    m = re.search(r'தி[ணன]ை[:\s]*([^\n.]+)', raw)
    if m:
        tinai = m.group(1).strip().rstrip(';')
    m = re.search(r'துறை[:\s]*([^\n.]+)', raw)
    if m:
        turai = m.group(1).strip().rstrip(';')
    return tinai, turai


def extract_poet_attribution(html_chunk: str) -> str:
    """Look for the trailing poet attribution line in the verse block."""
    text = html_block_to_text(html_chunk)
    m = re.search(r'-\s*([^\n.]+?)\.\s*$', text)
    if m:
        candidate = m.group(1).strip()
        # Reject obvious non-poet lines (only a digit, bracket, etc.)
        if 3 < len(candidate) < 80 and any(0x0B80 <= ord(c) <= 0x0BFF for c in candidate):
            return candidate
    return ''


def tamil_char_count(s: str) -> int:
    return sum(1 for c in s if 0x0B80 <= ord(c) <= 0x0BFF)


# ─── Edition-Specific Extractors ────────────────────────────────────────────

def extract_ed1(raw: str) -> List[ExtractedVerse]:
    """Ed1: <h3>செய்யுள் N</h3> followed by tinai/turai prose then a <ul>
    containing the verse text."""
    verses: List[ExtractedVerse] = []

    # Slice the document on "செய்யுள் N" h3 anchors; segment[i] is the body
    # between anchor[i] and anchor[i+1].
    anchor = re.compile(
        r'<h3[^>]*>\s*செய்யுள்\s*(\d+)\s*</h3>',
        re.IGNORECASE,
    )
    matches = list(anchor.finditer(raw))
    for i, m in enumerate(matches):
        n = m.group(1)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body = raw[m.end():end]

        # Pull tinai/turai from the prose before the first <ul>
        head_split = re.search(r'<ul\b', body)
        head = body[:head_split.start()] if head_split else body
        head_text = html_block_to_text(head)
        tinai, turai = parse_tinai_turai(head_text)

        # The verse body is the longest <ul> in this segment that contains
        # substantial Tamil text. Most segments have several <ul>s — Tolkappiyam
        # citations, the verse itself, and commentary citations. The verse is
        # always by far the longest.
        verse_text = ''
        best_len = 0
        for ul in re.finditer(r'<ul\b[^>]*>(.*?)</ul>', body, re.DOTALL):
            chunk = ul.group(1)
            chars = tamil_char_count(chunk)
            if chars > best_len and chars >= 40:
                cleaned = clean_verse_text(html_block_to_text(chunk))
                if cleaned:
                    verse_text = cleaned
                    best_len = chars

        if verse_text:
            verses.append(ExtractedVerse(
                verse_number=n,
                classical_tamil=verse_text,
                tinai=tinai,
                turai=turai,
            ))
    return verses


def extract_plain_numbered(raw: str, found_nums: set, n_range: range) -> List[ExtractedVerse]:
    """Fallback for verses with NO <strong> wrapper — common in Ed3 verses
    303-316 and 349/364, where the markup degenerates to:

        N. tinai<br>
        [turai]<br>
        <br>
        verse_line_1<br>
        verse_line_2<br>
        ...verse_lines... <br>
        ----------<br>

    We anchor on `\\nN.\\s+TamilWord<br>` and grab everything up to the next
    verse number or a horizontal rule.
    """
    verses: List[ExtractedVerse] = []
    plain_pat = re.compile(
        r'(?:<br[^>]*>|\n)\s*(\d{3,4})\.\s+([\u0B80-\u0BFF][^<\n]*?)<br',
        re.DOTALL,
    )
    matches = [
        m for m in plain_pat.finditer(raw)
        if int(m.group(1)) in n_range and int(m.group(1)) not in found_nums
    ]
    for i, m in enumerate(matches):
        n = m.group(1)
        if int(n) in found_nums:
            continue
        tinai = m.group(2).strip().rstrip('.')

        # Body runs up to either the next plain anchor at offset
        # plain_pat.search(raw, m.end()) OR the next horizontal rule.
        next_m = plain_pat.search(raw, m.end())
        end = next_m.start() if next_m else len(raw)
        # Cap at next ----------- or next <strong>N.\s
        for stop_pat in [
            re.compile(r'-{5,}'),
            re.compile(r'<strong>\s*\d+\.'),
        ]:
            stop = stop_pat.search(raw, m.end(), end)
            if stop:
                end = stop.start()
        body = raw[m.end():end]

        # Pull turai
        turai = ''
        turai_m = re.search(r'\[([^\]]+)\]', body[:600])
        if turai_m:
            turai = turai_m.group(1).strip().rstrip('.')

        # Strip the [turai] line(s) and the leading whitespace from the
        # verse body, leaving just the Tamil verse lines.
        body_clean = re.sub(r'\[[^\]]+\]\s*<br[^>]*>', '', body, count=1)
        body_clean = re.sub(r'\(.*?விளக்கம்.*?\).*', '', body_clean, flags=re.DOTALL)

        verse_text = clean_verse_text(html_block_to_text(body_clean))
        # Strip any leading attribution/turai prose by dropping leading lines
        # that don't look like verse (Tamil-heavy, < 80 chars).
        lines = verse_text.split('\n')
        kept = []
        seen_verse = False
        for line in lines:
            tamil = tamil_char_count(line)
            if not seen_verse:
                if tamil >= 8 and len(line) < 90:
                    seen_verse = True
                    kept.append(line)
                continue
            # After verse start, stop at obvious commentary markers
            if re.match(r'^\s*\(', line) or 'விளக்கம்' in line or 'உரை' in line:
                break
            kept.append(line)
        verse_text = '\n'.join(kept).strip()

        if verse_text and tamil_char_count(verse_text) >= 30:
            verses.append(ExtractedVerse(
                verse_number=n,
                classical_tamil=verse_text,
                tinai=tinai,
                turai=turai,
            ))
            found_nums.add(int(n))
    return verses


def extract_ed2_or_ed3(raw: str) -> List[ExtractedVerse]:
    """Ed2 / Ed3: <strong>N. tinai...</strong> followed by the verse <ul>.

    Ed2 markup is inconsistent across Part1 and Part2:

    Part1:  <strong> N. tinai<br>
            [turai prose]<br>
            <ul><br>verse_lines<br>...</strong>...

    Part2:  <strong> N. tinai<br></strong>
            [turai]<br>
            <ul><strong> <br>verse_lines</strong>...

    Ed3:    <strong>N. tinai</strong>
            <ul>verse_lines</ul>

    Strategy: anchor on `<strong>\\s*N\\.` only; then within the segment, pull
    the tinai (non-tag text up to <br> or [), the turai (in brackets), and
    the verse body from the next <ul> after stripping any nested <strong>.
    """
    verses: List[ExtractedVerse] = []

    anchor = re.compile(r'<strong>\s*(\d+)\.\s*', re.DOTALL)
    matches = [
        m for m in anchor.finditer(raw)
        if 100 <= int(m.group(1)) <= 450
    ]

    for i, m in enumerate(matches):
        n = m.group(1)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body = raw[m.end():end]

        # Tinai: take everything up to the first <, [, or newline.
        tinai_m = re.match(r'\s*([^\[<\n]+)', body)
        tinai = tinai_m.group(1).strip().rstrip('.') if tinai_m else ''

        # Turai: first [...] in the next ~600 chars.
        turai_m = re.search(r'\[([^\]]+)\]', body[:800])
        turai = turai_m.group(1).strip().rstrip('.') if turai_m else ''

        # Verse body: first <ul>...</ul>
        ul_m = re.search(r'<ul\b[^>]*>(.*?)</ul>', body, re.DOTALL)
        if not ul_m:
            continue
        chunk = ul_m.group(1)

        # Strip any nested <strong>/</strong> tags (Ed2 Part2 wraps verses
        # in an inner <strong>; Ed2 Part1 closes </strong> mid-verse).
        chunk = re.sub(r'</?strong[^>]*>', '', chunk, flags=re.IGNORECASE)

        poet = extract_poet_attribution(chunk)
        verse_text = clean_verse_text(html_block_to_text(chunk))

        if verse_text and tamil_char_count(verse_text) >= 30:
            verses.append(ExtractedVerse(
                verse_number=n,
                classical_tamil=verse_text,
                tinai=tinai,
                turai=turai,
                poet=poet,
            ))
    return verses


# ─── Main Extraction Dispatcher ─────────────────────────────────────────────

def detect_edition(filename: str) -> str:
    """Return 'ed1' / 'ed2' / 'ed3' from the filename."""
    f = filename.lower()
    if 'ed1' in f:
        return 'ed1'
    if 'ed2' in f:
        return 'ed2'
    if 'ed3' in f:
        return 'ed3'
    return 'ed1'  # default


def extract_verses(html_path: str) -> List[ExtractedVerse]:
    with open(html_path, 'r', encoding='utf-8') as f:
        raw = f.read()

    edition = detect_edition(Path(html_path).name)
    if edition == 'ed1':
        verses = extract_ed1(raw)
    else:
        verses = extract_ed2_or_ed3(raw)

        # Plain-numbered fallback for verses without <strong> wrapping.
        found_nums = {int(v.verse_number) for v in verses if v.verse_number.isdigit()}
        if found_nums:
            n_range = range(min(found_nums), max(found_nums) + 1)
        else:
            n_range = range(100, 451)
        verses.extend(extract_plain_numbered(raw, found_nums, n_range))

    # Sort by verse number
    verses.sort(key=lambda v: int(v.verse_number) if v.verse_number.isdigit() else 0)
    return verses


# ─── Schema Mapping ─────────────────────────────────────────────────────────

# Schema enum values are English Latin transliterations of the Tamil thinai
# names. Akananuru sources spell them in Tamil; we map here.
TINAI_TAMIL_TO_ENGLISH = {
    'குறிஞ்சி': 'Kurinji',
    'முல்லை': 'Mullai',
    'மருதம்': 'Marutham',
    'நெய்தல்': 'Neytal',
    'பாலை': 'Palai',
    'கைக்கிளை': 'Kaikkilai',
    'பெருந்திணை': 'Peruntinai',
}


def normalize_thinai(tamil_thinai: str) -> Optional[str]:
    """Convert a Tamil thinai name (possibly with surrounding whitespace,
    punctuation, or invisible joiner/non-joiner characters) to the English
    schema enum value, or None if not recognized."""
    if not tamil_thinai:
        return None
    # Strip zero-width joiners (U+200C, U+200D) that can appear in PM source
    # text and break exact equality with our lookup keys.
    cleaned = re.sub(r'[\u200B-\u200D\uFEFF]', '', tamil_thinai)
    cleaned = cleaned.strip().rstrip('.').rstrip(',').strip()
    # Try exact match first
    if cleaned in TINAI_TAMIL_TO_ENGLISH:
        return TINAI_TAMIL_TO_ENGLISH[cleaned]
    # Fallback: substring match
    for tam, eng in TINAI_TAMIL_TO_ENGLISH.items():
        if tam in cleaned:
            return eng
    return None


def map_to_schema(verse: ExtractedVerse, source_url: str = "") -> dict:
    """Map extracted verse to the 32-field Sentamizh Corpus schema."""
    verse_num = verse.verse_number.zfill(3)
    thinai_eng = normalize_thinai(verse.tinai)

    entry = {
        "verse_id": f"AKAM-{verse_num}",
        "source_text": "Akananuru",
        "layer": "Sangam",
        "period": "300 BCE – 300 CE",
        "verse_number": verse.verse_number,
        "classical_tamil": verse.classical_tamil,
        "modern_tamil": None,
        "english": None,
        "source_url": source_url if source_url else None,
        "difficulty": "archaic",

        "thinai": thinai_eng,
        "turai": verse.turai if verse.turai else None,
        "akam_or_puram": "Akam",
        "karu": None,
        "uri": None,
        "ullurai": None,
        "speaker_role": None,
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

    context_parts = []
    if verse.poet:
        context_parts.append(f"Poet: {verse.poet}")
    if verse.tinai:
        context_parts.append(f"Tinai: {verse.tinai}")
    if verse.turai:
        context_parts.append(f"Turai: {verse.turai}")
    if context_parts:
        entry["cultural_context"] = '; '.join(context_parts)

    return entry


# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extract Akananuru verses from Project Madurai HTML"
    )
    parser.add_argument("html_file", help="Path to HTML file")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--source-url", default="", help="Source URL")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    html_path = Path(args.html_file)
    if not html_path.exists():
        print(f"Error: File not found: {html_path}")
        sys.exit(1)

    print(f"Extracting from: {html_path.name}")
    verses = extract_verses(str(html_path))
    edition = detect_edition(html_path.name)
    print(f"Edition: {edition}")
    print(f"Extracted {len(verses)} verses")

    if args.verbose:
        for v in verses[:5]:
            preview = v.classical_tamil[:60].replace('\n', ' ')
            print(f"  #{v.verse_number}: tinai={v.tinai!r} turai={v.turai[:30]!r} | {preview}...")

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
        nums = sorted([int(v.verse_number) for v in verses if v.verse_number.isdigit()])
        if nums:
            expected = list(range(nums[0], nums[-1] + 1))
            missing = sorted(set(expected) - set(nums))
            if missing:
                preview = missing[:10]
                print(f"  Missing verse numbers: {preview}{'...' if len(missing) > 10 else ''}")
            else:
                print(f"  Verse number coverage: complete ({nums[0]}-{nums[-1]})")
        with_tinai = sum(1 for v in verses if v.tinai)
        print(f"  Verses with tinai: {with_tinai}/{len(verses)}")


if __name__ == "__main__":
    main()
