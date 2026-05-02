#!/usr/bin/env python3
"""
Integration script for PaaPeyarchi dataset with Sentamizh Corpus.

Matches PaaPeyarchi entries to corpus entries to fill in modern_tamil field.
Uses multiple matching strategies: exact, first-line, n-gram similarity, and token overlap.
"""

import json
import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict


class PaaPeyarchiIntegrator:
    """Integrator for PaaPeyarchi dataset with Sentamizh Corpus."""

    def __init__(
        self,
        paapeyarchi_path: str,
        threshold: float = 0.8,
        output_suffix: str = "_enriched",
    ):
        """Initialize the integrator.

        Args:
            paapeyarchi_path: Path to PaaPeyarchi_train.json
            threshold: Match confidence threshold (0.0-1.0)
            output_suffix: Suffix for enriched output files
        """
        self.paapeyarchi_path = paapeyarchi_path
        self.threshold = threshold
        self.output_suffix = output_suffix
        self.paapeyarchi_data = []
        self.paapeyarchi_index = {}
        self.matches_found = []
        self.review_needed = []
        self.unmatched = []

    def load_paapeyarchi(self) -> None:
        """Load PaaPeyarchi dataset."""
        try:
            with open(self.paapeyarchi_path, "r", encoding="utf-8") as f:
                self.paapeyarchi_data = json.load(f)
            print(f"Loaded {len(self.paapeyarchi_data)} PaaPeyarchi entries")
        except Exception as e:
            print(f"Error loading PaaPeyarchi: {e}")
            sys.exit(1)

    def build_index(self) -> None:
        """Build search index for PaaPeyarchi entries."""
        for idx, entry in enumerate(self.paapeyarchi_data):
            classic_text = entry.get("classic", "").strip()
            description = entry.get("Description", "").strip()

            # Store both normalized and original
            self.paapeyarchi_index[idx] = {
                "classic": classic_text,
                "classic_normalized": self._normalize_text(classic_text),
                "classic_first_line": self._get_first_line(classic_text),
                "classic_ngrams": self._get_ngrams(classic_text),
                "classic_tokens": self._tokenize(classic_text),
                "description": description,
                "original_idx": idx,
            }

    def _normalize_text(self, text: str) -> str:
        """Normalize text by removing extra whitespace."""
        # Replace multiple spaces and line breaks with single space
        text = text.replace("\n", " ").replace("\\n", " ")
        text = " ".join(text.split())
        return text.lower()

    def _get_first_line(self, text: str) -> str:
        """Extract first line of text."""
        lines = text.split("\n")
        if lines:
            return self._normalize_text(lines[0])
        return self._normalize_text(text)

    def _get_ngrams(self, text: str, n: int = 3) -> Set[str]:
        """Extract character n-grams from text."""
        normalized = self._normalize_text(text)
        ngrams = set()
        for i in range(len(normalized) - n + 1):
            ngrams.add(normalized[i : i + n])
        return ngrams

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        normalized = self._normalize_text(text)
        # Simple space-based tokenization
        return [token for token in normalized.split() if token]

    def _jaccard_similarity(self, set1: Set, set2: Set) -> float:
        """Calculate Jaccard similarity between two sets."""
        if not set1 and not set2:
            return 1.0
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def _token_overlap(self, tokens1: List[str], tokens2: List[str]) -> float:
        """Calculate token overlap ratio."""
        if not tokens1 and not tokens2:
            return 1.0
        if not tokens1 or not tokens2:
            return 0.0
        set1 = set(tokens1)
        set2 = set(tokens2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def match_entry(self, corpus_entry: Dict) -> Tuple[Optional[int], float, str]:
        """Find best PaaPeyarchi match for a corpus entry.

        Returns:
            Tuple of (paapeyarchi_index, confidence_score, match_type)
        """
        classical_tamil = corpus_entry.get("classical_tamil", "").strip()
        if not classical_tamil:
            return None, 0.0, "no_text"

        # Normalize corpus text
        corpus_normalized = self._normalize_text(classical_tamil)
        corpus_first_line = self._get_first_line(classical_tamil)
        corpus_ngrams = self._get_ngrams(classical_tamil)
        corpus_tokens = self._tokenize(classical_tamil)

        best_idx = None
        best_score = 0.0
        best_match_type = "none"

        # Quick pre-filtering: only compare texts of similar length
        corpus_len = len(corpus_normalized)
        corpus_token_count = len(corpus_tokens)

        for idx, paa_entry in self.paapeyarchi_index.items():
            # Quick filter by length (allow 30% variance)
            paa_len = len(paa_entry["classic_normalized"])
            if abs(corpus_len - paa_len) > max(corpus_len, paa_len) * 0.3:
                continue

            # Strategy 1: Exact match (normalized)
            if corpus_normalized == paa_entry["classic_normalized"]:
                return idx, 1.0, "exact"

            # Strategy 2: First line match (strong indicator)
            first_line_score = 0.0
            if corpus_first_line and paa_entry["classic_first_line"]:
                if corpus_first_line == paa_entry["classic_first_line"]:
                    first_line_score = 0.95
                else:
                    # Partial first line match
                    first_line_score = self._token_overlap(
                        corpus_first_line.split(), paa_entry["classic_first_line"].split()
                    )

            # Only continue with other strategies if first line is promising
            if first_line_score < 0.3:
                # Strategy 3: N-gram similarity (trigrams) - quick estimate
                ngram_score = self._jaccard_similarity(
                    corpus_ngrams, paa_entry["classic_ngrams"]
                )

                # Strategy 4: Token overlap
                token_score = self._token_overlap(
                    corpus_tokens, paa_entry["classic_tokens"]
                )

                # Weighted combination
                # First line is most distinctive (0.4), then tokens (0.35), then ngrams (0.25)
                combined_score = (
                    first_line_score * 0.4 + token_score * 0.35 + ngram_score * 0.25
                )
            else:
                combined_score = first_line_score

            # Update best match
            if combined_score > best_score:
                best_score = combined_score
                best_idx = idx

                if first_line_score > 0.9:
                    best_match_type = "first_line"
                elif first_line_score > 0.5:
                    best_match_type = "partial_first_line"
                else:
                    best_match_type = "ngram_token"

        return best_idx, best_score, best_match_type

    def process_corpus_file(self, corpus_path: str, dry_run: bool = False) -> None:
        """Process a single corpus JSON file.

        Args:
            corpus_path: Path to corpus JSON file
            dry_run: If True, only report matches without modifying files
        """
        try:
            with open(corpus_path, "r", encoding="utf-8") as f:
                corpus_data = json.load(f)
        except Exception as e:
            print(f"Error loading corpus file {corpus_path}: {e}")
            return

        if not isinstance(corpus_data, list):
            print(f"Warning: {corpus_path} is not a list")
            return

        matched_count = 0
        review_count = 0
        unmatched_count = 0

        print(f"\nProcessing {Path(corpus_path).name}...")

        for entry in corpus_data:
            paapeyarchi_idx, confidence, match_type = self.match_entry(entry)

            verse_id = entry.get("verse_id", "unknown")

            if paapeyarchi_idx is not None:
                if confidence >= 0.8:
                    # Auto-match
                    matched_count += 1
                    paa_entry = self.paapeyarchi_data[paapeyarchi_idx]
                    description = paa_entry.get("Description", "")

                    if not dry_run:
                        entry["modern_tamil"] = description

                    self.matches_found.append(
                        {
                            "corpus_file": Path(corpus_path).name,
                            "verse_id": verse_id,
                            "paapeyarchi_idx": paapeyarchi_idx,
                            "confidence": confidence,
                            "match_type": match_type,
                            "first_line": self._get_first_line(
                                entry.get("classical_tamil", "")
                            )[:50],
                        }
                    )

                elif confidence >= 0.5:
                    # Review needed
                    review_count += 1
                    paa_entry = self.paapeyarchi_data[paapeyarchi_idx]
                    description = paa_entry.get("Description", "")

                    self.review_needed.append(
                        {
                            "corpus_file": Path(corpus_path).name,
                            "verse_id": verse_id,
                            "paapeyarchi_idx": paapeyarchi_idx,
                            "confidence": confidence,
                            "match_type": match_type,
                            "first_line": self._get_first_line(
                                entry.get("classical_tamil", "")
                            )[:50],
                        }
                    )

                    if not dry_run:
                        # Don't auto-fill, but flag for review
                        pass
                else:
                    unmatched_count += 1
                    self.unmatched.append(
                        {
                            "corpus_file": Path(corpus_path).name,
                            "verse_id": verse_id,
                            "reason": "confidence_below_threshold",
                            "confidence": confidence,
                        }
                    )
            else:
                unmatched_count += 1
                self.unmatched.append(
                    {
                        "corpus_file": Path(corpus_path).name,
                        "verse_id": verse_id,
                        "reason": "no_match_found",
                        "confidence": 0.0,
                    }
                )

        print(f"  Matched: {matched_count}")
        print(f"  Review needed: {review_count}")
        print(f"  Unmatched: {unmatched_count}")

        # Write updated corpus if not dry-run
        if not dry_run:
            output_path = str(corpus_path).replace(".json", f"{self.output_suffix}.json")
            try:
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(corpus_data, f, ensure_ascii=False, indent=2)
                print(f"  Wrote enriched corpus to {output_path}")
            except Exception as e:
                print(f"Error writing enriched corpus: {e}")

    def generate_report(
        self, total_entries: int, report_path: Optional[str] = None
    ) -> None:
        """Generate and optionally write match report.

        Args:
            total_entries: Total number of corpus entries processed
            report_path: Optional path to write CSV report
        """
        print("\n" + "=" * 60)
        print("MATCH REPORT")
        print("=" * 60)
        print(f"Total entries: {total_entries}")
        print(f"Matched (confidence >= 0.8): {len(self.matches_found)}")
        print(f"Review needed (0.5 <= confidence < 0.8): {len(self.review_needed)}")
        print(f"Unmatched: {len(self.unmatched)}")
        if total_entries > 0:
            print(
                f"Match rate: {len(self.matches_found) / total_entries * 100:.1f}% (auto-filled)"
            )
            print(
                f"Review rate: {len(self.review_needed) / total_entries * 100:.1f}% (flagged for review)"
            )
        else:
            print("Match rate: N/A (no entries processed)")
            print("Review rate: N/A (no entries processed)")
        print("=" * 60)

        if report_path:
            self._write_csv_report(report_path)

    def _write_csv_report(self, report_path: str) -> None:
        """Write detailed match report as CSV."""
        try:
            # Combine all matches for CSV
            all_matches = self.matches_found + self.review_needed

            if not all_matches:
                print(f"No matches to write to {report_path}")
                return

            with open(report_path, "w", newline="", encoding="utf-8") as f:
                fieldnames = [
                    "corpus_file",
                    "verse_id",
                    "paapeyarchi_idx",
                    "confidence",
                    "match_type",
                    "first_line_preview",
                    "status",
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for match in self.matches_found:
                    row = {
                        "corpus_file": match["corpus_file"],
                        "verse_id": match["verse_id"],
                        "paapeyarchi_idx": match["paapeyarchi_idx"],
                        "confidence": f"{match['confidence']:.3f}",
                        "match_type": match["match_type"],
                        "first_line_preview": match["first_line"],
                        "status": "AUTO_FILLED",
                    }
                    writer.writerow(row)

                for match in self.review_needed:
                    row = {
                        "corpus_file": match["corpus_file"],
                        "verse_id": match["verse_id"],
                        "paapeyarchi_idx": match["paapeyarchi_idx"],
                        "confidence": f"{match['confidence']:.3f}",
                        "match_type": match["match_type"],
                        "first_line_preview": match["first_line"],
                        "status": "REVIEW_NEEDED",
                    }
                    writer.writerow(row)

            print(f"\nCSV report written to {report_path}")
        except Exception as e:
            print(f"Error writing CSV report: {e}")

    def run(
        self,
        corpus_paths: List[str],
        dry_run: bool = False,
        report_path: Optional[str] = None,
    ) -> None:
        """Run the integration process.

        Args:
            corpus_paths: List of corpus JSON file paths
            dry_run: If True, only report matches without modifying files
            report_path: Optional path to write CSV report
        """
        # Load PaaPeyarchi data
        self.load_paapeyarchi()

        # Build index
        self.build_index()

        # Process each corpus file
        total_entries = 0
        for corpus_path in corpus_paths:
            path = Path(corpus_path)
            if path.is_file():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        corpus_data = json.load(f)
                    total_entries += len(corpus_data) if isinstance(corpus_data, list) else 0
                    self.process_corpus_file(corpus_path, dry_run=dry_run)
                except Exception as e:
                    print(f"Error processing {corpus_path}: {e}")
            else:
                print(f"File not found: {corpus_path}")

        # Generate report
        self.generate_report(total_entries, report_path)

        # Print summary
        if dry_run:
            print("\nDRY RUN: No files were modified")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Integrate PaaPeyarchi dataset with Sentamizh Corpus",
        epilog="""
Examples:
  # Process single file with auto-match and report
  python3 integrate_paapeyarchi.py data/processed/Kuruntokai_Vaidehi_All.json \\
    --report matches_report.csv

  # Process multiple files with custom threshold
  python3 integrate_paapeyarchi.py data/processed/*.json --threshold 0.7

  # Dry-run to see matches without modifying files
  python3 integrate_paapeyarchi.py data/processed/Kuruntokai_Vaidehi_All.json --dry-run

  # Use custom PaaPeyarchi dataset location
  python3 integrate_paapeyarchi.py data/processed/Kuruntokai_Vaidehi_All.json \\
    --paapeyarchi /path/to/custom_dataset.json

Matching strategies (in order of strength):
  1. Exact match: Normalized whitespace comparison (confidence: 1.0)
  2. First-line match: Comparing first line of texts (confidence: 0.9-0.95)
  3. Partial first-line: Partial match on first line (confidence: 0.5-0.9)
  4. Token/N-gram: Word and character trigram overlap (confidence: 0.0-0.5)

Confidence thresholds:
  >= 0.8: Auto-fill modern_tamil field
  0.5-0.8: Flag as review_needed in report
  < 0.5: Unmatched
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "corpus_paths",
        nargs="+",
        help="Path(s) to corpus JSON file(s) to enrich",
    )
    parser.add_argument(
        "--paapeyarchi",
        default="data/external/PaaPeyarchi_train.json",
        help="Path to PaaPeyarchi_train.json (default: data/external/PaaPeyarchi_train.json)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.8,
        help="Match confidence threshold (0.0-1.0) for auto-filling (default: 0.8)",
    )
    parser.add_argument(
        "--output-suffix",
        default="_enriched",
        help="Suffix for enriched output files (default: _enriched)",
    )
    parser.add_argument(
        "--report",
        help="Path to write CSV report of matches (optional)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only show matches without modifying files",
    )

    args = parser.parse_args()

    # Create integrator
    integrator = PaaPeyarchiIntegrator(
        paapeyarchi_path=args.paapeyarchi,
        threshold=args.threshold,
        output_suffix=args.output_suffix,
    )

    # Run integration
    integrator.run(
        corpus_paths=args.corpus_paths,
        dry_run=args.dry_run,
        report_path=args.report,
    )


if __name__ == "__main__":
    main()
