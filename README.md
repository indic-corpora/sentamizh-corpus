---
license: apache-2.0
language:
  - ta
  - en
pretty_name: Sentamizh Corpus
size_categories:
  - 10K<n<100K
task_categories:
  - text-generation
  - translation
  - text-classification
tags:
  - tamil
  - classical-tamil
  - sangam
  - bhakti
  - tolkappiyam
  - dhvani
  - rasa
  - literary
  - multilingual
  - cultural-heritage
---

# Sentamizh Corpus

A multi-framework annotated corpus of Classical Tamil literature — 10,393 verses across 9 source texts, with a 32-field schema spanning Tolkappiyam-era poetics, Bhakti devotional traditions, and a cross-cultural bridge layer for readers without classical-Tamil background. The schema is designed to support trilingual representation (Classical Tamil, Modern Tamil, English); current per-language coverage and per-field annotation status are detailed in the Dataset Structure and Bias/Risks/Limitations sections below.

## Dataset Details

### Dataset Description

The Sentamizh Corpus is an open-source dataset of Classical Tamil literature designed to make a 2,000-year literary tradition computationally accessible. Each entry pairs a Classical Tamil verse with structured annotations drawn from three interpretive frameworks: Tolkappiyam-era Tamil poetics (Thinai, Akam/Puram, Karu/Uri, Ullurai), Natya Shastra rasa theory (Navarasa), and Anandavardhana's *dhvani* (suggested meaning). A cross-cultural bridge layer maps each verse to widely legible emotional structures — Plutchik's wheel and Nayika Bheda — so the corpus is useful to readers without Tamil-language expertise.

The corpus complements existing digitized resources for Classical Tamil — most prominently Project Madurai, the Tamil Virtual Academy, and Vaidehi Herbert's Sangam translations — by adding a structured, queryable, machine-readable layer on top of source material those projects have already preserved.

- **Curated by:** Revathi Prasad (project lead, schema design, engineering) with classical-Tamil expert annotation by a family member.
- **Languages:** Classical Tamil (`ta`), Modern Tamil (`ta`), English (`en`).
- **License:** Apache 2.0.
- **Repository:** <https://github.com/indic-corpora/sentamizh-corpus>
- **Hugging Face organization:** <https://huggingface.co/indic-corpora>
- **Documentation:** [Project Brief](docs/project-brief.md) · [Roadmap](ROADMAP.md) · [Architectural decisions](docs/decisions/) · [Changelog](CHANGELOG.md).

### Dataset Sources

The corpus stands on existing digitization work. Each source text in the corpus traces back to one of:

- **[Project Madurai](https://projectmadurai.org/)** — the volunteer-driven digital library that produced the HTML editions of Sangam, Bhakti, Epic, and Spiritual texts used here. The corpus's `classical_tamil` field for these texts is derived from Project Madurai's editions; provenance is recorded per-entry in the `source_url` field.
- **[Vaidehi Herbert's Sangam Translations](https://sangamtranslationsbyvaidehi.com/)** — the source for Kuruntokai and Natrinai, with Tamil-English alignment that informs both the `classical_tamil` and `english` fields for those texts.
- **[Tamil Virtual Academy](https://www.tamilvu.org/)** — referenced as a secondary scholarly source where Project Madurai's digitization has known issues.
- **[PaaPeyarchi (HuggingFace)](https://huggingface.co/datasets/akdiwahar/PaaPeyarchi)** by akdiwahar — a separate dataset of Classical-to-Modern Tamil pairs covering some of the same texts. Referenced as a candidate for `modern_tamil` field population; license-compatibility constraints are detailed in [docs/integration-strategy.md](docs/integration-strategy.md).

## Uses

### Direct Use

The corpus is designed with the following uses in mind. Use is supported but has not yet been independently validated by users in any of these areas; if you use it for one of them, contributions back are welcome.

- Computational study of Classical Tamil poetics, prosody, and literary devices.
- AI training data for low-resource Indic NLP. The schema is structured to support Classical-to-Modern Tamil paraphrase, Classical-to-English translation, and trilingual alignment as the multi-language layers fill in. Today the Classical Tamil layer is the most usable; English coverage is limited to Kuruntokai and Natrinai (~8% of entries), and Modern Tamil coverage is on the Phase 2 roadmap.
- Reference material for creators working with classical Indian literary traditions (writers, dramatists, designers) who want structured access to emotional and thematic annotations rather than just digitized text.
- Cross-cultural literary scholarship that requires legible mappings between classical Indian literary categories and widely-used emotional/dramatic frameworks.

### Out-of-Scope Use

- Generating or attributing biographical claims about specific historical persons. Many Sangam poets are anonymous or pseudonymous; the corpus does not assert biographical fact.
- Religious or doctrinal authority. Bhakti and spiritual texts in this corpus are presented as literary artifacts, not as sources for theological claims.
- Automated translation in the Modern-to-Classical direction. The corpus is one-directional source material; reverse-direction translation is not validated.
- Definitive interpretation. The interpretive layer (rasa, dhvani, themes) reflects the annotator's judgment within Tamil literary tradition; it does not foreclose other valid readings of the same verse.

## Dataset Structure

### Data Instances

A representative entry (Kuruntokai 3) — most fields populated by extraction or by the Vaidehi alignment; some interpretive fields are still null pending Phase 1 manual annotation:

```json
{
  "verse_id": "KURU-003",
  "source_text": "Kuruntokai",
  "layer": "Sangam",
  "period": "3rd century BCE – 3rd century CE",
  "verse_number": "3",
  "classical_tamil": "நிலத்தினும் பெரிதே, வானினும் உயர்ந்தன்று,\nநீரினும் ஆரளவின்றே, சாரல்\nகருங்கோல் குறிஞ்சிப் பூக் கொண்டு\nபெருந்தேன் இழைக்கும் நாடனொடு நட்பே.",
  "english": "Larger than the earth,\nhigher than the sky,\nand harder to fathom than the ocean,\nis my love for the man from\nthe mountain slopes, where bees\nmake rich honey from the flowers\nof kurinji plants with dark stems.",
  "thinai": "Kurinji",
  "akam_or_puram": "Akam",
  "speaker_role": "talaivi",
  "difficulty": "archaic",
  "source_url": "https://sangamtranslationsbyvaidehi.com/ettuthokai-kurunthokai-1-200/",
  "modern_tamil": null,
  "rasa_primary": null,
  "themes": null,
  "ullurai": null,
  "dhvani_layer": null,
  "annotator": null,
  "annotation_confidence": null
}
```

### Data Fields

The schema has 32 fields organized in four layers. Full field-level definitions and types live in [`schemas/sentamizh_schema.json`](schemas/sentamizh_schema.json); the design rationale is in [`docs/decisions/0001-32-field-schema.md`](docs/decisions/0001-32-field-schema.md).

**Core layer (10 fields)** — identification + raw text:
`verse_id`, `source_text`, `layer`, `period`, `verse_number`, `classical_tamil`, `modern_tamil`, `english`, `source_url`, `difficulty`.

**Tamil-native layer (10 fields)** — Tolkappiyam-aligned categories:
`thinai`, `turai`, `akam_or_puram`, `karu`, `uri`, `ullurai`, `speaker_role`, `metre`, `pann`, `dhvani_layer`.

**Interpretive layer (7 fields)** — themes, philosophy, storytelling seeds:
`rasa_primary`, `rasa_secondary`, `themes`, `philosophical_concept`, `cultural_context`, `storytelling_seed_narrative`, `storytelling_seed_emotional`.

**Cross-cultural bridge layer (3 fields)** — universally legible mappings:
`nayika_bheda` (8 classical heroine states from Natya Shastra), `visual_imagery` (concrete visual elements in widely-understood terms), `emotional_valence` (Plutchik-mapped: primary emotion + intensity + optional secondary).

**Provenance metadata (2 fields):** `annotator`, `annotation_confidence`.

### Data Splits

The corpus ships as one JSON file per source text under `data/processed/`. There is no train/test split at this stage; users should construct splits appropriate to their task.

| Source text | Layer | Entries | File |
|---|---|---|---|
| Purananuru | Sangam (Puram) | 388 | `Purananuru_All.json` |
| Akananuru | Sangam (Akam) | 400 | `Akananuru_All.json` |
| Kuruntokai | Sangam (Akam) | 400 | `Kuruntokai_Vaidehi_All.json` |
| Natrinai | Sangam (Akam) | 396 | `Natrinai_Vaidehi_All.json` |
| Thevaram | Bhakti | 4,043 | `Thevaram_All.json` |
| Divya Prabandham | Bhakti | 3,928 | `Divya_Prabandham_All.json` |
| Silappatikaram | Epic | 10 | `Silappatikaram_All.json` |
| Manimekalai | Epic | 493 | `Manimekalai_All.json` |
| Thirumanthiram | Spiritual | 335 | `Thirumanthiram_All.json` |
| **Total** | | **10,393** | |

Naladiyar and Pazhamozhi (Didactic layer) are on the roadmap but not yet in the corpus.

## Dataset Creation

### Curation Rationale

Existing digitized Classical Tamil resources have done the hard work of preserving and publishing the source texts. They were not designed to be queried as structured data, layered with interpretive annotations, or used as machine-readable training material. The Sentamizh Corpus adds those layers.

The 32-field schema is shaped to serve three audiences at once: Tamil literary scholars who expect Tolkappiyam-era categories; AI/ML researchers who expect machine-readable schemas; and creators (writers, designers, content makers) who want literary structure to be legible without classical-Tamil background. The cross-cultural bridge layer is the deliberate compromise that makes one dataset work for all three. See [docs/decisions/0001-32-field-schema.md](docs/decisions/0001-32-field-schema.md) for the full rationale.

### Source Data

#### Data Collection and Processing

Source HTML editions were downloaded from Project Madurai (32 files for Sangam, Bhakti, Epic, and Spiritual texts) and from Vaidehi Herbert's Sangam translation site (Kuruntokai and Natrinai, with English alignment). Each source has its own extractor under `scripts/extract_*.py` because the HTML structures differ enough that a single parser would be brittle. Verse-vs-commentary separation, where the source uses semantic typography, is handled by inspecting span colors via PyMuPDF; where typography is absent, structural cues (verse numbering, indentation) are used. Unicode normalization (NFC) and zero-width-character cleanup are applied uniformly.

Methodology details for the more challenging source materials are documented in [docs/extraction-analysis.md](docs/extraction-analysis.md).

#### Source Data Producers

The original texts are public-domain literary works produced over a span of roughly two thousand years (3rd century BCE through ~10th century CE). Their digitization is the work of the resources cited in [Dataset Sources](#dataset-sources). The corpus credits each source per-entry via the `source_url` field.

### Annotations

#### Annotation Process

Phase 1 annotation is being conducted manually by a single Classical-Tamil-fluent expert annotator using the custom mobile annotation tool under `annotator/`. The tool uses Soniox for streaming Tamil voice dictation and Agarathi (which proxies the University of Madras Tamil Lexicon and other Tamil dictionaries) for in-line dictionary lookups. The choice to start with manual annotation rather than LLM-prefill is recorded in [docs/decisions/0003-manual-annotation-not-llm-prefill.md](docs/decisions/0003-manual-annotation-not-llm-prefill.md).

Phase 2 will introduce LLM-assisted pre-annotation followed by expert review for the remaining null fields. LLM-generated annotations will be tagged distinctly via the `annotator` field so that downstream consumers can filter on annotation provenance.

#### Who are the annotators?

One Classical-Tamil-fluent expert (a family member of the project lead). Phase 2 plans include additional Tamil-literary scholars; the schema's controlled vocabularies are scheduled for independent expert review before that step.

#### Personal and Sensitive Information

The corpus contains historical literary texts. No personal information about contemporary individuals is present.

## Bias, Risks, and Limitations

- **Annotation depth is uneven across the schema.** Of the 32 schema fields, roughly 20 (the interpretive and bridge-layer fields) are largely null at this stage. Most entries currently provide identification and raw text but minimal interpretive metadata.
- **Some fields carry uniform extractor-applied default values that are not yet reviewed.** Bhakti texts have `rasa_primary='Shanta'` on every entry by default; `speaker_role` on Bhakti is uniformly `'devotee'`; on Epic, uniformly `'narrator'`; on Sangam-Puram (Purananuru), uniformly `'bard'`. These were stamped during extraction as priors and have not yet been reviewed verse-by-verse. They should be treated as defaults pending review, not authoritative annotations.
- **Translation coverage is partial.** English translations exist primarily for Kuruntokai and Natrinai (~99% coverage from Vaidehi's editions). Modern Tamil paraphrases (`modern_tamil`) are not yet populated for any entry.
- **17 verses are missing across three texts** (12 Purananuru, 4 Natrinai, 1 Kuruntokai), plus an anomalous KURU-401 whose canonical numbering needs scholarly review. Specifics in [CHANGELOG.md](CHANGELOG.md).
- **Schema enums have not yet been validated by independent Tamil scholars.** The Navarasa, Thinai, Nayika Bheda, and metre enum sets reflect standard literary references but expert sign-off is on the roadmap.
- **License complexity around `modern_tamil` integration.** PaaPeyarchi is CC-BY-NC-2.0; if its content flows into this Apache-2.0 corpus, license segregation is required. See [docs/integration-strategy.md](docs/integration-strategy.md).

### Recommendations

- **Treat null fields as un-annotated, not as absent.** A null `rasa_primary` does not mean a verse lacks rasa; it means no annotator has yet recorded one.
- **Filter on `annotator` and `annotation_confidence` for downstream model training.** Once those fields are populated, they let consumers separate manually-annotated entries from LLM-assisted ones, and gate inclusion on confidence.
- **Prefer Kuruntokai and Natrinai for any work requiring Classical-Tamil-to-English alignment** — those are the only texts with substantial English coverage today (from Vaidehi Herbert's translations). Akananuru's English layer and all Modern Tamil layers are not yet populated.

## Citation

If you use this dataset, please cite it via the [`CITATION.cff`](CITATION.cff) file in the repo root. GitHub renders that file as a "Cite this repository" widget on the project homepage with copy-pasteable BibTeX and APA forms.

## More Information

- Long-form story and motivation: [`docs/project-brief.md`](docs/project-brief.md).
- Future plans: [`ROADMAP.md`](ROADMAP.md).
- Architectural decisions and their rationale: [`docs/decisions/`](docs/decisions/).
- Project history (what shipped when): [`CHANGELOG.md`](CHANGELOG.md).
- How to contribute: [`CONTRIBUTING.md`](CONTRIBUTING.md).
- Phase 1 annotator setup: [`annotator/SETUP.md`](annotator/SETUP.md).
- Deployment automation: [`DEPLOY.md`](DEPLOY.md).

## Quick start (for developers)

```bash
# Run the full pipeline (extract → validate → integrate → statistics)
python3 scripts/run_all.py

# Validate the corpus against the schema (10,393 entries, all passing)
python3 scripts/validate.py data/processed/

# Run a specific stage
python3 scripts/run_all.py --stage 1                  # Extract only
python3 scripts/run_all.py --text kuruntokai          # One text only
python3 scripts/run_all.py --annotate --backend anthropic --model claude-sonnet-4-5  # LLM-assist (Phase 2)
python3 scripts/run_all.py --dry-run --verbose        # See what would run
```

For the annotator (mobile-first manual annotation tool): [`annotator/SETUP.md`](annotator/SETUP.md).
For the deploy pipeline (Netlify + GitHub Actions): [`DEPLOY.md`](DEPLOY.md).

## Dataset Card Authors

Revathi Prasad, with annotation contribution from a family member fluent in Classical Tamil.

## Dataset Card Contact

Issues and questions: please open an issue on the GitHub repository or use the contact in [`CITATION.cff`](CITATION.cff).
