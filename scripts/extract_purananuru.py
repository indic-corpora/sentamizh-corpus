#!/usr/bin/env python3
"""
Sentamizh Corpus — Purananuru Extraction Pipeline

Extracts structured verse data from Project Madurai Purananuru HTML files.
Produces JSON entries conforming to the Sentamizh Corpus schema (32 fields).

Usage:
    python extract_purananuru.py <html_file> [--output <output_file>]
    python extract_purananuru.py ../data/raw/Purananuru_Part1_Verses_1_60.html
    python extract_purananuru.py ../data/raw/Purananuru_Part1_Verses_1_60.html -o ../data/processed/purananuru_part1.json

Strategy:
    Primary extraction signal: <ul> tags containing verse text with end-marker (N).
    Every verse in the HTML has its Classical Tamil text inside a <ul> block,
    ending with a parenthesized verse number like (2), (3), etc.
    This is more reliable than <h3> headings (some verses share headings).

    For each <ul>:
    1. Extract verse number from end-marker (N)
    2. Extract classical Tamil text (clean line numbers and markers)
    3. Walk backwards to find <h3> heading (title)
    4. Walk forwards to find tinai/turai line, commentary, explanation
"""

import json
import re
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

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
    """Raw extracted data from HTML, before schema mapping."""
    verse_number: str = ""
    title: str = ""
    prose_intro: str = ""
    classical_tamil: str = ""
    tinai: str = ""
    turai: str = ""
    poet: str = ""
    subject: str = ""
    commentary: str = ""
    explanation: str = ""
    tinai_turai_raw: str = ""


# ─── Text Cleaning ──────────────────────────────────────────────────────────

def clean_verse_text(raw_text: str) -> str:
    """Clean extracted verse text: remove line numbers, extra whitespace,
    trailing verse number in parens."""
    text = raw_text.replace('\xa0', ' ').replace('&nbsp;', ' ')

    # Remove trailing verse number in parentheses: (2), (3), etc.
    text = re.sub(r'\s*\(\d+\)\s*$', '', text.strip())

    # Remove embedded line numbers (standalone numbers like 5, 10, 15, 20, 25...)
    # They appear with lots of whitespace before them
    text = re.sub(r'\s{3,}(\d{1,3})\s*$', '', text, flags=re.MULTILINE)
    # Also catch line numbers at end of lines with tabs
    text = re.sub(r'\t+\s*(\d{1,3})\s*$', '', text, flags=re.MULTILINE)

    # Normalize: collapse blank lines, trim each line
    lines = [line.strip() for line in text.split('\n')]
    lines = [l for l in lines if l]
    text = '\n'.join(lines)

    return text.strip()


def clean_text(text: str) -> str:
    """General text cleaning."""
    text = text.replace('\xa0', ' ').replace('&nbsp;', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ─── Tinai/Turai Parsing ────────────────────────────────────────────────────

def parse_tinai_turai_line(raw_line: str) -> dict:
    """Parse a tinai/turai/attribution line into components.

    Handles many variations:
        "திணை- பாடாண்டிணை; துறை- செவியறிவுறூஉ; ... நாகனார் பாடியது."
        "திணை: வஞ்சி; துறை: கொற்றவள்ளை. ... பரணர் பாடியது."
        "திணையும் துறையும் அவை. ... நெட்டிமையார் பாடியது."
        "*திணை - பாடாண்டிணை. துறை - பரிசில் கடாநிலை. ..."
    """
    result = {
        'tinai': '',
        'turai': '',
        'poet': '',
        'subject': '',
    }

    clean = clean_text(raw_line)
    # Remove leading asterisk
    clean = clean.lstrip('*').strip()

    # Handle "திணையும் துறையும் அவை" and variations (= same as previous)
    # Variations: "திணையும் துறையும் அவை", "திணையுந் துறையு மவை", "திணை யும் துறையு மவை"
    if re.search(r'திணை\s*யு[ம்ந]\s*துறை\s*யு\s*ம?\s*அவை', clean) or 'திணையும் துறையும் அவை' in clean:
        result['tinai'] = '(same as previous)'
        result['turai'] = '(same as previous)'
    elif re.search(r'திணை\s*:\s*அது', clean):
        result['tinai'] = '(same as previous)'
        # But turai may be specified
        turai_match = re.search(r'துறை[-:\s]*([^.;]+)', clean)
        if turai_match:
            val = turai_match.group(1).strip().rstrip(';').strip()
            val = re.sub(r'^[-:\s]+', '', val).strip()
            if val:
                result['turai'] = val
    else:
        # Extract tinai — get text between திணை and the next separator (; . துறை)
        tinai_match = re.search(r'திணை[-:\s]*([^;.]+?)(?:[;.]|\s*துறை)', clean)
        if tinai_match:
            tinai_val = tinai_match.group(1).strip().rstrip(';').strip()
            tinai_val = re.sub(r'^[-:\s]+', '', tinai_val).strip()
            # Must be a real tinai name (at least 3 chars, not just a fragment)
            if tinai_val and len(tinai_val) >= 3 and 'அவை' not in tinai_val:
                result['tinai'] = tinai_val

        # Extract turai — get text after துறை until next separator
        turai_match = re.search(r'துறை[-:\s]*([^.;]+?)(?:[.;]|$)', clean)
        if turai_match:
            turai_val = turai_match.group(1).strip().rstrip(';').strip()
            turai_val = re.sub(r'^[-:\s]+', '', turai_val).strip()
            # Filter out references to previous ("அவை", "மவை", "யு மவை")
            if turai_val and len(turai_val) > 2 and 'அவை' not in turai_val and 'மவை' not in turai_val:
                # Turai should be a short classification, not a long sentence
                # If it contains "பாடியது" it's captured attribution text — truncate
                if 'பாடியது' in turai_val:
                    turai_val = turai_val.split('.')[0].strip()
                    if 'பாடியது' in turai_val or len(turai_val) > 40:
                        turai_val = ''
                if turai_val:
                    result['turai'] = turai_val

    # Extract poet name: "X பாடியது"
    poet_match = re.search(r'(\S+(?:\s+\S+){0,5}?)\s+பாடியது', clean)
    if poet_match:
        poet_raw = poet_match.group(1).strip()
        # Clean: remove "யை" suffix from subject that might be captured
        # The pattern before பாடியது is typically "poet-name" directly
        # But sometimes it's "subject-யை poet-name"
        # Take the last 1-3 words as poet name
        words = poet_raw.split()
        if len(words) <= 3:
            result['poet'] = poet_raw
        else:
            # Find where subject ends (ends with யை/ை) and poet begins
            for i, w in enumerate(words):
                if w.endswith('யை') or w.endswith('னை') or w.endswith('ளை'):
                    result['subject'] = ' '.join(words[:i+1])
                    result['poet'] = ' '.join(words[i+1:])
                    break
            else:
                result['poet'] = ' '.join(words[-2:])  # Last 2 words as poet

    return result


# ─── Main Extraction ────────────────────────────────────────────────────────

def extract_verses(html_path: str) -> list[ExtractedVerse]:
    """Extract all verses from a Purananuru HTML file.

    Strategy: iterate over <ul> tags, extract verse number from end-marker,
    then walk DOM to find heading, tinai/turai, commentary.
    """
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    verses = []

    # Build a map of h3 headings by verse number for title lookup
    h3_titles = {}
    for h3 in soup.find_all('h3'):
        text = h3.get_text(strip=True)
        match = re.search(r'(\d+)\.\s*(.+)', text)
        if match:
            num = match.group(1)
            title = match.group(2).strip().rstrip('.')
            h3_titles[num] = title

    # Find all <ul> tags with verse content
    all_uls = soup.find_all('ul')

    for ul in all_uls:
        raw_text = ul.get_text()

        # Check for verse-end marker (N)
        marker_match = re.search(r'\((\d+)\)\s*$', raw_text.strip())
        if not marker_match:
            continue  # Skip non-verse <ul> (e.g., acknowledgements)

        verse_num = marker_match.group(1)
        verse = ExtractedVerse()
        verse.verse_number = verse_num
        verse.classical_tamil = clean_verse_text(raw_text)

        # Look up title from h3 map
        verse.title = h3_titles.get(verse_num, "")

        # Walk forward from this <ul> to find tinai/turai, commentary, explanation
        tinai_turai_raw = ""
        commentary_parts = []
        explanation_parts = []
        in_commentary = False
        in_explanation = False

        sibling = ul.next_sibling
        stop_count = 0
        while sibling and stop_count < 60:
            stop_count += 1

            if isinstance(sibling, Tag):
                # Stop at next <ul> (next verse) or <center> with <h3> (next heading)
                if sibling.name == 'ul':
                    break
                if sibling.name == 'center' and sibling.find('h3'):
                    break

                tag_text = clean_text(sibling.get_text())

                if sibling.name == 'strong':
                    strong_text = sibling.get_text(strip=True)
                    if 'உரை' in strong_text:
                        in_commentary = True
                        in_explanation = False
                    elif 'விளக்கம்' in strong_text:
                        in_explanation = True
                        in_commentary = False

                elif tag_text and sibling.name not in ('br',):
                    if in_explanation:
                        explanation_parts.append(tag_text)
                    elif in_commentary:
                        commentary_parts.append(tag_text)

            elif isinstance(sibling, NavigableString):
                text = sibling.strip()
                if text:
                    # Check for dash separator (verse boundary)
                    if re.match(r'^-{5,}', text):
                        break

                    # Check if this is the tinai/turai line
                    if ('திணை' in text or 'திணையும்' in text) and not tinai_turai_raw:
                        tinai_turai_raw = text
                    elif in_explanation:
                        explanation_parts.append(text)
                    elif in_commentary:
                        commentary_parts.append(text)
                    elif text.startswith(':'):
                        if in_commentary:
                            commentary_parts.append(text)

            sibling = sibling.next_sibling

        # Also try walking backward to find prose intro
        prose_parts = []
        prev = ul.previous_sibling
        prev_count = 0
        while prev and prev_count < 15:
            prev_count += 1
            if isinstance(prev, Tag):
                if prev.name == 'center' and prev.find('h3'):
                    break  # Hit the heading
                if prev.name == 'ul':
                    break  # Hit previous verse
                if prev.name not in ('br',):
                    text = clean_text(prev.get_text())
                    if text and len(text) > 10:
                        prose_parts.insert(0, text)
            elif isinstance(prev, NavigableString):
                text = prev.strip()
                if text and len(text) > 10 and not re.match(r'^-{5,}', text):
                    prose_parts.insert(0, clean_text(text))
            prev = prev.previous_sibling

        # Populate verse
        verse.tinai_turai_raw = tinai_turai_raw
        verse.prose_intro = ' '.join(prose_parts).strip()
        verse.commentary = ' '.join(commentary_parts).strip()
        verse.explanation = ' '.join(explanation_parts).strip()

        # Parse tinai/turai
        if tinai_turai_raw:
            parsed = parse_tinai_turai_line(tinai_turai_raw)
            verse.tinai = parsed['tinai']
            verse.turai = parsed['turai']
            verse.poet = parsed['poet']
            verse.subject = parsed['subject']

        if verse.classical_tamil:
            verses.append(verse)

    # Sort by verse number
    verses.sort(key=lambda v: int(v.verse_number) if v.verse_number.isdigit() else 0)

    return verses


# ─── Schema Mapping ─────────────────────────────────────────────────────────

def map_to_schema(verse: ExtractedVerse, source_url: str = "") -> dict:
    """Map extracted verse to the 32-field Sentamizh Corpus schema."""

    verse_num = verse.verse_number.zfill(3)

    entry = {
        # Core layer
        "verse_id": f"PURN-{verse_num}",
        "source_text": "Purananuru",
        "layer": "Sangam",
        "period": "300 BCE – 300 CE",
        "verse_number": verse.verse_number,
        "classical_tamil": verse.classical_tamil,
        "modern_tamil": None,
        "english": None,
        "source_url": source_url if source_url else None,
        "difficulty": "archaic",

        # Tamil-native interpretive layer
        "thinai": None,
        "turai": verse.turai if verse.turai and '(same' not in verse.turai else None,
        "akam_or_puram": "Puram",
        "karu": None,
        "uri": None,
        "ullurai": None,
        "speaker_role": "bard",
        "metre": "aciriyappa",
        "pann": None,
        "dhvani_layer": None,

        # Interpretive layer
        "rasa_primary": None,
        "rasa_secondary": None,
        "themes": None,
        "philosophical_concept": None,
        "cultural_context": None,
        "storytelling_seed_narrative": None,
        "storytelling_seed_emotional": None,

        # Cross-cultural bridge layer
        "nayika_bheda": None,
        "visual_imagery": None,
        "emotional_valence": None,

        # Meta
        "annotator": "extraction-pipeline-v1",
        "annotation_confidence": "medium",
    }

    # Build cultural_context from extracted metadata
    context_parts = []
    if verse.title:
        context_parts.append(f"Title: {verse.title}")
    if verse.poet:
        context_parts.append(f"Poet: {verse.poet}")
    if verse.subject:
        context_parts.append(f"Subject: {verse.subject}")
    if verse.tinai and '(same' not in verse.tinai:
        context_parts.append(f"Tinai: {verse.tinai}")
    if verse.turai and '(same' not in verse.turai:
        context_parts.append(f"Turai: {verse.turai}")
    if context_parts:
        entry["cultural_context"] = '; '.join(context_parts)

    return entry


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extract Purananuru verses from Project Madurai HTML"
    )
    parser.add_argument("html_file", help="Path to HTML file")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--source-url", default="", help="Source URL for provenance")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print detailed extraction info")

    args = parser.parse_args()

    html_path = Path(args.html_file)
    if not html_path.exists():
        print(f"Error: File not found: {html_path}")
        sys.exit(1)

    # Extract
    print(f"Extracting from: {html_path.name}")
    verses = extract_verses(str(html_path))
    print(f"Extracted {len(verses)} verses")

    if args.verbose:
        for v in verses:
            tamil_preview = v.classical_tamil[:60].replace('\n', ' ')
            print(f"  #{v.verse_number}: {v.title[:40] if v.title else '(no title)'}  |  Tamil: {tamil_preview}...")
            if v.tinai or v.turai:
                print(f"    Tinai: {v.tinai} | Turai: {v.turai} | Poet: {v.poet}")

    # Map to schema
    entries = [map_to_schema(v, args.source_url) for v in verses]

    # Output
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = html_path.parent.parent / "processed" / f"{html_path.stem}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(entries)} entries to {output_path}")

    # Summary statistics
    with_title = sum(1 for v in verses if v.title)
    with_tinai = sum(1 for v in verses if v.tinai and '(same' not in v.tinai)
    with_turai = sum(1 for v in verses if v.turai and '(same' not in v.turai)
    with_poet = sum(1 for v in verses if v.poet)
    with_commentary = sum(1 for v in verses if v.commentary)
    same_as_prev = sum(1 for v in verses if v.tinai == '(same as previous)')

    print(f"\nExtraction summary:")
    print(f"  Verses with title:      {with_title}/{len(verses)}")
    print(f"  Verses with tinai:      {with_tinai}/{len(verses)} (+ {same_as_prev} 'same as previous')")
    print(f"  Verses with turai:      {with_turai}/{len(verses)}")
    print(f"  Verses with poet:       {with_poet}/{len(verses)}")
    print(f"  Verses with commentary: {with_commentary}/{len(verses)}")

    # Check for verse number gaps
    nums = sorted([int(v.verse_number) for v in verses])
    expected = list(range(nums[0], nums[-1] + 1))
    missing = set(expected) - set(nums)
    if missing:
        print(f"  Missing verse numbers:  {sorted(missing)}")
    else:
        print(f"  Verse number coverage:  Complete ({nums[0]}-{nums[-1]})")


if __name__ == "__main__":
    main()
