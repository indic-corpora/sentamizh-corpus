#!/usr/bin/env python3
"""
Analyze the structure of Project Madurai HTML files for Tamil texts.

This script helps understand the patterns in different Tamil text types
(Akananuru, Silappatikaram, Thevaram, Divya Prabandham, Manimekalai, Thirumanthiram)
to build effective extraction pipelines.

Usage:
    python3 analyze_html.py data/raw/Akananuru_Ed1_Part1.html
    python3 analyze_html.py data/raw/Thevaram_*.html --compare
    python3 analyze_html.py data/raw/*.html --output analysis_report.json
"""

import json
import re
import sys
import glob
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Any
import argparse

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: beautifulsoup4 is required. Install with: pip install beautifulsoup4")
    sys.exit(1)


# Tamil Unicode range
TAMIL_UNICODE_RANGE = (0x0B80, 0x0BFF)


class HTMLAnalyzer:
    """Analyzes HTML structure of Project Madurai Tamil texts."""

    def __init__(self, filepath: str):
        """Initialize analyzer with HTML file."""
        self.filepath = filepath
        self.filename = Path(filepath).name
        self.soup = None
        self.text_content = ""
        self._load_html()

    def _load_html(self) -> None:
        """Load and parse HTML file."""
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                self.soup = BeautifulSoup(f.read(), 'html.parser')
                # Get all text content
                self.text_content = self.soup.get_text()
        except Exception as e:
            print(f"Error loading {self.filepath}: {e}", file=sys.stderr)
            self.soup = None

    def _get_tag_samples(self, tag_name: str, max_samples: int = 5) -> Tuple[int, List[str]]:
        """Get count and samples of a tag."""
        tags = self.soup.find_all(tag_name)
        count = len(tags)
        samples = []
        for tag in tags[:max_samples]:
            text = tag.get_text(strip=True)
            if text:
                # Truncate long text
                text = text[:100] + "..." if len(text) > 100 else text
                samples.append(text)
        return count, samples

    def _count_tamil_characters(self) -> Tuple[int, float]:
        """Count Tamil characters and calculate density."""
        tamil_count = sum(
            1 for char in self.text_content
            if TAMIL_UNICODE_RANGE[0] <= ord(char) <= TAMIL_UNICODE_RANGE[1]
        )
        total_chars = len(self.text_content)
        density = (tamil_count / total_chars * 100) if total_chars > 0 else 0
        return tamil_count, density

    def _find_verse_numbers(self) -> Tuple[int, List[str]]:
        """Find verse number patterns like (1), (2), (123)."""
        # Pattern: parenthesized numbers, possibly with Tamil markers
        pattern = r'\(\d+\)'
        matches = re.findall(pattern, self.text_content)
        samples = list(set(matches))[:10]  # Unique samples
        return len(matches), samples

    def _find_tinai_turai_markers(self) -> Dict[str, int]:
        """Search for திணை (tinai) and துறை (turai) markers."""
        markers = {}
        tinai_pattern = 'திணை'
        turai_pattern = 'துறை'

        markers['திணை (tinai)'] = self.text_content.count(tinai_pattern)
        markers['துறை (turai)'] = self.text_content.count(turai_pattern)

        return markers

    def _find_verse_end_markers(self) -> Tuple[int, List[str]]:
        """Find verse-end markers like (N) commonly used in Purananuru."""
        # Look for pattern: (N) or similar end markers
        pattern = r'\([Nn]\)'
        matches = re.findall(pattern, self.text_content)

        # Also look in <ul> blocks specifically
        ul_blocks = self.soup.find_all('ul')
        ul_with_markers = 0
        for ul in ul_blocks:
            if re.search(pattern, ul.get_text()):
                ul_with_markers += 1

        return len(matches), ul_with_markers

    def _find_numbered_sections(self) -> Dict[str, Any]:
        """Look for numbered sections and chapter divisions."""
        result = {
            'h1_with_numbers': 0,
            'h2_with_numbers': 0,
            'h3_with_numbers': 0,
            'total_numeric_headings': 0,
            'patterns': []
        }

        for h_level in [1, 2, 3]:
            headers = self.soup.find_all(f'h{h_level}')
            for header in headers:
                text = header.get_text(strip=True)
                # Match patterns like "1.", "1)", "1 -", etc.
                if re.match(r'^\d+[\.\)\-\s]', text):
                    result[f'h{h_level}_with_numbers'] += 1
                    result['total_numeric_headings'] += 1
                    if text not in result['patterns']:
                        result['patterns'].append(text[:80])

        return result

    def _find_padal_pathigam_patterns(self) -> Dict[str, int]:
        """Check for padal/pathigam/verse structural patterns in Bhakti texts."""
        patterns = {
            'padal': self.text_content.lower().count('padal'),
            'pathigam': self.text_content.lower().count('pathigam'),
            'padigam': self.text_content.count('பதிகம்'),  # Tamil
            'thiruppatikam': self.text_content.lower().count('thiruppatikam'),
        }
        return patterns

    def _find_poem_separators(self) -> Dict[str, int]:
        """Search for common poem separators (hr tags, headers between poems)."""
        separators = {
            'hr_tags': len(self.soup.find_all('hr')),
            'br_sequences': len(re.findall(r'<br\s*/?>\s*<br', str(self.soup))),
            'em_dashes': self.text_content.count('—'),
            'triple_asterisks': self.text_content.count('***'),
        }
        return separators

    def _analyze_heading_structure(self) -> Dict[str, Any]:
        """Analyze the hierarchy and distribution of headings."""
        result = {}
        for h_level in range(1, 7):
            count, samples = self._get_tag_samples(f'h{h_level}')
            result[f'h{h_level}'] = {
                'count': count,
                'samples': samples
            }
        return result

    def _analyze_text_structure(self) -> Dict[str, Any]:
        """Analyze text structural tags."""
        result = {}
        for tag in ['ul', 'ol', 'p', 'strong', 'em', 'br']:
            count, samples = self._get_tag_samples(tag)
            result[tag] = {
                'count': count,
                'samples': samples
            }
        return result

    def analyze(self) -> Dict[str, Any]:
        """Run complete analysis and return results."""
        if not self.soup:
            return {'error': f'Failed to load {self.filepath}'}

        tamil_char_count, tamil_density = self._count_tamil_characters()
        verse_numbers_count, verse_number_samples = self._find_verse_numbers()
        verse_end_matches, ul_with_markers = self._find_verse_end_markers()

        analysis = {
            'filename': self.filename,
            'filepath': str(self.filepath),
            'title': self.soup.title.string if self.soup.title else 'N/A',
            'headings': self._analyze_heading_structure(),
            'text_structure': self._analyze_text_structure(),
            'character_stats': {
                'total_characters': len(self.text_content),
                'tamil_characters': tamil_char_count,
                'tamil_density_percent': round(tamil_density, 2)
            },
            'verse_patterns': {
                'parenthesized_numbers': {
                    'count': verse_numbers_count,
                    'samples': verse_number_samples
                },
                'verse_end_markers_(N)': {
                    'count': verse_end_matches,
                    'ul_blocks_with_markers': ul_with_markers
                }
            },
            'tinai_turai_markers': self._find_tinai_turai_markers(),
            'poem_separators': self._find_poem_separators(),
            'numbered_sections': self._find_numbered_sections(),
            'bhakti_patterns': self._find_padal_pathigam_patterns(),
        }

        return analysis


class AnalysisComparator:
    """Compare structural patterns across multiple files."""

    def __init__(self, analyses: List[Dict[str, Any]]):
        """Initialize with list of analysis results."""
        self.analyses = analyses

    def compare(self) -> Dict[str, Any]:
        """Compare structural similarities and differences."""
        if len(self.analyses) < 2:
            return {'error': 'Need at least 2 analyses to compare'}

        comparison = {
            'file_count': len(self.analyses),
            'files': [a['filename'] for a in self.analyses],
            'structural_patterns': self._compare_structures(),
            'text_patterns': self._compare_text_patterns(),
            'verse_patterns': self._compare_verse_patterns(),
            'character_patterns': self._compare_characters(),
        }

        return comparison

    def _compare_structures(self) -> Dict[str, Any]:
        """Compare heading and section structures."""
        result = {
            'heading_distribution': defaultdict(list),
            'avg_heading_counts': {}
        }

        for h_level in range(1, 7):
            counts = [a['headings'][f'h{h_level}']['count'] for a in self.analyses]
            result['heading_distribution'][f'h{h_level}'] = counts
            result['avg_heading_counts'][f'h{h_level}'] = round(sum(counts) / len(counts), 1)

        return dict(result)

    def _compare_text_patterns(self) -> Dict[str, Any]:
        """Compare text structural element patterns."""
        result = {}
        for tag in ['ul', 'ol', 'p', 'strong', 'em', 'br']:
            counts = [a['text_structure'][tag]['count'] for a in self.analyses]
            result[tag] = {
                'counts': counts,
                'avg': round(sum(counts) / len(counts), 1),
                'min': min(counts),
                'max': max(counts)
            }
        return result

    def _compare_verse_patterns(self) -> Dict[str, Any]:
        """Compare verse pattern presence."""
        result = {
            'verse_numbers_presence': [],
            'verse_end_markers_presence': [],
            'tinai_presence': [],
            'turai_presence': []
        }

        for a in self.analyses:
            result['verse_numbers_presence'].append(a['verse_patterns']['parenthesized_numbers']['count'])
            result['verse_end_markers_presence'].append(a['verse_patterns']['verse_end_markers_(N)']['count'])
            result['tinai_presence'].append(a['tinai_turai_markers'].get('திணை (tinai)', 0))
            result['turai_presence'].append(a['tinai_turai_markers'].get('துறை (turai)', 0))

        return result

    def _compare_characters(self) -> Dict[str, Any]:
        """Compare character statistics."""
        result = {
            'total_chars': [],
            'tamil_chars': [],
            'tamil_density': []
        }

        for a in self.analyses:
            cs = a['character_stats']
            result['total_chars'].append(cs['total_characters'])
            result['tamil_chars'].append(cs['tamil_characters'])
            result['tamil_density'].append(cs['tamil_density_percent'])

        return result


def print_analysis(analysis: Dict[str, Any]) -> None:
    """Pretty-print analysis results to terminal."""
    if 'error' in analysis:
        print(f"\n[ERROR] {analysis['error']}")
        return

    print(f"\n{'='*80}")
    print(f"FILE: {analysis['filename']}")
    print(f"{'='*80}")

    print(f"\nTitle: {analysis['title']}")

    print("\n--- CHARACTER STATISTICS ---")
    cs = analysis['character_stats']
    print(f"  Total characters: {cs['total_characters']:,}")
    print(f"  Tamil characters: {cs['tamil_characters']:,}")
    print(f"  Tamil density: {cs['tamil_density_percent']:.2f}%")

    print("\n--- HEADING STRUCTURE ---")
    for h_level in range(1, 7):
        h_info = analysis['headings'][f'h{h_level}']
        print(f"  h{h_level}: {h_info['count']} tags")
        if h_info['samples']:
            for sample in h_info['samples'][:3]:
                print(f"      - {sample}")

    print("\n--- TEXT STRUCTURE ---")
    for tag in ['ul', 'ol', 'p', 'strong', 'em', 'br']:
        info = analysis['text_structure'][tag]
        print(f"  <{tag}>: {info['count']} tags")
        if info['samples']:
            for sample in info['samples'][:2]:
                print(f"      - {sample}")

    print("\n--- VERSE PATTERNS ---")
    vp = analysis['verse_patterns']
    print(f"  Parenthesized numbers (1), (2), etc: {vp['parenthesized_numbers']['count']}")
    if vp['parenthesized_numbers']['samples']:
        print(f"      Samples: {', '.join(vp['parenthesized_numbers']['samples'][:5])}")

    print(f"  Verse-end markers (N): {vp['verse_end_markers_(N)']['count']}")
    print(f"      <ul> blocks with (N): {vp['verse_end_markers_(N)']['ul_blocks_with_markers']}")

    print("\n--- TINAI / TURAI MARKERS ---")
    ttm = analysis['tinai_turai_markers']
    for marker, count in ttm.items():
        print(f"  {marker}: {count}")

    print("\n--- POEM SEPARATORS ---")
    ps = analysis['poem_separators']
    print(f"  <hr> tags: {ps['hr_tags']}")
    print(f"  <br> sequences: {ps['br_sequences']}")
    print(f"  Em dashes: {ps['em_dashes']}")
    print(f"  Triple asterisks: {ps['triple_asterisks']}")

    print("\n--- NUMBERED SECTIONS ---")
    ns = analysis['numbered_sections']
    print(f"  Numeric h1: {ns['h1_with_numbers']}")
    print(f"  Numeric h2: {ns['h2_with_numbers']}")
    print(f"  Numeric h3: {ns['h3_with_numbers']}")
    print(f"  Total numeric headings: {ns['total_numeric_headings']}")
    if ns['patterns']:
        print(f"  Patterns (first 5):")
        for pattern in ns['patterns'][:5]:
            print(f"      - {pattern}")

    print("\n--- BHAKTI TEXT PATTERNS ---")
    bp = analysis['bhakti_patterns']
    for pattern, count in bp.items():
        if count > 0:
            print(f"  {pattern}: {count}")


def print_comparison(comparison: Dict[str, Any]) -> None:
    """Pretty-print comparison results."""
    if 'error' in comparison:
        print(f"\n[ERROR] {comparison['error']}")
        return

    print(f"\n{'='*80}")
    print(f"COMPARISON: {comparison['file_count']} files")
    print(f"{'='*80}")

    print("\nFiles analyzed:")
    for i, filename in enumerate(comparison['files'], 1):
        print(f"  {i}. {filename}")

    print("\n--- HEADING DISTRIBUTION ---")
    sp = comparison['structural_patterns']
    for h_level, counts in sorted(sp['heading_distribution'].items()):
        avg = sp['avg_heading_counts'][h_level]
        print(f"  {h_level}: {counts} (avg: {avg})")

    print("\n--- TEXT STRUCTURE COMPARISON ---")
    tp = comparison['text_patterns']
    print(f"  {'Tag':<10} {'Counts':<30} {'Min':<8} {'Max':<8} {'Avg':<8}")
    print(f"  {'-'*70}")
    for tag, stats in sorted(tp.items()):
        print(f"  {tag:<10} {str(stats['counts']):<30} {stats['min']:<8} {stats['max']:<8} {stats['avg']:<8}")

    print("\n--- VERSE PATTERNS COMPARISON ---")
    vp = comparison['verse_patterns']
    print(f"  Parenthesized numbers: {vp['verse_numbers_presence']}")
    print(f"  Verse-end markers (N): {vp['verse_end_markers_presence']}")
    print(f"  திணை markers: {vp['tinai_presence']}")
    print(f"  துறை markers: {vp['turai_presence']}")

    print("\n--- CHARACTER STATISTICS COMPARISON ---")
    cp = comparison['character_patterns']
    print(f"  Total chars: {cp['total_chars']}")
    print(f"  Tamil chars: {cp['tamil_chars']}")
    print(f"  Tamil density %: {[round(x, 1) for x in cp['tamil_density']]}")


def expand_file_patterns(patterns: List[str]) -> List[str]:
    """Expand glob patterns to actual file paths."""
    expanded = []
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            expanded.extend(sorted(matches))
        else:
            # If no glob matches, treat as literal path
            expanded.append(pattern)
    return expanded


def main():
    parser = argparse.ArgumentParser(
        description='Analyze structure of Project Madurai HTML files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python3 analyze_html.py data/raw/Akananuru_Ed1_Part1.html
  python3 analyze_html.py data/raw/Thevaram_*.html --compare
  python3 analyze_html.py data/raw/*.html --output analysis_report.json
        '''
    )
    parser.add_argument(
        'files',
        nargs='+',
        help='HTML file paths (supports glob patterns)'
    )
    parser.add_argument(
        '--compare',
        action='store_true',
        help='Compare structural patterns across files'
    )
    parser.add_argument(
        '--output',
        help='Output JSON analysis file'
    )

    args = parser.parse_args()

    # Expand file patterns
    filepaths = expand_file_patterns(args.files)

    if not filepaths:
        print("Error: No files found matching the provided patterns")
        sys.exit(1)

    print(f"Analyzing {len(filepaths)} file(s)...")

    # Analyze each file
    analyses = []
    for filepath in filepaths:
        analyzer = HTMLAnalyzer(filepath)
        analysis = analyzer.analyze()
        analyses.append(analysis)
        print_analysis(analysis)

    # Compare if requested
    if args.compare and len(analyses) > 1:
        comparator = AnalysisComparator(analyses)
        comparison = comparator.compare()
        print_comparison(comparison)

        # Add comparison to output
        if args.output:
            analyses.append({'comparison': comparison})

    # Save JSON output if requested
    if args.output:
        output_data = {
            'analyses': analyses,
            'file_count': len(filepaths),
        }
        if args.compare and len(analyses) > 1:
            output_data['comparison'] = analyses[-1].get('comparison', {})

        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            print(f"\nJSON analysis saved to: {args.output}")
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == '__main__':
    main()
