# Sentamizh Corpus — Project Brief

This is the long-form story of the project: the vision, what the corpus is for, how it relates to existing resources, and the principles guiding how it's built. The [`README.md`](../README.md) is the structured short-form view; the [`ROADMAP.md`](../ROADMAP.md) is the explicit plan; this document is the narrative thread that ties them together.

## 1. Vision

A structured, open-source corpus of Classical Tamil literature — annotated across multiple interpretive frameworks, published in machine-readable form, and designed to be useful in computational, scholarly, and creative work alike.

Classical Tamil is a 2,000-year tradition. Sangam-era poetry, Bhakti devotional verse, the Tamil epics, and the spiritual and didactic traditions that follow are well-preserved as text — substantial volunteer scholarship has digitized them over the last three decades. What's missing is a *structured* layer on top: a schema that lets a researcher query "show me all Akam poems where the implicit speaker is the heroine's confidante (tozi)," or that lets an AI training pipeline ingest classical-Tamil verse with consistent metadata, or that lets a writer working in adjacent traditions find emotional and thematic structures they can build on.

The Sentamizh Corpus is one attempt at that structured layer.

## 2. Why this dataset doesn't yet exist anywhere else

Existing digital resources for Classical Tamil each solve a piece of the problem the corpus aims to address:

- **Project Madurai** preserves and publishes the source texts as HTML editions. Decades of volunteer typing and proofreading. The texts are accessible to anyone who can read Tamil; they are not designed to be queried as structured data.
- **Tamil Virtual Academy** provides scholarly digitization with annotations, primarily as PDFs. Excellent for reading; not designed for programmatic access.
- **Vaidehi Herbert's Sangam Translations** publishes verse-by-verse English translations of Sangam material with extensive commentary, organized as web pages. Beautiful for human reading; structured access requires scraping.
- **Hugging Face datasets** — PaaPeyarchi (Classical-Modern Tamil pairs), Kameshr's Sangam excerpts (English + themes + imagery for ~1,000 entries), pranesh-19's Sangam translations (~244 entries), kodebot's Purananuru meanings (~398 entries) — each covers a slice. None aims at the combination this corpus is designed to provide: multi-text scope, structured representation across Classical Tamil + Modern Tamil + English, and Tolkappiyam-aligned interpretive layers in one schema.

The Sentamizh Corpus's contribution is the structured, interpretive, multi-layer schema *on top of* the source material those projects have made available. It is genuinely additive — every Sangam verse in this corpus traces back to Project Madurai's or Vaidehi Herbert's editions; every Bhakti verse traces back to Project Madurai. The schema is what's new.

## 3. The multi-fold purpose

The corpus is not built for a single downstream use. The schema's design — and specifically the cross-cultural bridge layer — reflects this intentionally:

### As cultural preservation and a generational dialect bridge

Classical Tamil (Centamil) is linguistically distant from the Tamil spoken today. A reader fluent in modern Tamil cannot necessarily parse a Sangam verse without help. The corpus's `classical_tamil` → `modern_tamil` → `english` triplet structure is a deliberate bridge: each verse, once fully populated, will be readable by audiences with very different relationships to Tamil.

### As inspiration and reference material for creators

Storytelling seeds (`storytelling_seed_narrative`, `storytelling_seed_emotional`), rasa, dhvani, ullurai, and visual_imagery — these are not just academic annotations. They are creative prompts, structured. A screenwriter, dramatist, designer, or game writer working in Indian or Indic-adjacent traditions can query the corpus for emotional structures, narrative kernels, or imagery patterns drawn from a deep tradition, with the bridge layer making them legible without classical-Tamil expertise.

### As AI training data for low-resource Indic NLP

The corpus is a structured Classical Tamil source with consistent fields, validated schema, and machine-readable layout, designed to support trilingual representation (Classical Tamil, Modern Tamil, English) as the multi-language annotation layers fill in. Useful, as those layers populate, for classical-to-modern paraphrase, classical-to-English translation, literary-style generation, and benchmarking. Field-level licensing and provenance make it possible to filter to subsets appropriate for commercial use.

NVIDIA released Nemotron 3 Nano Omni on April 28, 2026 — an open-weights multimodal model (30B-A3B mixture-of-experts) with full access to weights, training recipes, and quantization tooling. The announcement does not enumerate language coverage, and Tamil literary content is unlikely to be present in any general-purpose multimodal pretraining set. The Sentamizh Corpus is structured to add that capability through fine-tuning. Phase 5 of the roadmap targets fine-tuning Nemotron on this corpus specifically; the rationale is recorded in [ADR 0005](decisions/0005-nemotron-3-nano-omni-as-phase-5-target.md).

### As a register and voice reference for spoken Indic content

This is a hypothesis to test rather than a claim about current capability. Tamil literary tradition is unusually rich in *register variation* — the way a tozi speaks to a talaivi differs from the way a devotee speaks to a deity, which differs again from the way a bard speaks of a king. The dhvani, ullurai, and rasa annotations capture sub-textual emotional layering that may be useful for natural-register conversational AI in Indic languages, where current systems often default to a news-formal style. Whether the corpus actually delivers on this is to be tested in Phase 5.

### As infrastructure for Tamil literary scholarship

A schema-validated, publicly versioned, citable corpus complements the existing digitized resources by adding a structured, queryable, machine-readable layer they were never designed to provide. It is a foundation for incremental scholarship — annotations, corrections, and extensions can be layered on without losing the source.

## 4. The corpus today

10,393 schema-validated entries across 9 source texts: Purananuru, Akananuru, Kuruntokai, Natrinai (Sangam); Thevaram, Divya Prabandham (Bhakti); Silappatikaram, Manimekalai (Epic); Thirumanthiram (Spiritual). The full table of counts, formats, and source attributions is in [`README.md`](../README.md).

Phase 1 manual annotation is just beginning. The interpretive fields — rasa, themes, dhvani, ullurai, karu, uri — are largely unannotated at this stage. A few fields carry uniform extractor-applied default values (Bhakti `rasa_primary='Shanta'`, etc.) that should be treated as priors pending review, not authoritative annotations. See [`CHANGELOG.md`](../CHANGELOG.md) and [`README.md`](../README.md) § Bias, Risks, and Limitations for the honest current state.

## 5. Schema rationale, briefly

The 32-field schema is organized in four layers — Core (identification + text), Tamil-native (Tolkappiyam-aligned categories), Interpretive (rasa, themes, philosophy, storytelling seeds), and Cross-cultural Bridge (Plutchik / Nayika Bheda / visual imagery) — plus two metadata fields. Each layer is independently optional at query time, so a consumer can use only the layers relevant to their work.

The full design rationale lives in [ADR 0001](decisions/0001-32-field-schema.md). Per-field rationale — what each field captures, the source tradition it draws on, why each is in the schema — lives as `description` properties inside [`schemas/sentamizh_schema.json`](../schemas/sentamizh_schema.json) itself, where JSON Schema tools and IDEs surface it next to the fields.

## 6. Operating principles

These are the principles the project tries to live by. They show up across every operational doc, every ADR, and every commit.

### Ship and experiment

The corpus and the annotator both exist because shipping early surfaces problems that planning could not. Phase 1 annotator went through six rounds of fixes after first-use observation — the kind of feedback no design review would have produced. The same logic applies forward: ship the next phase early, in a state honest about its limits, and let observation drive the next round.

### Telemetry-grounded decisions

Operational claims are backed by data wherever possible. The annotator's `_telemetry` Sheet records every API call's latency, cost, and provider. Phase 2 ASR comparisons (Soniox vs Whisper vs IndicConformer) will produce comparable numbers, not vibes. When we don't have data, the relevant ADR is honest about the gap.

### Honest-by-default documentation

Every claim in public-facing documentation either links to evidence (a commit, an ADR, an external benchmark) or is explicitly labeled as a hypothesis. Aspirational language lives in `ROADMAP.md`; present-tense claims live in `README.md`; reasoning behind choices lives in `docs/decisions/`. Mixing those tenses is the single most common cause of doc rot, so the project tries hard to keep them separate.

### Open by default

Apache 2.0 license. Public extraction scripts. Public schema. Public annotator code. Public ADRs explaining why each choice was made — including the choices that didn't work and why they were rejected. The intent is for the project to be useful even if specific claims need refinement.

### Respect for upstream work

This corpus exists because of decades of volunteer scholarship — Project Madurai, Tamil Virtual Academy, Vaidehi Herbert's translations, the maintainers of the various Hugging Face datasets, the original Tamil literary tradition itself. Public commentary about those projects in this corpus's docs is additive ("describes what each one is for"), never positional ("what they're missing").

## 7. Roadmap, summary

Detailed in [`ROADMAP.md`](../ROADMAP.md). The shape:

- **Phase 1 (current):** Manual annotation by one expert; merge-back from Sheets to canonical JSON; backfill missing verses; schema vocabulary review.
- **Phase 2:** PaaPeyarchi integration (license-permitting); LLM-assisted annotation with expert review; self-hosted IndicConformer behind the same proxy contract; ASR benchmark.
- **Phase 3:** TensorRT optimization, Hugging Face publication, demo Space.
- **Phase 4:** Cross-corpus extension to Sanskrit, Hindi Bhakti, and narrative didactic.
- **Phase 5:** Voice and register applications (hypothetical, to be tested).

## 8. References

### Primary literary frameworks

- Tolkappiyam, *Porul Adhikaram* — the foundational Tamil grammar and poetics framework. Source for Thinai, Akam/Puram, Karu, Uri, Ullurai.
- Bharata Muni, *Natya Shastra* (~200 BCE–200 CE) — source for Navarasa.
- Anandavardhana, *Dhvanyaloka* (9th century CE) — source for the dhvani layer.
- Plutchik, R. (1980). *A general psychoevolutionary theory of emotion* — source for the cross-cultural bridge layer's emotional valence mapping.

### Source materials and digitization projects

- Project Madurai (projectmadurai.org).
- Tamil Virtual Academy (tamilvu.org).
- Vaidehi Herbert's Sangam Translations (sangamtranslationsbyvaidehi.com).
- PaaPeyarchi (huggingface.co/datasets/akdiwahar/PaaPeyarchi).
- AI4Bharat Indic NLP catalog (ai4bharat.github.io/indicnlp_catalog).
- Tamil NLP Catalog (narvidhai.github.io/tamil-nlp-catalog).

### Within this repository

- [`README.md`](../README.md) — short-form description and dataset card.
- [`ROADMAP.md`](../ROADMAP.md) — explicit forward plan.
- [`CHANGELOG.md`](../CHANGELOG.md) — what shipped when.
- [`docs/decisions/`](decisions/) — Architecture Decision Records.
- [`docs/integration-strategy.md`](integration-strategy.md) — how upstream HF datasets relate to this corpus.
- [`docs/extraction-analysis.md`](extraction-analysis.md) — extraction methodology notes.
