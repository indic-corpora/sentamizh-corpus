#!/usr/bin/env python3
"""
Sentamizh Corpus — Purananuru Complete Extraction & Merge Pipeline

Orchestrates extraction of all 6 Purananuru HTML parts (Ed1 Parts 1-3, Ed2 Parts 1-3),
merges into a single consolidated JSON, deduplicates by verse_id, validates against schema,
and outputs consolidated Purananuru_All.json.

Usage:
    python extract_all_purananuru.py
    python extract_all_purananuru.py --validate
    python extract_all_purananuru.py --keep-parts
    python extract_all_purananuru.py --validate --keep-parts
    python extract_all_purananuru.py --verbose

Edition mapping:
    Ed1 (PM #494): verses 1-200 across 3 parts
    Ed2 (PM #531): verses 201-400 across 3 parts
"""

import json
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict

try:
    from jsonschema import Draft202012Validator, ValidationError
except ImportError:
    print("Installing jsonschema...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "jsonschema", "--break-system-packages", "-q"])
    from jsonschema import Draft202012Validator, ValidationError

# Import extraction functions from extract_purananuru
import importlib.util
spec = importlib.util.spec_from_file_location("extract_purananuru", Path(__file__).parent / "extract_purananuru.py")
extract_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract_module)

extract_verses = extract_module.extract_verses
map_to_schema = extract_module.map_to_schema


# ─── Configuration ──────────────────────────────────────────────────────────

PARTS_CONFIG = [
    {
        "edition": "Ed1",
        "part": 1,
        "verses": "1-67",
        "pm_id": "pmuni0494",
        "source_url": "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0494.txt",
    },
    {
        "edition": "Ed1",
        "part": 2,
        "verses": "68-133",
        "pm_id": "pmuni0494",
        "source_url": "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0494.txt",
    },
    {
        "edition": "Ed1",
        "part": 3,
        "verses": "134-200",
        "pm_id": "pmuni0494",
        "source_url": "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0494.txt",
    },
    {
        "edition": "Ed2",
        "part": 1,
        "verses": "201-267",
        "pm_id": "pmuni0531",
        "source_url": "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0531.txt",
    },
    {
        "edition": "Ed2",
        "part": 2,
        "verses": "268-333",
        "pm_id": "pmuni0531",
        "source_url": "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0531.txt",
    },
    {
        "edition": "Ed2",
        "part": 3,
        "verses": "334-400",
        "pm_id": "pmuni0531",
        "source_url": "https://www.projectmadurai.org/pm_etexts/utf8/pmuni0531.txt",
    },
]


# ─── Merging & Deduplication ────────────────────────────────────────────────

def count_nonnull_fields(entry: Dict[str, Any]) -> int:
    """Count how many non-null fields an entry has."""
    return sum(1 for v in entry.values() if v is not None and v != "")


def merge_entries(entries_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    When merging duplicate verse_ids, prefer the entry with more non-null fields.

    Args:
        entries_list: List of entries with the same verse_id

    Returns:
        The entry with the most metadata
    """
    if not entries_list:
        return {}
    if len(entries_list) == 1:
        return entries_list[0]

    # Sort by number of non-null fields descending
    sorted_entries = sorted(entries_list, key=count_nonnull_fields, reverse=True)
    return sorted_entries[0]


def deduplicate_by_verse_id(all_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Group entries by verse_id and keep the one with most metadata.

    Args:
        all_entries: All extracted entries

    Returns:
        Deduplicated list, sorted by verse_id
    """
    by_verse_id = defaultdict(list)

    for entry in all_entries:
        verse_id = entry.get("verse_id")
        if verse_id:
            by_verse_id[verse_id].append(entry)

    deduplicated = []
    for verse_id in sorted(by_verse_id.keys()):
        merged = merge_entries(by_verse_id[verse_id])
        deduplicated.append(merged)

    return deduplicated


# ─── Schema Validation ──────────────────────────────────────────────────────

def load_schema(schema_path: Path) -> Dict[str, Any]:
    """Load the Sentamizh Corpus schema."""
    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate_entry(entry: Dict[str, Any], schema: Dict[str, Any], verbose: bool = False) -> tuple[bool, str]:
    """
    Validate a single entry against the schema.

    Returns:
        (is_valid, error_message)
    """
    validator = Draft202012Validator(schema)

    errors = list(validator.iter_errors(entry))
    if errors:
        error_msg = "; ".join(e.message for e in errors[:3])
        if verbose:
            return False, f"verse_id {entry.get('verse_id')}: {error_msg}"
        else:
            return False, error_msg

    return True, ""


def validate_merged_file(json_path: Path, schema_path: Path, verbose: bool = False) -> bool:
    """
    Validate all entries in the merged JSON file against schema.

    Returns:
        True if all valid, False otherwise
    """
    print(f"\nValidating against schema: {schema_path.name}")

    schema = load_schema(schema_path)

    with open(json_path, 'r', encoding='utf-8') as f:
        entries = json.load(f)

    if not isinstance(entries, list):
        print("ERROR: Root must be a JSON array")
        return False

    invalid_count = 0
    for i, entry in enumerate(entries):
        is_valid, error = validate_entry(entry, schema, verbose=verbose)
        if not is_valid:
            invalid_count += 1
            if invalid_count <= 5:  # Print first 5 errors
                print(f"  [Entry {i}] {error}")
            elif invalid_count == 6:
                print(f"  ... and {len(entries) - 5} more validation errors")

    if invalid_count == 0:
        print(f"✓ All {len(entries)} entries validated successfully")
        return True
    else:
        print(f"✗ {invalid_count}/{len(entries)} entries failed validation")
        return False


# ─── Main Pipeline ──────────────────────────────────────────────────────────

def read_file_workaround(file_path: Path) -> str:
    """
    Read file content using os.open to work around filesystem locking issues.
    """
    import os

    # Use os.open with buffering to avoid deadlock
    fd = os.open(str(file_path), os.O_RDONLY)
    try:
        # Read in chunks to avoid locking
        chunks = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        data = b''.join(chunks)
        return data.decode('utf-8')
    finally:
        os.close(fd)


def extract_single_part(html_path: Path, source_url: str, edition: str = "Ed1", verbose: bool = False) -> tuple[List[Dict[str, Any]], int]:
    """
    Extract a single HTML part and return schema-mapped entries.

    Ed1 and Ed2 Project Madurai editions use different markup:
      Ed1: <h3>N. Title</h3> + <ul>verse text (N)</ul>       (verse-end marker)
      Ed2: <strong>N. Title</strong> + <ul>verse text</ul>   (no end marker)

    Dispatches to the right parser based on the edition flag from PARTS_CONFIG.

    Returns:
        (entries, count)
    """
    if edition == "Ed2":
        return extract_single_part_ed2(html_path, source_url, verbose=verbose)

    import os
    from bs4 import BeautifulSoup

    if not html_path.exists():
        print(f"  WARNING: File not found: {html_path}")
        return [], 0

    # Read HTML file with workaround for filesystem issues
    html_content = read_file_workaround(html_path)
    soup = BeautifulSoup(html_content, 'html.parser')

    # Extract raw verses directly instead of calling extract_verses
    # (to avoid the file open issue in the imported module)
    verses = []

    # Build a map of h3 headings by verse number for title lookup
    h3_titles = {}
    for h3 in soup.find_all('h3'):
        text = h3.get_text(strip=True)
        match = __import__('re').search(r'(\d+)\.\s*(.+)', text)
        if match:
            num = match.group(1)
            title = match.group(2).strip().rstrip('.')
            h3_titles[num] = title

    # Find all <ul> tags with verse content
    all_uls = soup.find_all('ul')

    for ul in all_uls:
        raw_text = ul.get_text()

        # Check for verse-end marker (N)
        marker_match = __import__('re').search(r'\((\d+)\)\s*$', raw_text.strip())
        if not marker_match:
            continue  # Skip non-verse <ul>

        verse_num = marker_match.group(1)
        verse = extract_module.ExtractedVerse()
        verse.verse_number = verse_num
        verse.classical_tamil = extract_module.clean_verse_text(raw_text)

        # Look up title from h3 map
        verse.title = h3_titles.get(verse_num, "")

        # Walk forward from this <ul> to find tinai/turai, commentary, explanation
        tinai_turai_raw = ""
        commentary_parts = []
        explanation_parts = []
        in_commentary = False
        in_explanation = False

        from bs4 import NavigableString, Tag
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

                tag_text = extract_module.clean_text(sibling.get_text())

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
                    if __import__('re').match(r'^-{5,}', text):
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

        # Walk backward to find prose intro
        prose_parts = []
        prev = ul.previous_sibling
        prev_count = 0
        while prev and prev_count < 15:
            prev_count += 1
            if isinstance(prev, Tag):
                if prev.name == 'center' and prev.find('h3'):
                    break
                if prev.name == 'ul':
                    break
                if prev.name not in ('br',):
                    text = extract_module.clean_text(prev.get_text())
                    if text and len(text) > 10:
                        prose_parts.insert(0, text)
            elif isinstance(prev, NavigableString):
                text = prev.strip()
                if text and len(text) > 10 and not __import__('re').match(r'^-{5,}', text):
                    prose_parts.insert(0, extract_module.clean_text(text))
            prev = prev.previous_sibling

        # Populate verse
        verse.tinai_turai_raw = tinai_turai_raw
        verse.prose_intro = ' '.join(prose_parts).strip()
        verse.commentary = ' '.join(commentary_parts).strip()
        verse.explanation = ' '.join(explanation_parts).strip()

        # Parse tinai/turai
        if tinai_turai_raw:
            parsed = extract_module.parse_tinai_turai_line(tinai_turai_raw)
            verse.tinai = parsed['tinai']
            verse.turai = parsed['turai']
            verse.poet = parsed['poet']
            verse.subject = parsed['subject']

        if verse.classical_tamil:
            verses.append(verse)

    # Sort by verse number
    verses.sort(key=lambda v: int(v.verse_number) if v.verse_number.isdigit() else 0)

    # Map to schema
    entries = [map_to_schema(v, source_url) for v in verses]

    return entries, len(entries)


def extract_single_part_ed2(html_path: Path, source_url: str, verbose: bool = False) -> tuple[List[Dict[str, Any]], int]:
    """
    Extract a single Ed2 HTML part (verses 201-400).

    Ed2 verse structure:
        <strong>N. Title</strong>          (verse heading)
        <br><br>
        prose intro text                   (Tamil commentary prologue)
        <br>
        <ul>verse text</ul>                (classical Tamil, NO (N) end marker)
        <br>
        tinai/turai line                   (contains திணை or துறை)
        <br>
        உரை: commentary                    (urai — glossarial commentary)
        ...
        விளக்கம்: explanation              (vilakkam — extended explanation)
        <br>
        ------------                       (separator to next verse)

    Known gaps in Ed2 source text:
        267, 268: marked as lost (content is just "... ... ...")
        349, 364: heading appears as plain text between <br> tags, not in <strong>
                   (text-node heading scan would recover these — polish pass)

    Returns:
        (entries, count)
    """
    import re
    from bs4 import BeautifulSoup, NavigableString, Tag

    if not html_path.exists():
        print(f"  WARNING: File not found: {html_path}")
        return [], 0

    html_content = read_file_workaround(html_path)
    soup = BeautifulSoup(html_content, 'html.parser')

    # Collect verse headings: <strong>N.? Title?</strong>
    # Period and title both optional (handles "308 கோவூர்" and lost-verse "267").
    headings = []
    for strong in soup.find_all('strong'):
        text = strong.get_text(strip=True)
        m = re.match(r"^\s*(\d+)\s*\.?\s*(.*)$", text)
        if m:
            headings.append((strong, m.group(1), m.group(2).strip().rstrip('.')))

    verses = []
    for strong, verse_num, title in headings:
        verse = extract_module.ExtractedVerse()
        verse.verse_number = verse_num
        verse.title = title

        prose_parts = []
        verse_ul_text = ""
        tinai_turai_raw = ""
        commentary_parts = []
        explanation_parts = []
        state = "prose"            # prose -> after_ul
        commentary_mode = False    # true after உரை: marker
        explanation_mode = False   # true after விளக்கம்: marker

        sib = strong.next_sibling
        steps = 0
        while sib and steps < 120:
            steps += 1

            # Stop at next verse heading
            if isinstance(sib, Tag) and sib.name == 'strong':
                if re.match(r"^\s*\d+\b", sib.get_text(strip=True)):
                    break

            # Capture the <ul> as verse body
            if isinstance(sib, Tag) and sib.name == 'ul':
                verse_ul_text = sib.get_text()
                state = "after_ul"
                sib = sib.next_sibling
                continue

            # Normalize text from this node
            if isinstance(sib, Tag):
                if sib.name == 'br':
                    sib = sib.next_sibling
                    continue
                raw = extract_module.clean_text(sib.get_text())
            elif isinstance(sib, NavigableString):
                raw = sib.strip()
            else:
                sib = sib.next_sibling
                continue

            if not raw:
                sib = sib.next_sibling
                continue

            # Dash separator row:
            #   before <ul>: decorative — skip without terminating verse
            #   after  <ul>: verse terminator
            if re.match(r"^-{5,}$", raw.replace(" ", "")):
                if state == "after_ul":
                    break
                sib = sib.next_sibling
                continue

            # Commentary/explanation markers
            if raw.startswith('உரை:') or raw.startswith('உரை :'):
                commentary_mode = True
                explanation_mode = False
                raw = re.sub(r"^உரை\s*:\s*", "", raw)
            elif raw.startswith('விளக்கம்:') or raw.startswith('விளக்கம் :'):
                explanation_mode = True
                commentary_mode = False
                raw = re.sub(r"^விளக்கம்\s*:\s*", "", raw)

            # tinai/turai line: first post-<ul> text containing திணை or துறை
            # (must not be inside commentary/explanation block)
            if (state == "after_ul" and not tinai_turai_raw
                    and ('திணை' in raw or 'துறை' in raw)
                    and not commentary_mode and not explanation_mode):
                tinai_turai_raw = raw
                sib = sib.next_sibling
                continue

            # Route content to the right bucket
            if state == "prose":
                prose_parts.append(raw)
            elif state == "after_ul":
                if explanation_mode:
                    if raw:
                        explanation_parts.append(raw)
                elif commentary_mode:
                    if raw:
                        commentary_parts.append(raw)

            sib = sib.next_sibling

        # Populate the verse object
        if verse_ul_text:
            verse.classical_tamil = extract_module.clean_verse_text(verse_ul_text)
        verse.tinai_turai_raw = tinai_turai_raw
        verse.prose_intro = ' '.join(prose_parts).strip()
        verse.commentary = ' '.join(commentary_parts).strip()
        verse.explanation = ' '.join(explanation_parts).strip()

        if tinai_turai_raw:
            parsed = extract_module.parse_tinai_turai_line(tinai_turai_raw)
            verse.tinai = parsed.get('tinai', '')
            verse.turai = parsed.get('turai', '')
            verse.poet = parsed.get('poet', '')
            verse.subject = parsed.get('subject', '')

        # Skip lost verses (no classical_tamil body)
        if verse.classical_tamil:
            verses.append(verse)

    verses.sort(key=lambda v: int(v.verse_number) if v.verse_number.isdigit() else 0)
    entries = [map_to_schema(v, source_url) for v in verses]
    return entries, len(entries)


def main():
    parser = argparse.ArgumentParser(
        description="Extract and merge all Purananuru parts into consolidated JSON"
    )
    parser.add_argument("--validate", action="store_true",
                        help="Validate merged output against schema")
    parser.add_argument("--keep-parts", action="store_true",
                        help="Keep individual part JSON files (default: remove)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print detailed extraction info")

    args = parser.parse_args()

    # Determine paths (relative to script location)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    raw_data_dir = project_root / "data" / "raw"
    processed_data_dir = project_root / "data" / "processed"
    schema_path = project_root / "schemas" / "sentamizh_schema.json"

    processed_data_dir.mkdir(parents=True, exist_ok=True)

    if not schema_path.exists():
        print(f"ERROR: Schema not found: {schema_path}")
        sys.exit(1)

    print("=" * 80)
    print("Purananuru Complete Extraction & Merge Pipeline")
    print("=" * 80)
    print()

    # Extract all parts
    all_entries = []
    part_stats = []

    for config in PARTS_CONFIG:
        edition = config["edition"]
        part = config["part"]
        verses_range = config["verses"]
        source_url = config["source_url"]

        html_filename = f"Purananuru_{edition}_Part{part}.html"
        html_path = raw_data_dir / html_filename

        print(f"[{edition} Part {part}] Verses {verses_range}")
        print(f"  Input:  {html_filename}")

        entries, count = extract_single_part(html_path, source_url, edition=edition, verbose=args.verbose)
        all_entries.extend(entries)

        part_output = processed_data_dir / f"Purananuru_{edition}_Part{part}.json"
        part_output.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')

        print(f"  Output: {part_output.name}")
        print(f"  Extracted: {count} entries")

        part_stats.append({
            "edition": edition,
            "part": part,
            "count": count,
            "output": part_output,
        })

        # Print some stats
        with_metadata = sum(1 for e in entries if e.get("cultural_context"))
        with_poet = sum(1 for e in entries if e.get("annotator"))
        print(f"  Metadata: {with_metadata}/{count} with cultural_context")
        print()

    # Deduplicate across all parts
    print("Deduplicating entries by verse_id...")
    merged_entries = deduplicate_by_verse_id(all_entries)

    duplicates_removed = len(all_entries) - len(merged_entries)
    print(f"  Total extracted: {len(all_entries)}")
    print(f"  After dedup:     {len(merged_entries)}")
    if duplicates_removed > 0:
        print(f"  Duplicates removed: {duplicates_removed}")
    print()

    # Write merged file
    merged_output = processed_data_dir / "Purananuru_All.json"
    print(f"Writing consolidated file: {merged_output.name}")
    merged_output.write_text(json.dumps(merged_entries, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"  Total entries: {len(merged_entries)}")
    print()

    # Validate if requested
    if args.validate:
        is_valid = validate_merged_file(merged_output, schema_path, verbose=args.verbose)
        if not is_valid:
            sys.exit(1)

    # Clean up part files unless --keep-parts
    if not args.keep_parts:
        print("Cleaning up individual part files...")
        for stat in part_stats:
            part_output = stat["output"]
            if part_output.exists():
                part_output.unlink()
                print(f"  Removed: {part_output.name}")
        print()
    else:
        print("Keeping individual part files (--keep-parts flag set)")
        print()

    # Final summary
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"Output file:      {merged_output.name}")
    print(f"Total entries:    {len(merged_entries)}")
    print(f"Verse ID range:   PURN-001 to PURN-{merged_entries[-1]['verse_id'].split('-')[1]}")

    # Verify verse number coverage
    verse_nums = sorted([int(e['verse_number']) for e in merged_entries if e.get('verse_number', '').isdigit()])
    if verse_nums:
        print(f"Verse coverage:   {verse_nums[0]}-{verse_nums[-1]} ({len(verse_nums)} verses)")
        expected_range = set(range(verse_nums[0], verse_nums[-1] + 1))
        missing = expected_range - set(verse_nums)
        if missing:
            print(f"Missing verses:   {sorted(missing)}")

    # Metadata coverage
    with_title = sum(1 for e in merged_entries if e.get("cultural_context"))
    with_turai = sum(1 for e in merged_entries if e.get("turai"))
    print(f"With metadata:    {with_title}/{len(merged_entries)} entries")
    print(f"With turai:       {with_turai}/{len(merged_entries)} entries")
    print()

    print("✓ Pipeline complete")


if __name__ == "__main__":
    main()
