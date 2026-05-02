#!/usr/bin/env python3
"""
Sentamizh Corpus — PaaPeyarchi HuggingFace Dataset Downloader

Downloads the PaaPeyarchi Tamil Poetry dataset from HuggingFace,
which contains ~7,705 poems including Sangam literature entries
(Kuruntokai, Natrinai, Purananuru, Akananuru, and more).

This dataset can supplement our primary sources with:
  - Modern Tamil (simplified) text
  - Additional metadata fields
  - Cross-referencing for verse matching

Usage:
    python3 download_paapeyarchi.py
    python3 download_paapeyarchi.py --output-dir ../data/external
    python3 download_paapeyarchi.py --filter kuruntokai   # Only Kuruntokai entries
    python3 download_paapeyarchi.py --filter natrinai

Requirements:
    pip install datasets   (HuggingFace datasets library)
"""

import os
import sys
import json
import argparse
from pathlib import Path


DATASET_NAME = "akdiwahar/PaaPeyarchi"


def download_and_save(output_dir, text_filter=None):
    """Download PaaPeyarchi dataset and save as JSON."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("⚠  The 'datasets' library is required.")
        print("   Install it with: pip install datasets")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    print(f"Downloading {DATASET_NAME} from HuggingFace...")
    ds = load_dataset(DATASET_NAME)

    # Explore available splits
    print(f"Available splits: {list(ds.keys())}")

    for split_name, split_data in ds.items():
        print(f"\nSplit: {split_name}")
        print(f"  Rows: {len(split_data)}")
        print(f"  Columns: {split_data.column_names}")

        # Show a sample
        if len(split_data) > 0:
            print(f"  Sample entry keys: {list(split_data[0].keys())}")

        # Convert to list of dicts
        records = [dict(row) for row in split_data]

        # If filtering, try to match by text name in relevant columns
        if text_filter:
            filter_lower = text_filter.lower()
            filtered = []
            for record in records:
                # Check various possible column names for the source text
                record_str = json.dumps(record, ensure_ascii=False).lower()
                if filter_lower in record_str:
                    filtered.append(record)
            records = filtered
            print(f"  After filtering for '{text_filter}': {len(records)} entries")

        # Save
        output_file = os.path.join(output_dir, f"PaaPeyarchi_{split_name}.json")
        if text_filter:
            output_file = os.path.join(
                output_dir,
                f"PaaPeyarchi_{split_name}_{text_filter}.json"
            )

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        print(f"  Saved to: {output_file}")

    # Print column analysis
    print(f"\n{'='*60}")
    print("  Column Analysis (for integration planning)")
    print(f"{'='*60}")
    for split_name, split_data in ds.items():
        if len(split_data) > 0:
            sample = split_data[0]
            for key, value in sample.items():
                val_preview = str(value)[:80] if value else "None"
                print(f"  {key}: {val_preview}")
        break  # Only show first split


def main():
    parser = argparse.ArgumentParser(
        description="Download PaaPeyarchi Tamil Poetry dataset from HuggingFace"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)),
                             "data", "external"),
        help="Output directory (default: ../data/external)"
    )
    parser.add_argument(
        "--filter", "-f",
        help="Filter entries by text name (e.g., kuruntokai, natrinai)"
    )

    args = parser.parse_args()

    print("Sentamizh Corpus — PaaPeyarchi Dataset Downloader")
    print(f"Output dir: {os.path.abspath(args.output_dir)}")
    print(f"Dataset: {DATASET_NAME}")
    print()

    download_and_save(args.output_dir, text_filter=args.filter)


if __name__ == "__main__":
    main()
