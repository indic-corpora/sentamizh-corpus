#!/usr/bin/env python3
"""
Sentamizh Corpus — Vaidehi Sangam Translations Downloader & Extractor

Downloads Kuruntokai and Natrinai pages from sangamtranslationsbyvaidehi.com,
then parses them into structured JSON entries matching the Sentamizh schema.

These two texts are NOT available on Project Madurai's current HTML catalog,
so we source them from Vaidehi Herbert's translations site which provides:
  - Original Classical Tamil text (Unicode)
  - English translations
  - Poet name, Tinai, Speaker context, Notes

Usage:
    python3 download_vaidehi_sangam.py
    python3 download_vaidehi_sangam.py --download-only     # Just save HTML pages
    python3 download_vaidehi_sangam.py --parse-only         # Parse already-downloaded HTML
    python3 download_vaidehi_sangam.py --text kuruntokai    # Only one text
    python3 download_vaidehi_sangam.py --text natrinai

Requirements:
    Python 3.7+ with beautifulsoup4:
        pip install beautifulsoup4
"""

import os
import sys
import re
import json
import time
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

VAIDEHI_PAGES = {
    "kuruntokai": [
        ("Kuruntokai_Vaidehi_1_200.html",
         "https://sangamtranslationsbyvaidehi.com/ettuthokai-kurunthokai-1-200/",
         "Kuruntokai poems 1-200 with Tamil text and English translation"),
        ("Kuruntokai_Vaidehi_201_400.html",
         "https://sangamtranslationsbyvaidehi.com/ettuthokai-kurunthokai-201-400/",
         "Kuruntokai poems 201-400 with Tamil text and English translation"),
    ],
    "natrinai": [
        ("Natrinai_Vaidehi_1_200.html",
         "https://sangamtranslationsbyvaidehi.com/ettuthokai-natrinai-1-200/",
         "Natrinai poems 1-200 with Tamil text and English translation"),
        ("Natrinai_Vaidehi_201_400.html",
         "https://sangamtranslationsbyvaidehi.com/natrinai-2-2/",
         "Natrinai poems 201-400 with Tamil text and English translation"),
    ],
}

# Tinai name mappings (Tamil → schema enum values)
# Covers all spelling variants found in Vaidehi's pages
TINAI_MAP = {
    "குறிஞ்சி": "Kurinji",
    "குறிஞ்சித் திணை": "Kurinji",
    "குறிஞ்சித்திணை": "Kurinji",
    "முல்லை": "Mullai",
    "முல்லைத் திணை": "Mullai",
    "முல்லைத்திணை": "Mullai",
    "மருதம்": "Marutham",
    "மருதத் திணை": "Marutham",
    "மருதத்திணை": "Marutham",
    "நெய்தல்": "Neytal",
    "நெய்தல் திணை": "Neytal",
    "நெய்தல்த் திணை": "Neytal",
    "நெய்தல்த்திணை": "Neytal",
    "நெய்தற் திணை": "Neytal",
    "நெய்தற்திணை": "Neytal",
    "பாலை": "Palai",
    "பாலைத் திணை": "Palai",
    "பாலைத்திணை": "Palai",
    "கைக்கிளை": "Kaikkilai",
    "கைக்கிளைத் திணை": "Kaikkilai",
    "பெருந்திணை": "Peruntinai",
}

# Speaker role mappings
SPEAKER_PATTERNS = {
    "தலைவி": "talaivi",
    "தலைவன்": "talaivan",
    "தோழி": "tozi",
    "செவிலி": "cevilittay",
    "நற்றாய்": "nattay",
    "பாணன்": "panan",
    "விறலி": "virali",
    "கண்டோர்": "kantor",
    "பரத்தை": "parattai",
    "நுதலி": "nuttay",
}

# Who speaks to whom — speaker extraction
SPEAKER_SAID_PATTERNS = [
    # "தலைவி தோழியிடம் சொன்னது" → speaker = talaivi
    r"(தலைவ[னி]|தோழி|செவிலி|நற்றாய்|பாணன்|பரத்தை|கண்டோர்|விறலி).*(?:சொன்னது|கூறியது|உரைத்தது)",
    # "What the heroine said" → fallback English
    r"What the (heroine|hero|heroine's friend|foster mother|bard|hero's friend).*said",
]


def download_pages(output_dir, text_filter=None):
    """Download HTML pages from Vaidehi's site."""
    import urllib.request
    import urllib.error

    os.makedirs(output_dir, exist_ok=True)

    headers = {
        "User-Agent": "SentamizhCorpus/1.0 (Academic research; Classical Tamil literature)"
    }

    texts = VAIDEHI_PAGES
    if text_filter:
        texts = {k: v for k, v in texts.items() if k == text_filter}

    results = {"success": 0, "failed": 0, "skipped": 0}

    for text_name, pages in texts.items():
        print(f"\n{'='*60}")
        print(f"  {text_name.upper()}")
        print(f"{'='*60}")

        for filename, url, desc in pages:
            filepath = os.path.join(output_dir, filename)

            if os.path.exists(filepath):
                size = os.path.getsize(filepath)
                print(f"  [SKIP] {filename} ({size:,} bytes) — already exists")
                results["skipped"] += 1
                continue

            print(f"  Downloading: {filename}")
            print(f"    URL: {url}")

            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    content = resp.read()
                    with open(filepath, "wb") as f:
                        f.write(content)
                    print(f"    ✓ Saved ({len(content):,} bytes)")
                    results["success"] += 1
            except Exception as e:
                print(f"    ✗ FAILED: {e}")
                results["failed"] += 1

            # Polite delay
            time.sleep(2)

    print(f"\n{'='*60}")
    print(f"  Download complete: {results['success']} downloaded, "
          f"{results['skipped']} skipped, {results['failed']} failed")
    print(f"{'='*60}")
    return results


def extract_tinai(header_text):
    """Extract tinai from poem header text."""
    for tamil, english in TINAI_MAP.items():
        if tamil in header_text:
            return english
    return None


def extract_speaker_role(header_text):
    """Extract speaker role from poem header text."""
    for tamil, role in SPEAKER_PATTERNS.items():
        if tamil in header_text:
            return role
    # English fallback
    lower = header_text.lower()
    if "heroine's friend" in lower or "friend of the heroine" in lower:
        return "tozi"
    if "heroine" in lower:
        return "talaivi"
    if "hero's friend" in lower:
        return "panan"
    if "hero" in lower:
        return "talaivan"
    if "foster mother" in lower:
        return "cevilittay"
    if "bard" in lower:
        return "panan"
    return None


def extract_poet(header_text):
    """Extract poet name from the header line (after poem number, before tinai)."""
    # Pattern: "குறுந்தொகை 1, திப்புத்தோளார், குறிஞ்சித் திணை"
    # or: "நற்றிணை 1, கபிலர், குறிஞ்சித் திணை"
    parts = header_text.split(",")
    if len(parts) >= 2:
        poet = parts[1].strip()
        # Clean up - remove any tinai text that leaked in
        for tinai_tamil in TINAI_MAP:
            if tinai_tamil in poet:
                poet = poet[:poet.index(tinai_tamil)].strip().rstrip(",").rstrip("–").strip()
                break
        if poet and len(poet) > 1:
            return poet
    return None


def is_tamil_text(text):
    """Check if text contains Tamil characters."""
    return bool(re.search(r'[\u0B80-\u0BFF]', text))


def find_real_poem_headers(full_text, tamil_prefix):
    """Find positions of REAL poem headers, filtering out cross-references.

    Real headers follow: "PREFIX N, <poet>, <tinai> திணை – <context>"
    Cross-references look like: "... see PREFIX N, முல்லைப்பாட்டு 11..."

    We distinguish them by checking if "திணை" (or a speaker context marker
    like "சொன்னது") appears within 200 chars of the match.
    """
    header_re = re.compile(
        rf'{re.escape(tamil_prefix)}\s+(\d+)\s*,'
    )

    # Markers that indicate this is a real poem header, not a cross-reference
    # Real headers have tinai or speaker context nearby
    real_markers = ['திணை', 'சொன்னது', 'கூறியது', 'உரைத்தது', 'பாடியது']

    headers = []
    seen_nums = set()

    for match in header_re.finditer(full_text):
        verse_num = int(match.group(1))
        pos = match.start()

        # Look at the next 250 chars after this match for real-header markers
        lookahead = full_text[pos:pos + 250]

        is_real = any(marker in lookahead for marker in real_markers)

        if is_real and verse_num not in seen_nums:
            seen_nums.add(verse_num)
            headers.append((verse_num, pos))

    # Sort by position (should already be, but ensure)
    headers.sort(key=lambda x: x[1])
    return headers


def parse_poems_from_html(html_content, text_name):
    """Parse poems from a Vaidehi HTML page.

    Structure of each poem entry:
      - Header: "குறுந்தொகை N, <poet>, <tinai> திணை – <speaker context>"
      - Tamil verse (classical Tamil, no line break after header)
      - English header: "Kurunthokai N, ..." or "Natrinai N, ..."
      - English translation
      - Notes (optional)

    Key challenges handled:
      - Cross-references (e.g., "see நற்றிணை 40") look like headers but aren't
      - Tamil text often runs directly after header with no newline
      - Some poems have line numbers (5, 10, 15) embedded in verse text
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_content, "html.parser")

    # Get the main content area
    content = soup.find("div", class_="entry-content")
    if not content:
        content = soup.find("article")
    if not content:
        content = soup.body

    full_text = content.get_text()

    # Identify poem header pattern based on text
    if text_name == "kuruntokai":
        tamil_prefix = "குறுந்தொகை"
        eng_prefix = "Kurunthokai"
        alt_eng_prefixes = ["Kurunthokai", "Kuruntokai", "Kuruntogai"]
    elif text_name == "natrinai":
        tamil_prefix = "நற்றிணை"
        eng_prefix = "Natrinai"
        alt_eng_prefixes = ["Natrinai", "Naṟṟiṇai", "Narrinai"]
    else:
        raise ValueError(f"Unknown text: {text_name}")

    # Step 1: Find all REAL poem header positions
    headers = find_real_poem_headers(full_text, tamil_prefix)

    if not headers:
        print(f"    WARNING: No poem headers found!")
        return []

    poems = []

    for i, (verse_num, start_pos) in enumerate(headers):
        # Block runs from this header to the next header (or end of text)
        if i + 1 < len(headers):
            end_pos = headers[i + 1][1]
        else:
            end_pos = len(full_text)

        block = full_text[start_pos:end_pos].strip()

        # --- Extract the Tamil header line ---
        # The header runs from start to the first verse character
        # Pattern: "PREFIX N, poet, tinai திணை – context<verse starts>"
        # Find where the dramatic context ends and verse begins
        # The "சொன்னது" / "கூறியது" / "பாடியது" marks end of context
        context_end_markers = ['சொன்னது', 'கூறியது', 'உரைத்தது', 'பாடியது',
                               'சொல்லியது', 'பாடிய பாட்டு', 'கூற்று']
        header_end = None
        for marker in context_end_markers:
            idx = block.find(marker)
            if idx >= 0:
                header_end = idx + len(marker)
                break

        if header_end is None:
            # Fallback: header ends at "திணை" + some chars
            tinai_idx = block.find('திணை')
            if tinai_idx >= 0:
                # Find the next Tamil verse character after திணை
                after_tinai = block[tinai_idx + 4:]
                # Skip spaces, dashes, and context text until we hit verse
                header_end = tinai_idx + 4 + min(150, len(after_tinai))
            else:
                header_end = min(200, len(block))

        header_text = block[:header_end].strip()

        # Extract metadata from header
        poet = extract_poet(header_text)
        tinai = extract_tinai(header_text)
        speaker_role = extract_speaker_role(header_text)

        # Extract the dramatic context (the "– <context>" part)
        context_match = re.search(r'[–—]\s*(.+)$', header_text)
        dramatic_context = context_match.group(1).strip() if context_match else None

        # --- Split block into Tamil verse and English translation ---
        body_after_header = block[header_end:].strip() if header_end else block

        # Find where English translation starts
        # Look for "Kurunthokai N," or "Natrinai N," in English
        eng_start = None
        for prefix in alt_eng_prefixes:
            eng_pattern = re.compile(
                rf'{re.escape(prefix)}\s+{verse_num}\s*,',
                re.IGNORECASE
            )
            eng_match = eng_pattern.search(block)
            if eng_match:
                eng_start = eng_match.start()
                break

        if eng_start is not None:
            tamil_raw = block[header_end:eng_start].strip() if header_end else block[:eng_start].strip()
            eng_raw = block[eng_start:].strip()
        else:
            # Fallback: split at first long non-Tamil line
            tamil_raw = body_after_header
            eng_raw = ""

        # Clean Tamil text
        # Remove embedded line numbers like "  5" or "  10" at end of lines
        tamil_text = re.sub(r'\s+(\d{1,2})\s*$', '', tamil_raw, flags=re.MULTILINE)
        # Remove any stray English sentences that leaked in
        tamil_lines = []
        for line in tamil_text.split("\n"):
            line = line.strip()
            if line and (is_tamil_text(line) or line.startswith("(") or len(line) < 5):
                tamil_lines.append(line)
        tamil_text = "\n".join(tamil_lines).strip()

        # Process English section
        eng_body = ""
        notes = ""
        if eng_raw:
            # Remove English header line
            eng_header_end = eng_raw.find("\n")
            if eng_header_end > 0:
                eng_body = eng_raw[eng_header_end:].strip()
            else:
                eng_body = eng_raw

            # Separate notes from translation
            notes_patterns = [
                r'\n\s*Notes?\s*[:–—]\s*',
                r'\n\s*Notes?\s*\n',
                r'\n\s*Meanings?\s*[:–—]\s*',
                r'\n\s*Meanings?\s*\n',
            ]
            for np in notes_patterns:
                notes_match = re.search(np, eng_body)
                if notes_match:
                    notes = eng_body[notes_match.end():].strip()
                    eng_body = eng_body[:notes_match.start()].strip()
                    break

        if tamil_text:
            poems.append({
                "verse_number": verse_num,
                "poet": poet,
                "tinai": tinai,
                "speaker_role": speaker_role,
                "dramatic_context": dramatic_context,
                "classical_tamil": tamil_text,
                "english": eng_body if eng_body else None,
                "notes": notes if notes else None,
            })

    return poems


def map_to_schema(poem, text_name, source_url):
    """Map a parsed poem to the 32-field Sentamizh schema.

    All 32 schema fields are included — no more, no less.
    additionalProperties is false in the schema, so no extra fields allowed.
    """
    prefix = "KURU" if text_name == "kuruntokai" else "NATR"
    verse_id = f"{prefix}-{poem['verse_number']:03d}"

    # Build cultural_context from poet name + dramatic context + notes
    context_parts = []
    if poem.get("poet"):
        context_parts.append(f"Poet: {poem['poet']}")
    if poem.get("dramatic_context"):
        context_parts.append(poem["dramatic_context"])
    if poem.get("notes"):
        context_parts.append(f"Notes: {poem['notes']}")
    cultural_context = "; ".join(context_parts) if context_parts else None

    entry = {
        # === CORE LAYER ===
        "verse_id": verse_id,
        "source_text": text_name.capitalize(),
        "layer": "Sangam",
        "period": "3rd century BCE – 3rd century CE",
        "verse_number": str(poem["verse_number"]),
        "classical_tamil": poem["classical_tamil"],
        "modern_tamil": None,
        "english": poem["english"],
        "source_url": source_url,
        "difficulty": "archaic",

        # === TAMIL-NATIVE LAYER ===
        "thinai": poem["tinai"],
        "turai": None,
        "akam_or_puram": "Akam",
        "karu": None,
        "uri": None,
        "ullurai": None,
        "speaker_role": poem["speaker_role"],
        "metre": None,
        "pann": None,
        "dhvani_layer": None,

        # === INTERPRETIVE LAYER ===
        "rasa_primary": None,
        "rasa_secondary": None,
        "themes": None,
        "philosophical_concept": None,
        "cultural_context": cultural_context,
        "storytelling_seed_narrative": None,
        "storytelling_seed_emotional": None,

        # === CROSS-CULTURAL BRIDGE ===
        "nayika_bheda": None,
        "visual_imagery": None,
        "emotional_valence": None,

        # === META ===
        "annotator": None,
        "annotation_confidence": None,
    }
    return entry


def parse_html_files(raw_dir, output_dir, text_filter=None):
    """Parse downloaded HTML files into structured JSON."""
    os.makedirs(output_dir, exist_ok=True)

    texts = VAIDEHI_PAGES
    if text_filter:
        texts = {k: v for k, v in texts.items() if k == text_filter}

    total_poems = 0

    for text_name, pages in texts.items():
        all_poems = []

        print(f"\n{'='*60}")
        print(f"  Parsing {text_name.upper()}")
        print(f"{'='*60}")

        for filename, url, desc in pages:
            filepath = os.path.join(raw_dir, filename)
            if not os.path.exists(filepath):
                print(f"  [SKIP] {filename} — not downloaded yet")
                continue

            print(f"  Parsing: {filename}")
            with open(filepath, "r", encoding="utf-8") as f:
                html_content = f.read()

            poems = parse_poems_from_html(html_content, text_name)
            print(f"    → Extracted {len(poems)} poems")

            # Map to schema
            for poem in poems:
                entry = map_to_schema(poem, text_name, url)
                all_poems.append(entry)

        if all_poems:
            # Sort by verse number
            all_poems.sort(key=lambda x: x["verse_number"])

            # Save JSON
            output_file = os.path.join(
                output_dir,
                f"{text_name.capitalize()}_Vaidehi_All.json"
            )
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(all_poems, f, ensure_ascii=False, indent=2)

            total_poems += len(all_poems)

            # Print stats
            tinai_counts = {}
            for p in all_poems:
                t = p.get("thinai") or "Unknown"
                tinai_counts[t] = tinai_counts.get(t, 0) + 1

            print(f"\n  Total poems: {len(all_poems)}")
            print(f"  Tinai distribution:")
            for t, c in sorted(tinai_counts.items(), key=lambda x: -x[1]):
                print(f"    {t}: {c}")
            print(f"  Saved to: {output_file}")

            # Count Tamil character length
            tamil_chars = sum(
                len(re.findall(r'[\u0B80-\u0BFF]', p["classical_tamil"]))
                for p in all_poems
            )
            print(f"  Total Tamil characters: {tamil_chars:,}")

    print(f"\n{'='*60}")
    print(f"  Grand total: {total_poems} poems extracted")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="Download and parse Kuruntokai/Natrinai from Vaidehi's Sangam translations"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw"),
        help="Directory for downloaded HTML files (default: ../data/raw)"
    )
    parser.add_argument(
        "--processed-dir",
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "processed"),
        help="Directory for parsed JSON output (default: ../data/processed)"
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Only download HTML pages, don't parse"
    )
    parser.add_argument(
        "--parse-only",
        action="store_true",
        help="Only parse already-downloaded HTML files"
    )
    parser.add_argument(
        "--text", "-t",
        choices=["kuruntokai", "natrinai"],
        help="Process only one text"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without downloading"
    )

    args = parser.parse_args()

    print("Sentamizh Corpus — Vaidehi Sangam Extractor")
    print(f"Raw HTML dir: {os.path.abspath(args.output_dir)}")
    print(f"Processed dir: {os.path.abspath(args.processed_dir)}")

    if args.dry_run:
        print("\nDRY RUN — Pages that would be downloaded:\n")
        texts = VAIDEHI_PAGES
        if args.text:
            texts = {k: v for k, v in texts.items() if k == args.text}
        for text_name, pages in texts.items():
            print(f"  {text_name.upper()}:")
            for filename, url, desc in pages:
                filepath = os.path.join(args.output_dir, filename)
                exists = " [EXISTS]" if os.path.exists(filepath) else ""
                print(f"    {filename}{exists}")
                print(f"      URL: {url}")
                print(f"      {desc}")
            print()
        return

    if not args.parse_only:
        download_pages(args.output_dir, text_filter=args.text)

    if not args.download_only:
        try:
            from bs4 import BeautifulSoup  # noqa: F401
        except ImportError:
            print("\n⚠  beautifulsoup4 is required for parsing.")
            print("   Install it with: pip install beautifulsoup4")
            print("   Then re-run with --parse-only")
            sys.exit(1)

        parse_html_files(args.output_dir, args.processed_dir, text_filter=args.text)


if __name__ == "__main__":
    main()
