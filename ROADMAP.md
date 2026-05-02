# Roadmap

This file lists *planned* and *aspirational* work. Anything not tagged `[shipped]` is a hypothesis about what might happen, not a commitment.

When an item ships, it moves from this file into [`CHANGELOG.md`](CHANGELOG.md) (with a date and version) and the corpus's [`README.md`](README.md) is updated to reflect the new state.

Status tags used below: `[planned]`, `[in progress]`, `[shipped]`, `[abandoned]`.

---

## Phase 1 — Manual annotation (current)

- `[shipped]` Phase 1 annotator deployed: mobile-first web app, Soniox dictation, Agarathi dictionary lookup, Google Sheets backend.
- `[shipped]` 10,393 entries extracted and schema-validated.
- `[shipped]` Deployment automation in place (Netlify auto-deploy for the frontend, GitHub Actions + clasp for the Apps Script backend).
- `[in progress]` Manual annotation of interpretive fields by the project's classical-Tamil expert annotator.
- `[planned]` Merge-back script that pulls annotations from the Google Sheet back into `data/processed/*_All.json`. Without this, the Sheet diverges from the canonical corpus over time.
- `[planned]` Backfill of 17 missing verses (12 Purananuru, 4 Natrinai, 1 Kuruntokai). Each requires manual sourcing or targeted re-extraction.
- `[planned]` Independent expert review of the schema's controlled vocabularies — the enum sets for `rasa_primary`, `thinai`, `nayika_bheda`, and `metre`. This should happen before significant annotation accumulates, to avoid retroactive remapping.
- `[planned]` Clear or distinctly tag the placeholder values (`rasa_primary='Shanta'` on all Bhakti, `speaker_role='devotee'` on all Bhakti, `'narrator'` on Epic, `'bard'` on Sangam-Puram). They are extractor defaults, not annotations, and the current data shape risks them being mistaken for the latter.

## Phase 2 — Coverage and quality

- `[planned]` PaaPeyarchi integration to draft `modern_tamil` field across matched verses. License segregation is required first — PaaPeyarchi is CC-BY-NC-2.0, so its content cannot be merged into the Apache-2.0 corpus without an explicit non-commercial subset or independent re-translation. See [docs/integration-strategy.md](docs/integration-strategy.md).
- `[planned]` LLM-assisted pre-annotation of the still-null interpretive fields, followed by expert review. The LLM annotator (`scripts/annotate_entries.py`) is built; the trigger is having the controlled vocabularies signed off (Phase 1 item above) so the LLM is given stable enums.
- `[planned]` Self-hosted IndicConformer ASR as an alternative to Soniox, served behind the same `/transcribe` proxy contract so the annotator frontend doesn't change. This is a real-world test of the proxy-contract decision recorded in [ADR 0004](docs/decisions/0004-proxy-contract-for-pluggable-backends.md).
- `[planned]` Empirical benchmark of Tamil ASR on classical-Tamil dictation: Whisper-large-v3 vs Soniox vs self-hosted IndicConformer. Methodology, audio sample, WER results, latency, and cost-per-minute. The benchmark exists partly to close the evidence gap noted in [ADR 0002](docs/decisions/0002-soniox-over-whisper-for-tamil-stt.md).
- `[planned]` Add Naladiyar (Didactic, ~400 quatrains). The Project Madurai URL we tried previously serves Malaipadukadaam by mistake; the corrected source needs to be identified.
- `[planned]` Add Pazhamozhi (Didactic, ~400 proverbs). Source not yet identified.

## Phase 3 — Performance and accessibility

- `[planned]` TensorRT INT8 quantization of the self-hosted ASR for faster inference on commodity GPUs.
- `[planned]` Hugging Face dataset publication with a formal `0.1.0` release tag.
- `[planned]` Hugging Face Space demo: a small interactive viewer over the corpus.

## Phase 4 — Cross-corpus extension

- `[planned]` Sanskrit (e.g., Adi Shankara stotras: *Soundarya Lahari*, *Bhaja Govindam*).
- `[planned]` Hindi Bhakti (Kabir dohas, Mirabai bhajans).
- `[planned]` Panchatantra (narrative didactic).
- `[planned]` Schema generalization to handle non-Tamil source materials while preserving the cross-cultural bridge layer's mappings.

## Phase 5 — Voice and conversational applications (hypothetical)

- `[planned]` Investigate the corpus's utility as a register/voice reference for natural-sounding spoken Tamil/Hindi/English script generation. Hypothesis: the dhvani / ullurai / rasa annotations capture the indirect, evocative quality of literary Tamil in a way that may inform less-formal conversational AI script generation. **This is a hypothesis to be tested, not a claim about the corpus's current capability.**
- `[planned]` NeMo fine-tuning experiments using the corpus as training data for downstream Indic NLP tasks.

## Things explicitly NOT planned

- Generating or attributing biographical claims about specific historical Sangam poets.
- Retrofitting the schema for a single downstream model architecture.
- Locking the dataset behind a commercial license.
