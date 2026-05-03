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
- `[planned]` Self-hosted Tamil ASR via [VEXYL-STT](https://medium.com/@anilmathewm/vexyl-stt-free-self-hosted-indian-language-speech-to-text-server-f2909003aaf6) — a deploy-ready wrapper around AI4Bharat's IndicConformer with WebSocket streaming. Substantially less infrastructure work than building a serving layer from scratch. Served behind the same `/transcribe` proxy contract so the annotator frontend doesn't change ([ADR 0004](docs/decisions/0004-proxy-contract-for-pluggable-backends.md)).
- `[planned]` Empirical comparison of Tamil ASR options on classical-Tamil dictation: Soniox, [vasista22/whisper-tamil-medium](https://huggingface.co/vasista22/whisper-tamil-medium), VEXYL-STT (IndicConformer), and — if its audio modality handles Tamil — [Nemotron 3 Nano Omni](https://developer.nvidia.com/blog/nvidia-nemotron-3-nano-omni-powers-multimodal-agent-reasoning-in-a-single-efficient-open-model/). Methodology, audio sample, WER, latency, cost-per-minute. Closes the evidence gap noted in [ADR 0002](docs/decisions/0002-soniox-over-whisper-for-tamil-stt.md) and informs the Phase 5 fine-tuning base-model choice.
- `[planned]` Add Naladiyar (Didactic, ~400 quatrains). The Project Madurai URL we tried previously serves Malaipadukadaam by mistake; the corrected source needs to be identified.
- `[planned]` Add Pazhamozhi (Didactic, ~400 proverbs). Source not yet identified.
- `[planned]` **Self-hosted UMTL dictionary backend.** OCR the public-domain [University of Madras Tamil Lexicon scans on Internet Archive](https://archive.org/details/in.ernet.dli.2015.85194) (1924–1936 print) with Tesseract Tamil, clean and structure into a queryable JSON corpus, publish under [`indic-corpora`](https://huggingface.co/indic-corpora) on HuggingFace. Add as a second backend behind the same `/lookup` proxy ([ADR 0006](docs/decisions/0006-tamil-wiktionary-for-dictionary-lookup.md)) — Phase 1 uses Tamil Wiktionary at runtime; Phase 2 adds UMTL alongside or in front of it. Comparable benchmark of UMTL vs Wiktionary coverage and quality is the resulting publication artifact.

## Phase 3 — Performance and accessibility

- `[planned]` Quantization of the Phase 5 fine-tune: TensorRT INT8 baseline, plus FP8 and NVFP4 (Nemotron's first-class quantization options). Publish before/after benchmarks on the same classical-Tamil dictation set used in the Phase 2 ASR comparison.
- `[planned]` Hugging Face dataset publication under the [`indic-corpora`](https://huggingface.co/indic-corpora) namespace with a formal `0.1.0` release tag.
- `[planned]` Hugging Face Space demo: a small interactive viewer over the corpus.

## Phase 4 — Cross-corpus extension

- `[planned]` Sanskrit (e.g., Adi Shankara stotras: *Soundarya Lahari*, *Bhaja Govindam*).
- `[planned]` Hindi Bhakti (Kabir dohas, Mirabai bhajans).
- `[planned]` Panchatantra (narrative didactic).
- `[planned]` Schema generalization to handle non-Tamil source materials while preserving the cross-cultural bridge layer's mappings.

## Phase 5 — Voice and conversational applications (hypothetical)

- `[planned]` Fine-tune [Nemotron 3 Nano Omni](https://developer.nvidia.com/blog/nvidia-nemotron-3-nano-omni-powers-multimodal-agent-reasoning-in-a-single-efficient-open-model/) on the Sentamizh Corpus to add Tamil literary understanding to a base model whose pretraining is unlikely to include classical Tamil. Publish: methodology, fine-tune weights under the [`indic-corpora`](https://huggingface.co/indic-corpora) HuggingFace namespace, and benchmarks against the base model on Tamil literary tasks. Reasoning recorded in [ADR 0005](docs/decisions/0005-nemotron-3-nano-omni-as-phase-5-target.md).
- `[planned]` Test the voice/register hypothesis using Nemotron's audio modality as the testbed: do the dhvani / ullurai / rasa annotations capture enough of the indirect, evocative quality of literary Tamil to inform less-formal conversational generation? **This is a hypothesis to be tested, not a claim about the corpus's current capability.**

## Things explicitly NOT planned

- Generating or attributing biographical claims about specific historical Sangam poets.
- Retrofitting the schema for a single downstream model architecture.
- Locking the dataset behind a commercial license.
