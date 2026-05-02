#!/usr/bin/env python3
"""
Sentamizh Corpus Master Orchestration Script

Coordinates the entire extraction, validation, and annotation pipeline for the
Sentamizh Corpus. This is the single entry point for processing the full corpus.

Pipeline stages:
  1. Extract — Extract all texts to JSON
  2. Validate — Validate extracted JSON against schema
  3. Integrate PaaPeyarchi — Fill modern_tamil field
  4. Annotate — Run LLM annotation (optional)
  5. Statistics — Generate corpus-wide statistics

Usage:
  python run_all.py                          # Run all stages
  python run_all.py --stage 1                # Run extraction only
  python run_all.py --stage 2 --verbose      # Run validation with verbose output
  python run_all.py --text purananuru        # Process only Purananuru
  python run_all.py --annotate --backend anthropic --model claude-sonnet-4-20250514
  python run_all.py --dry-run --verbose      # Show what would be done
  python run_all.py --skip-download          # Skip re-downloading HTML files
"""

import json
import sys
import os
import argparse
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import defaultdict


# ─── Colors & Formatting ───────────────────────────────────────────────────

class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str, level: int = 1):
    """Print a formatted header."""
    if level == 1:
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}{text:^70}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}\n")
    elif level == 2:
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'─'*70}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'─'*70}{Colors.RESET}")


def print_stage(stage_num: int, text: str):
    """Print stage indicator."""
    print(f"\n{Colors.BOLD}{Colors.YELLOW}STAGE {stage_num}: {text}{Colors.RESET}")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")


# ─── Configuration ─────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EXTERNAL_DIR = DATA_DIR / "external"
SCHEMAS_DIR = PROJECT_ROOT / "schemas"

# Define all texts in the corpus with their extraction script and file count.
#
# The `parts` field lists raw HTML filenames (in data/raw/) that should be
# extracted individually and merged. When present, stage_extract() loops the
# extraction script over each part with `--output <per_part>.json` and then
# merges+dedupes into the final `output` file.
#
# Purananuru uses its own internal orchestrator (extract_all_purananuru.py)
# so it deliberately has no `parts` entry — the script iterates parts itself.
CORPUS_TEXTS = {
    "purananuru": {
        "script": "extract_all_purananuru.py",
        "output": "Purananuru_All.json",
        "verses": 400,
        "description": "Purananuru (Ancient Tamil Ethics)",
        # No `parts` — extract_all_purananuru.py has its own PARTS_CONFIG.
    },
    "akananuru": {
        "script": "extract_akananuru.py",
        "output": "Akananuru_All.json",
        "verses": 400,
        "description": "Akananuru (Sangam Love Poetry)",
        "parts": [
            "Akananuru_Ed1_Part1.html",
            "Akananuru_Ed1_Part2.html",
            "Akananuru_Ed2_Part1.html",
            "Akananuru_Ed2_Part2.html",
            "Akananuru_Ed3.html",
        ],
    },
    "thevaram": {
        "script": "extract_thevaram.py",
        "output": "Thevaram_All.json",
        "verses": 4000,
        "description": "Thevaram (Bhakti Sacred Hymns)",
        "parts": [
            "Thevaram_Thirumurai1_Part1.html",
            "Thevaram_Thirumurai1_Part2.html",
            "Thevaram_Thirumurai2_Part1.html",
            "Thevaram_Thirumurai2_Part2.html",
            "Thevaram_Thirumurai3_Part1.html",
            "Thevaram_Thirumurai3_Part2.html",
        ],
    },
    "divya_prabandham": {
        "script": "extract_divya_prabandham.py",
        "output": "Divya_Prabandham_All.json",
        "verses": 4000,
        "description": "Divya Prabandham (Vaishnavite Bhakti)",
        "parts": [
            "Divya_Prabandham_Mudhal_Ayiram_1.html",
            "Divya_Prabandham_Mudhal_Ayiram_2.html",
            "Divya_Prabandham_Periya_Thirumozhi_1.html",
            "Divya_Prabandham_Periya_Thirumozhi_2.html",
            "Divya_Prabandham_Iramanusa_1.html",
            "Divya_Prabandham_Iramanusa_2.html",
            "Divya_Prabandham_Siru_Thirumurai.html",
        ],
    },
    "silappatikaram": {
        "script": "extract_silappatikaram.py",
        "output": "Silappatikaram_All.json",
        "verses": None,
        "description": "Silappatikaram (Sangam Epic)",
        "parts": [
            "Silappatikaram_Pukar_Part1.html",
            "Silappatikaram_Pukar_Part2.html",
            "Silappatikaram_Pukar_Part3.html",
        ],
    },
    "manimekalai": {
        "script": "extract_manimekalai.py",
        "output": "Manimekalai_All.json",
        "verses": None,
        "description": "Manimekalai (Sangam Epic)",
        "parts": [
            "Manimekalai.html",
            "Manimekalai_Summary_Part1.html",
            "Manimekalai_Summary_Part2.html",
        ],
    },
    "thirumanthiram": {
        "script": "extract_thirumanthiram.py",
        "output": "Thirumanthiram_All.json",
        "verses": 3000,
        "description": "Thirumanthiram (Shaivite Tantra)",
        "parts": [
            "Thirumanthiram.html",
        ],
    },
    "kuruntokai": {
        "script": None,  # Pre-extracted via download_vaidehi_sangam.py
        "output": "Kuruntokai_Vaidehi_All.json",
        "verses": 400,
        "description": "Kuruntokai (Sangam Love Poetry)",
    },
    "natrinai": {
        "script": None,  # Pre-extracted via download_vaidehi_sangam.py
        "output": "Natrinai_Vaidehi_All.json",
        "verses": 400,
        "description": "Natrinai (Sangam Love Poetry)",
    },
}


def merge_and_dedupe_json_parts(part_paths: List[Path], output_path: Path) -> int:
    """
    Merge multiple per-part JSON files into a single deduplicated list.

    Each part file is expected to contain a JSON array of entries. Entries
    are deduplicated by `verse_id`; when duplicates collide, the entry with
    more non-null fields wins (mirrors extract_all_purananuru.py's policy).

    Returns:
        Number of entries in the merged file.
    """
    from collections import defaultdict

    all_entries: List[Dict] = []
    for p in part_paths:
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            # Don't silently drop a corrupted part — surface it. The merge
            # continues so a single bad part doesn't kill the whole run,
            # but the operator gets a chance to re-extract it.
            print_warning(f"merge: skipping {p.name} (invalid JSON: {e})")
            continue
        except OSError as e:
            print_warning(f"merge: skipping {p.name} (read error: {e})")
            continue
        if isinstance(data, list):
            all_entries.extend(data)
        else:
            print_warning(
                f"merge: skipping {p.name} "
                f"(top-level is {type(data).__name__}, expected list)"
            )

    def nonnull_count(entry: Dict) -> int:
        return sum(1 for v in entry.values() if v not in (None, "", [], {}))

    by_id: Dict[str, List[Dict]] = defaultdict(list)
    no_id: List[Dict] = []
    for e in all_entries:
        vid = e.get("verse_id")
        if vid:
            by_id[vid].append(e)
        else:
            no_id.append(e)

    merged = []
    for vid in sorted(by_id.keys()):
        merged.append(max(by_id[vid], key=nonnull_count))
    merged.extend(no_id)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(merged)


# ─── Utility Functions ──────────────────────────────────────────────────────

def run_command(cmd: List[str], description: str, verbose: bool = False) -> Tuple[bool, str]:
    """
    Run a shell command and capture output.

    Args:
        cmd: Command and arguments as list
        description: Human-readable description
        verbose: If True, print command output

    Returns:
        Tuple of (success: bool, output: str)
    """
    try:
        if verbose:
            print_info(f"Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout per command
            cwd=str(SCRIPTS_DIR)
        )

        output = result.stdout + result.stderr

        if result.returncode == 0:
            if verbose and output:
                print(output)
            return True, output
        else:
            return False, output

    except subprocess.TimeoutExpired:
        return False, f"Command timed out after 300 seconds: {' '.join(cmd)}"
    except Exception as e:
        return False, f"Error running command: {str(e)}"


def file_exists(path: Path) -> bool:
    """Check if a file exists."""
    return path.exists() and path.is_file()


def count_json_entries(filepath: Path) -> int:
    """Count entries in a JSON file (array or single object)."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return len(data)
        elif isinstance(data, dict):
            return 1
        return 0
    except Exception as e:
        return -1


def get_file_size_mb(filepath: Path) -> float:
    """Get file size in MB."""
    if filepath.exists():
        return filepath.stat().st_size / (1024 * 1024)
    return 0.0


# ─── Stage Functions ───────────────────────────────────────────────────────

def stage_extract(texts: List[str], skip_download: bool = False,
                  verbose: bool = False, dry_run: bool = False) -> Dict[str, Dict]:
    """
    Stage 1: Extract all texts.

    Returns dict with extraction results:
    {
        "text_name": {
            "success": bool,
            "output_file": str,
            "entries": int,
            "size_mb": float,
            "error": str (if failed)
        }
    }
    """
    print_stage(1, "EXTRACT — Extract all texts to JSON")

    results = {}

    for text_name in texts:
        if text_name not in CORPUS_TEXTS:
            print_warning(f"Unknown text: {text_name}")
            continue

        text_info = CORPUS_TEXTS[text_name]
        script = text_info.get("script")
        output_file = text_info["output"]
        output_path = PROCESSED_DIR / output_file
        description = text_info["description"]

        print_info(f"Extracting {text_name}: {description}")

        # Some texts are pre-extracted (kuruntokai, natrinai)
        if script is None:
            if file_exists(output_path):
                entries = count_json_entries(output_path)
                size_mb = get_file_size_mb(output_path)
                print_success(f"{text_name}: Already extracted ({entries} entries, {size_mb:.1f} MB)")
                results[text_name] = {
                    "success": True,
                    "output_file": str(output_path),
                    "entries": entries,
                    "size_mb": size_mb,
                }
            else:
                print_warning(f"{text_name}: Output file not found at {output_path}")
                results[text_name] = {
                    "success": False,
                    "output_file": str(output_path),
                    "entries": 0,
                    "size_mb": 0.0,
                    "error": "Output file does not exist (may need download_vaidehi_sangam.py)"
                }
            continue

        # Skip extraction if output already exists and not forcing
        if file_exists(output_path):
            entries = count_json_entries(output_path)
            size_mb = get_file_size_mb(output_path)
            print_info(f"{text_name}: Already extracted ({entries} entries, {size_mb:.1f} MB)")
            results[text_name] = {
                "success": True,
                "output_file": str(output_path),
                "entries": entries,
                "size_mb": size_mb,
            }
            continue

        # Does this text use per-part orchestration, or does its script
        # handle multi-part iteration internally?
        parts = text_info.get("parts")

        if dry_run:
            if parts:
                print_info(f"[DRY RUN] Would extract {len(parts)} parts and merge → {output_file}")
            else:
                print_info(f"[DRY RUN] Would run: python {script}")
            results[text_name] = {
                "success": True,
                "output_file": str(output_path),
                "entries": 0,
                "size_mb": 0.0,
                "dry_run": True,
            }
            continue

        # Branch A: per-part extraction + merge
        if parts:
            part_json_paths: List[Path] = []
            failed_parts: List[str] = []
            for part_html in parts:
                part_path = RAW_DIR / part_html
                if not part_path.exists():
                    print_warning(f"  Missing raw file: {part_html}")
                    failed_parts.append(part_html)
                    continue

                # Intermediate per-part JSON; cleaned up after merge.
                per_part_json = PROCESSED_DIR / f".{Path(part_html).stem}.part.json"
                cmd = [
                    sys.executable, script,
                    str(part_path),
                    "--output", str(per_part_json),
                ]
                part_success, part_output = run_command(
                    cmd,
                    f"Extract {part_html}",
                    verbose=verbose,
                )
                if part_success and per_part_json.exists():
                    part_json_paths.append(per_part_json)
                else:
                    print_warning(f"  {part_html}: extraction failed")
                    failed_parts.append(part_html)

            if part_json_paths:
                total = merge_and_dedupe_json_parts(part_json_paths, output_path)
                # Clean up intermediate per-part files
                for p in part_json_paths:
                    try:
                        p.unlink()
                    except OSError:
                        pass
                size_mb = get_file_size_mb(output_path)
                if failed_parts:
                    print_warning(
                        f"{text_name}: Extracted {total} entries from "
                        f"{len(part_json_paths)}/{len(parts)} parts "
                        f"(failed: {failed_parts})"
                    )
                else:
                    print_success(
                        f"{text_name}: Extracted {total} entries from "
                        f"{len(parts)} parts ({size_mb:.1f} MB)"
                    )
                results[text_name] = {
                    "success": not failed_parts,
                    "output_file": str(output_path),
                    "entries": total,
                    "size_mb": size_mb,
                    "parts_extracted": len(part_json_paths),
                    "parts_failed": failed_parts,
                }
            else:
                print_error(f"{text_name}: All parts failed extraction")
                results[text_name] = {
                    "success": False,
                    "output_file": str(output_path),
                    "entries": 0,
                    "size_mb": 0.0,
                    "error": f"All {len(parts)} parts failed",
                    "parts_failed": failed_parts,
                }
            continue

        # Branch B: self-orchestrating script (e.g. extract_all_purananuru.py)
        success, output = run_command(
            [sys.executable, script],
            f"Extract {text_name}",
            verbose=verbose
        )

        if success:
            if file_exists(output_path):
                entries = count_json_entries(output_path)
                size_mb = get_file_size_mb(output_path)
                print_success(f"{text_name}: Extracted {entries} entries ({size_mb:.1f} MB)")
                results[text_name] = {
                    "success": True,
                    "output_file": str(output_path),
                    "entries": entries,
                    "size_mb": size_mb,
                }
            else:
                print_error(f"{text_name}: Script succeeded but output file not found")
                results[text_name] = {
                    "success": False,
                    "output_file": str(output_path),
                    "entries": 0,
                    "size_mb": 0.0,
                    "error": "Output file not created by extraction script"
                }
        else:
            print_error(f"{text_name}: Extraction failed")
            results[text_name] = {
                "success": False,
                "output_file": str(output_path),
                "entries": 0,
                "size_mb": 0.0,
                "error": output[:200] if output else "Unknown error"
            }

    return results


def stage_validate(texts: List[str], extraction_results: Dict,
                   verbose: bool = False, dry_run: bool = False) -> Dict[str, Dict]:
    """
    Stage 2: Validate all extracted JSON files.

    Returns dict with validation results.
    """
    print_stage(2, "VALIDATE — Validate extracted JSON against schema")

    results = {}

    for text_name in texts:
        if text_name not in CORPUS_TEXTS:
            continue

        text_info = CORPUS_TEXTS[text_name]
        output_file = text_info["output"]
        output_path = PROCESSED_DIR / output_file

        # Skip if extraction failed
        if text_name in extraction_results and not extraction_results[text_name]["success"]:
            print_warning(f"{text_name}: Skipping validation (extraction failed)")
            results[text_name] = {"success": False, "error": "Extraction failed"}
            continue

        if not file_exists(output_path):
            print_warning(f"{text_name}: Output file not found, skipping validation")
            results[text_name] = {"success": False, "error": "Output file not found"}
            continue

        if dry_run:
            print_info(f"[DRY RUN] Would validate: {output_path.name}")
            results[text_name] = {"success": True, "dry_run": True, "entries": 0, "passed": 0}
            continue

        print_info(f"Validating {text_name}...")

        success, output = run_command(
            [sys.executable, "validate.py", str(output_path)],
            f"Validate {text_name}",
            verbose=verbose
        )

        if success:
            print_success(f"{text_name}: Validation passed")
            results[text_name] = {"success": True}
        else:
            print_error(f"{text_name}: Validation failed")
            results[text_name] = {
                "success": False,
                "error": output[:500] if output else "Validation failed"
            }

    return results


def stage_integrate_paapeyarchi(texts: List[str],
                                verbose: bool = False, dry_run: bool = False) -> Dict[str, Dict]:
    """
    Stage 3: Integrate PaaPeyarchi data to fill modern_tamil field.

    Returns dict with integration results.
    """
    print_stage(3, "INTEGRATE PaaPeyarchi — Fill modern_tamil field")

    paapeyarchi_path = EXTERNAL_DIR / "PaaPeyarchi_train.json"

    if not file_exists(paapeyarchi_path):
        print_error(f"PaaPeyarchi file not found at {paapeyarchi_path}")
        print_warning("Skipping PaaPeyarchi integration stage")
        return {text: {"success": False, "error": "PaaPeyarchi file not found"} for text in texts}

    results = {}

    for text_name in texts:
        if text_name not in CORPUS_TEXTS:
            continue

        text_info = CORPUS_TEXTS[text_name]
        output_file = text_info["output"]
        output_path = PROCESSED_DIR / output_file

        if not file_exists(output_path):
            print_warning(f"{text_name}: Output file not found, skipping integration")
            results[text_name] = {"success": False, "error": "Output file not found"}
            continue

        if dry_run:
            print_info(f"[DRY RUN] Would integrate PaaPeyarchi for: {text_name}")
            results[text_name] = {"success": True, "dry_run": True}
            continue

        print_info(f"Integrating PaaPeyarchi for {text_name}...")

        success, output = run_command(
            [sys.executable, "integrate_paapeyarchi.py", str(output_path), "--paapeyarchi", str(paapeyarchi_path)],
            f"Integrate PaaPeyarchi for {text_name}",
            verbose=verbose
        )

        if success:
            print_success(f"{text_name}: PaaPeyarchi integration completed")
            results[text_name] = {"success": True}
        else:
            print_warning(f"{text_name}: PaaPeyarchi integration failed or partially completed")
            results[text_name] = {
                "success": False,
                "error": output[:200] if output else "Integration failed"
            }

    return results


def stage_annotate(texts: List[str], backend: Optional[str] = None,
                   model: Optional[str] = None, max_entries: Optional[int] = None,
                   verbose: bool = False, dry_run: bool = False) -> Dict[str, Dict]:
    """
    Stage 4: Run LLM annotation on extracted entries.

    Returns dict with annotation results.
    """
    print_stage(4, "ANNOTATE — Run LLM annotation (optional)")

    if backend is None:
        print_warning("No backend specified. Skipping annotation stage.")
        print_info("To enable annotation, use: --annotate --backend anthropic --model <model-name>")
        return {text: {"success": False, "error": "Annotation not enabled"} for text in texts}

    results = {}

    for text_name in texts:
        if text_name not in CORPUS_TEXTS:
            continue

        text_info = CORPUS_TEXTS[text_name]
        output_file = text_info["output"]
        output_path = PROCESSED_DIR / output_file

        if not file_exists(output_path):
            print_warning(f"{text_name}: Output file not found, skipping annotation")
            results[text_name] = {"success": False, "error": "Output file not found"}
            continue

        print_info(f"Annotating {text_name} with {backend} ({model})...")

        cmd = [
            sys.executable, "annotate_entries.py", str(output_path),
            "--backend", backend,
            "--model", model,
        ]

        if max_entries:
            cmd.extend(["--max-entries", str(max_entries)])

        if dry_run:
            print_info(f"[DRY RUN] Would run: {' '.join(cmd)}")
            results[text_name] = {"success": True, "dry_run": True}
            continue

        success, output = run_command(
            cmd,
            f"Annotate {text_name}",
            verbose=verbose
        )

        if success:
            print_success(f"{text_name}: Annotation completed")
            results[text_name] = {"success": True}
        else:
            print_error(f"{text_name}: Annotation failed")
            results[text_name] = {
                "success": False,
                "error": output[:200] if output else "Annotation failed"
            }

    return results


def stage_statistics(texts: List[str], verbose: bool = False) -> Dict[str, any]:
    """
    Stage 5: Generate corpus-wide statistics report.

    Returns dict with corpus statistics.
    """
    print_stage(5, "STATISTICS — Generate corpus-wide statistics")

    stats = {
        "timestamp": datetime.now().isoformat(),
        "texts": {},
        "totals": {
            "texts_processed": 0,
            "total_entries": 0,
            "total_size_mb": 0.0,
            "texts_success": 0,
            "texts_failed": 0,
        }
    }

    for text_name in texts:
        if text_name not in CORPUS_TEXTS:
            continue

        text_info = CORPUS_TEXTS[text_name]
        output_file = text_info["output"]
        output_path = PROCESSED_DIR / output_file

        if file_exists(output_path):
            entries = count_json_entries(output_path)
            size_mb = get_file_size_mb(output_path)

            stats["texts"][text_name] = {
                "file": output_file,
                "entries": entries,
                "size_mb": round(size_mb, 2),
                "description": text_info["description"],
            }

            stats["totals"]["texts_processed"] += 1
            stats["totals"]["total_entries"] += entries
            stats["totals"]["total_size_mb"] += size_mb
            stats["totals"]["texts_success"] += 1

            print_success(f"{text_name}: {entries:,} entries ({size_mb:.1f} MB)")
        else:
            stats["texts"][text_name] = {
                "file": output_file,
                "entries": 0,
                "size_mb": 0.0,
                "status": "missing"
            }
            stats["totals"]["texts_failed"] += 1
            print_warning(f"{text_name}: Output file missing")

    # Save statistics to file
    stats_file = PROCESSED_DIR / "corpus_statistics.json"
    try:
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        print_success(f"Statistics saved to {stats_file.name}")
    except Exception as e:
        print_error(f"Failed to save statistics: {e}")

    return stats


def print_summary(extraction_results: Dict = None, validation_results: Dict = None,
                  integration_results: Dict = None, annotation_results: Dict = None,
                  statistics: Dict = None):
    """Print comprehensive summary report."""
    print_header("EXECUTION SUMMARY", level=1)

    if extraction_results:
        print_header("Extraction Results", level=2)
        success_count = sum(1 for r in extraction_results.values() if r["success"])
        print(f"Texts extracted: {success_count}/{len(extraction_results)}")
        total_entries = sum(r.get("entries", 0) for r in extraction_results.values())
        total_size = sum(r.get("size_mb", 0) for r in extraction_results.values())
        print(f"Total entries: {total_entries:,}")
        print(f"Total size: {total_size:.1f} MB")

        for text, result in extraction_results.items():
            status = "✓" if result["success"] else "✗"
            entries = result.get("entries", "?")
            print(f"  {status} {text}: {entries} entries")

    if validation_results:
        print_header("Validation Results", level=2)
        success_count = sum(1 for r in validation_results.values() if r.get("success"))
        print(f"Texts validated: {success_count}/{len(validation_results)}")

    if integration_results:
        print_header("PaaPeyarchi Integration Results", level=2)
        success_count = sum(1 for r in integration_results.values() if r.get("success"))
        print(f"Texts integrated: {success_count}/{len(integration_results)}")

    if annotation_results:
        print_header("Annotation Results", level=2)
        success_count = sum(1 for r in annotation_results.values() if r.get("success"))
        print(f"Texts annotated: {success_count}/{len(annotation_results)}")

    if statistics:
        print_header("Corpus Statistics", level=2)
        totals = statistics.get("totals", {})
        print(f"Texts processed: {totals.get('texts_processed', 0)}")
        print(f"Total entries: {totals.get('total_entries', 0):,}")
        print(f"Total size: {totals.get('total_size_mb', 0):.1f} MB")
        print(f"Success: {totals.get('texts_success', 0)} | Failed: {totals.get('texts_failed', 0)}")


# ─── Main Orchestration ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Sentamizh Corpus Master Orchestration Script",
        epilog="Examples:\n"
               "  python run_all.py                                    # Run all stages\n"
               "  python run_all.py --stage 1                          # Extract only\n"
               "  python run_all.py --text purananuru                  # One text only\n"
               "  python run_all.py --annotate --backend anthropic     # With annotation\n"
               "  python run_all.py --dry-run --verbose                # Dry run\n",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--stage",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="Run only a specific stage (1=Extract, 2=Validate, 3=Integrate, 4=Annotate, 5=Statistics)"
    )

    parser.add_argument(
        "--text",
        type=str,
        choices=list(CORPUS_TEXTS.keys()),
        help="Process only one specific text"
    )

    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip re-downloading HTML files"
    )

    parser.add_argument(
        "--annotate",
        action="store_true",
        help="Enable LLM annotation (Stage 4). Skipped by default — annotation is "
             "the most expensive stage and Phase 1 prefers manual annotation via "
             "the annotator/ web app.",
    )

    parser.add_argument(
        "--backend",
        type=str,
        choices=["anthropic", "openai"],
        help="LLM backend for annotation (anthropic or openai)"
    )

    parser.add_argument(
        "--model",
        type=str,
        help="LLM model name (e.g., claude-sonnet-4-20250514, gpt-4)"
    )

    parser.add_argument(
        "--max-entries",
        type=int,
        help="Maximum entries to annotate per text (for testing)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without executing"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed output including command outputs"
    )

    args = parser.parse_args()

    # Validate project structure
    if not PROCESSED_DIR.exists():
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    if not SCHEMAS_DIR.exists():
        print_error(f"Schema directory not found: {SCHEMAS_DIR}")
        sys.exit(1)

    # Determine which texts to process
    texts_to_process = [args.text] if args.text else list(CORPUS_TEXTS.keys())

    # Determine which stages to run
    stages_to_run = [args.stage] if args.stage else [1, 2, 3, 4, 5]

    # Annotation is opt-in: Stage 4 only runs when --annotate is passed.
    # When the user explicitly asks for `--stage 4`, that implies --annotate.
    if args.stage == 4 and not args.annotate:
        args.annotate = True
    if not args.annotate and 4 in stages_to_run:
        stages_to_run.remove(4)

    if args.annotate and not args.backend:
        print_error("--annotate requires --backend to be specified")
        sys.exit(1)

    if args.annotate and not args.model:
        print_error("--annotate requires --model to be specified")
        sys.exit(1)

    # Print header
    print_header("SENTAMIZH CORPUS MASTER ORCHESTRATION SCRIPT")
    print_info(f"Project root: {PROJECT_ROOT}")
    print_info(f"Texts to process: {', '.join(texts_to_process)}")
    print_info(f"Stages to run: {', '.join(str(s) for s in stages_to_run)}")

    if args.dry_run:
        print_warning("DRY RUN MODE - No changes will be made")

    start_time = time.time()

    # Track results
    all_results = {}

    # ─── Stage 1: Extract ──────────────────────────────────────────────────
    if 1 in stages_to_run:
        all_results["extraction"] = stage_extract(
            texts_to_process,
            skip_download=args.skip_download,
            verbose=args.verbose,
            dry_run=args.dry_run
        )
    else:
        all_results["extraction"] = {}

    # ─── Stage 2: Validate ────────────────────────────────────────────────
    if 2 in stages_to_run:
        all_results["validation"] = stage_validate(
            texts_to_process,
            all_results["extraction"],
            verbose=args.verbose,
            dry_run=args.dry_run
        )
    else:
        all_results["validation"] = {}

    # ─── Stage 3: Integrate PaaPeyarchi ───────────────────────────────────
    if 3 in stages_to_run:
        all_results["integration"] = stage_integrate_paapeyarchi(
            texts_to_process,
            verbose=args.verbose,
            dry_run=args.dry_run
        )
    else:
        all_results["integration"] = {}

    # ─── Stage 4: Annotate ────────────────────────────────────────────────
    if 4 in stages_to_run:
        all_results["annotation"] = stage_annotate(
            texts_to_process,
            backend=args.backend if args.annotate else None,
            model=args.model if args.annotate else None,
            max_entries=args.max_entries,
            verbose=args.verbose,
            dry_run=args.dry_run
        )
    else:
        all_results["annotation"] = {}

    # ─── Stage 5: Statistics ──────────────────────────────────────────────
    if 5 in stages_to_run:
        all_results["statistics"] = stage_statistics(
            texts_to_process,
            verbose=args.verbose
        )
    else:
        all_results["statistics"] = {}

    # ─── Print Summary ────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    print_summary(
        extraction_results=all_results.get("extraction"),
        validation_results=all_results.get("validation"),
        integration_results=all_results.get("integration"),
        annotation_results=all_results.get("annotation"),
        statistics=all_results.get("statistics")
    )

    print_info(f"Total execution time: {elapsed:.1f} seconds")

    # Determine exit code
    extraction = all_results.get("extraction", {})
    if extraction and any(not r.get("success", False) for r in extraction.values()):
        print_error("Some extractions failed. See above for details.")
        sys.exit(1)

    print_success("Pipeline execution completed successfully!")
    sys.exit(0)


if __name__ == "__main__":
    main()
