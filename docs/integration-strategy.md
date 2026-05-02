# Dataset Integration Strategy — Leveraging Existing HuggingFace Datasets

> **Status: [Plan]** — As of 2026-04-30, none of the integrations described here have been executed against the canonical corpus. The `modern_tamil` field is currently 0% populated across all 10,393 entries. This document describes the *intended* approach; actual integration is on the roadmap.

## Overview

Four existing HuggingFace datasets cover content overlapping with parts of the Sentamizh schema scope. Rather than extracting equivalent material from scratch, the plan is to cross-reference these datasets to draft specific fields where their content aligns, then layer the unique Sentamizh annotations on top. Each of the upstream datasets was created for its own purposes; the integration described here builds on top of them, not in opposition to them.

## Available Datasets

| Dataset | Rows | Relevant Fields | Overlapping Texts | License |
|---------|------|----------------|-------------------|---------|
| akdiwahar/PaaPeyarchi | 7,705 | Classical Tamil → Modern Tamil | Kuruntokai, Natrinai, Purananuru, Naladiyar, Tirukkural, Thirumanthiram, others | CC-BY-NC-2.0 |
| kodebot/Purananuru_Tamil_with_meaning | 398 | Classical Tamil → Modern Tamil (instruction format) | Purananuru | Unknown |
| Kameshr/tamil-sangam-text-excerpt | 1,053 | Tamil, Transliteration, English, Themes, Imagery, Literary Devices, Symbolism | Sangam excerpts (unspecified sources) | MIT |
| pranesh-19/Sangam_tamil_to_English | 244 | Classical Tamil → English, book_name | 5 Sangam texts | Apache-2.0 |

## Integration Plan by Schema Field

### Fields we can pre-populate:

**`modern_tamil`** — Primary source: PaaPeyarchi (7,705 pairs across multiple texts). Secondary: kodebot (398 Purananuru-specific). Strategy: Match verses by fuzzy text alignment between our extracted `classical_tamil` and PaaPeyarchi's source column. PaaPeyarchi is the highest-value dataset for us — it covers several of our target texts with clean Classical→Modern Tamil pairs.

**`english`** — Primary source: Kameshr (1,053 entries with English translations). Secondary: pranesh-19 (244 entries). Strategy: Match by verse text alignment. Coverage is much smaller than PaaPeyarchi, so English translations will be sparser and will need more LLM/human annotation work.

**`themes`** — Source: Kameshr (has a Themes column). Strategy: Cross-reference where verse matches exist, but treat as draft annotations requiring human review. Kameshr's theme vocabulary may not align with ours.

**`visual_imagery`** — Source: Kameshr (has an Imagery column). Strategy: Same as themes — use as draft input for our `visual_imagery` field, but normalize to our description style.

### Fields we CANNOT pre-populate from existing data:

All Tamil-native literary fields (turai, karu, uri, ullurai, speaker_role, metre, pann) — no existing dataset captures these.

All cross-cultural bridge fields (nayika_bheda, emotional_valence) — no existing dataset has these.

Rasa, thinai, dhvani, storytelling seeds — unique to our schema.

## Technical Integration Pipeline

### Step 1: Download & normalize existing datasets
```
pip install datasets pandas
```
- Load each dataset via HuggingFace `datasets` library
- Normalize column names and text encoding
- Export to intermediate CSV/JSON for matching

### Step 2: Verse matching
- For PaaPeyarchi → our corpus: fuzzy match on classical Tamil text
  - Use difflib.SequenceMatcher or rapidfuzz for Tamil string similarity
  - Threshold: 85%+ similarity = confident match
  - Manual review queue for 70-85% matches
- For Kameshr/pranesh-19 → our corpus: same approach on Tamil text column

### Step 3: Field merging
- For each matched verse, copy relevant fields into our schema structure
- Tag with `annotation_confidence: "low"` and `annotator: "auto-merged:PaaPeyarchi"` (or respective dataset name)
- These become draft annotations in a human review queue

### Step 4: Human review
- Review merged translations for accuracy
- Upgrade `annotation_confidence` after review
- Add unique Sentamizh annotations (rasa, thinai, karu, uri, etc.)

## License Considerations

The Sentamizh Corpus itself is Apache 2.0. License compatibility of upstream sources determines how their content may flow into the corpus:

- **PaaPeyarchi (CC-BY-NC-2.0)**: Non-commercial. Attribution to akdiwahar is required. CC-BY-NC content cannot be merged into an Apache-2.0 corpus while preserving the corpus's commercial-use grant; if PaaPeyarchi-derived `modern_tamil` flows into the corpus, the affected entries would need to be either independently re-translated, segregated into a non-commercial subset, or referenced via fuzzy-match links rather than copied verbatim. This is a real constraint on the integration design and is flagged on the roadmap.
- **Kameshr (MIT)**: Permissive. Compatible with Apache-2.0 with attribution.
- **pranesh-19 (Apache-2.0)**: Permissive. Compatible with attribution.
- **kodebot**: License not specified. Treat as reference only; don't copy content into the corpus without explicit clarification from the maintainer.

## Priority Order

1. **PaaPeyarchi** — highest value (7,705 Modern Tamil translations across many texts)
2. **Kameshr** — second priority (English translations + themes + imagery for 1,053 entries)
3. **pranesh-19** — supplementary (244 English translations)
4. **kodebot** — reference only (license unclear, quality issues in augmented version)

## What Integration Could Buy Us (if executed)

Without any integration, every field in the corpus is populated from scratch via extraction, LLM-assistance, or expert annotation. With the plan above executed, the upstream datasets could supply approximately ~7,700 candidate `modern_tamil` drafts, ~1,200 candidate `english` drafts, and ~1,000 candidate `themes`/`imagery` drafts as starting points for human review — license-permitting per the table above. This would let expert annotation focus on the interpretive layers (rasa, dhvani, ullurai, karu/uri, nayika_bheda, etc.) that the upstream datasets do not cover.

These numbers are upper bounds, not committed yields. Actual coverage would depend on fuzzy-match hit rates against Sentamizh's `classical_tamil` field, and on license-segregation decisions per upstream source.
