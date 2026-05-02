#!/usr/bin/env python3
"""
Sentamizh Corpus — Schema Validator

Validates JSON corpus entries against the Sentamizh schema.
Usage:
    python validate.py <path_to_json_file>
    python validate.py ../samples/sample_entry.json
    python validate.py ../data/seed_corpus/   (validates all .json files in directory)
"""

import json
import sys
import os
from collections import Counter
from pathlib import Path

try:
    import jsonschema
    from jsonschema import validate, ValidationError, Draft202012Validator
except ImportError:
    print("Installing jsonschema...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "jsonschema", "--break-system-packages", "-q"])
    import jsonschema
    from jsonschema import validate, ValidationError, Draft202012Validator


SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "sentamizh_schema.json"


def load_schema():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_entry(entry: dict, schema: dict, entry_label: str = "") -> list[str]:
    """Validate a single corpus entry. Returns list of error messages."""
    errors = []
    validator = Draft202012Validator(schema)

    for error in sorted(validator.iter_errors(entry), key=lambda e: list(e.path)):
        field = " -> ".join(str(p) for p in error.path) if error.path else "(root)"
        errors.append(f"  [{entry_label}] {field}: {error.message}")

    # Additional cross-field checks beyond JSON Schema
    if not errors:
        errors.extend(cross_field_checks(entry, entry_label))

    return errors


def cross_field_checks(entry: dict, label: str) -> list[str]:
    """Business logic checks that JSON Schema alone can't enforce."""
    errors = []

    # Sangam texts should have akam_or_puram set
    sangam_texts = {"Purananuru", "Akananuru", "Kuruntokai", "Natrinai"}
    if entry.get("source_text") in sangam_texts:
        if not entry.get("akam_or_puram"):
            errors.append(f"  [{label}] akam_or_puram: Sangam text '{entry['source_text']}' should specify Akam or Puram")

        # Akam poems should have thinai
        if entry.get("akam_or_puram") == "Akam" and not entry.get("thinai"):
            errors.append(f"  [{label}] thinai: Akam poem should specify a Thinai landscape")

    # Thinai should only be set for Sangam Akam poems
    if entry.get("thinai") and entry.get("layer") != "Sangam":
        errors.append(f"  [{label}] thinai: Thinai should only be set for Sangam layer texts")

    # Turai should only be set for Sangam texts
    if entry.get("turai") and entry.get("layer") != "Sangam":
        errors.append(f"  [{label}] turai: Turai sub-genre should only be set for Sangam layer texts")

    # Ullurai primarily for Sangam Akam poetry
    if entry.get("ullurai") and entry.get("akam_or_puram") == "Puram":
        errors.append(f"  [{label}] ullurai: Metaphorical landscape-emotion correlation is primarily for Akam poetry, not Puram. Verify if intentional.")

    # Nayika bheda should not be set for Didactic or purely Puram texts
    if entry.get("nayika_bheda") and entry.get("layer") == "Didactic":
        errors.append(f"  [{label}] nayika_bheda: Heroine-state classification is not applicable to Didactic layer texts")

    # Pann is primarily for Bhakti layer
    if entry.get("pann") and entry.get("layer") not in ("Bhakti", "Spiritual"):
        errors.append(f"  [{label}] pann: Melodic mode annotation is primarily for Bhakti/Spiritual layer texts. Verify if intentional.")

    # emotional_valence must have required sub-fields if present
    ev = entry.get("emotional_valence")
    if ev is not None:
        if not isinstance(ev, dict):
            errors.append(f"  [{label}] emotional_valence: Must be an object with 'primary' and 'intensity' fields")
        else:
            if "primary" not in ev:
                errors.append(f"  [{label}] emotional_valence.primary: Required field missing")
            if "intensity" not in ev:
                errors.append(f"  [{label}] emotional_valence.intensity: Required field missing")

    # verse_id prefix should match source_text
    prefix_map = {
        "Purananuru": "PURN",
        "Akananuru": "AKAM",
        "Kuruntokai": "KURU",
        "Natrinai": "NATR",
        "Divya Prabandham": "DIVA",
        "Thirumurai": "THIR",
        "Thevaram": "THEV",
        "Thirumanthiram": "THIR",
        "Silappatikaram": "SILA",
        "Manimekalai": "MANI",
        "Naladiyar": "NALA",
        "Pazhamozhi": "PAZH",
        "Deivathin Kural": "DEIV",
        "Yaeni Padigal Manthirankal": "YAEN",
    }
    expected_prefix = prefix_map.get(entry.get("source_text", ""))
    if expected_prefix and entry.get("verse_id"):
        actual_prefix = entry["verse_id"].split("-")[0]
        if actual_prefix != expected_prefix:
            errors.append(
                f"  [{label}] verse_id: Expected prefix '{expected_prefix}' for {entry['source_text']}, got '{actual_prefix}'"
            )

    return errors


def validate_file(filepath: Path, schema: dict) -> tuple[int, int, list[str]]:
    """Validate a JSON file (single entry or array of entries). Returns (total, passed, errors).

    Read errors (OSError, JSONDecodeError) and unexpected JSON shapes are reported
    as a single error and the file is otherwise skipped — they don't crash the run.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        return 0, 0, [f"  [{filepath.name}] read error: {e}"]
    except json.JSONDecodeError as e:
        return 0, 0, [f"  [{filepath.name}] invalid JSON: {e}"]

    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        entries = [data]
    else:
        return 0, 0, [f"  [{filepath.name}] unexpected JSON type: {type(data).__name__}"]

    all_errors = []

    # File-level: detect duplicate verse_ids before we go entry-by-entry.
    # JSON Schema can't express uniqueness across an array, so we do it here.
    ids = [e.get("verse_id") for e in entries if isinstance(e, dict) and e.get("verse_id")]
    dupes = {vid: n for vid, n in Counter(ids).items() if n > 1}
    if dupes:
        for vid, n in sorted(dupes.items()):
            all_errors.append(f"  [{filepath.name}] duplicate verse_id '{vid}' appears {n} times")

    passed = 0
    for i, entry in enumerate(entries):
        label = entry.get("verse_id", f"entry_{i}") if isinstance(entry, dict) else f"entry_{i}"
        errs = validate_entry(entry, schema, label)
        if errs:
            all_errors.extend(errs)
        else:
            passed += 1

    return len(entries), passed, all_errors


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate.py <file_or_directory>")
        sys.exit(1)

    target = Path(sys.argv[1])
    schema = load_schema()

    if target.is_dir():
        # Top-level only by default — recursing picks up intermediate
        # extraction artifacts in subfolders like _intermediates/ and
        # double-counts. Pass an explicit file path to validate one
        # of those directly.
        files = sorted(
            f for f in target.glob("*.json")
            # Skip non-corpus shapes the run_all pipeline drops here.
            if f.name not in {"corpus_statistics.json"}
            and not f.name.startswith("_")
        )
        if not files:
            print(f"No corpus .json files found in {target}")
            sys.exit(1)
    elif target.is_file():
        files = [target]
    else:
        print(f"Not found: {target}")
        sys.exit(1)

    total_entries = 0
    total_passed = 0
    total_errors = []

    for f in files:
        print(f"Validating: {f.name}")
        count, passed, errors = validate_file(f, schema)
        total_entries += count
        total_passed += passed
        total_errors.extend(errors)

        if errors:
            for e in errors:
                print(e)
        else:
            print(f"  All {count} entries valid.")

    print(f"\n{'='*50}")
    print(f"Total: {total_entries} entries | {total_passed} passed | {total_entries - total_passed} failed")

    if total_errors:
        print(f"\n{len(total_errors)} validation error(s) found.")
        sys.exit(1)
    else:
        print("All entries passed validation.")
        sys.exit(0)


if __name__ == "__main__":
    main()
