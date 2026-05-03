# Changelog

All notable changes to the Sentamizh Corpus are documented in this file.

The format is based on [Keep a Changelog v1.1.0](https://keepachangelog.com/en/1.1.0/), and the corpus dataset adheres to [Semantic Versioning](https://semver.org/) once the first numbered release ships publicly.

## [Unreleased]

### Added (AI translation suggestions)
- `annotator/google_apps_script.gs`: new `handleTranslate(body)` function and `POST /exec action=translate` endpoint. Calls NVIDIA NIM (`integrate.api.nvidia.com`) with `nvidia/nemotron-3-nano-omni` by default, swappable via `TRANSLATION_MODEL` Script Property. Stacks context aggressively: the verse's classical Tamil + the annotator's modern Tamil paraphrase (when generating English) or English (when generating modern Tamil) + Wiktionary definitions for words in the verse. Routes the LLM through the easiest available representation rather than translating from raw classical Tamil where every model performs poorly.
- `annotator/index.html`: new "Suggest translation" button on the modern Tamil and English fields. Renders the LLM response as an italic light-grey draft in the textarea with an "AI-assisted draft — review before saving" badge. The draft is **not** committed to the corpus until the annotator edits it (any keystroke or dictation), at which point the badge clears and the draft becomes her text. Wiktionary definitions for words in the verse are pre-fetched in the background on verse load so the button click doesn't block on cold lookups.
- `docs/decisions/0007-translation-backend.md`: ADR for the choice (NVIDIA NIM + Nemotron, proxy contract per ADR 0004, context-stacking architecture).
- `docs/decisions/0008-open-model-eval-classical-tamil.md`: ADR for the eval methodology to compare 5 candidate models (Nemotron, DeepSeek, Llama 3.3, Sarvam, IndicTrans2) on a fixed 10-verse test set across 3 metrics (lexical anchoring, faithfulness, fluency). The eval is concurrent with Phase 1, not blocking.
- `annotator/google_apps_script.gs`: `authorize()` helper now also touches NVIDIA NIM so a single editor-driven consent flow grants the `script.external_request` scope for all three outbound hosts (Wiktionary, Soniox, NIM).
- `annotator/SETUP.md`: Step 5 expanded with `NVIDIA_API_KEY` and `TRANSLATION_MODEL` Script Properties (both optional — the AI suggestion feature is opt-in).
- `DEPLOY.md`: troubleshooting entry for "NVIDIA_API_KEY not configured." API keys section updated.

### Changed (selection-aware mic dictation)
- `annotator/index.html`: replaced the previous "append to end" Soniox dictation with **selection-aware insertion**. On mic tap, the textarea's `selectionStart`/`selectionEnd` is captured. Interim transcripts render in a floating preview overlay near the textarea instead of mutating the textarea on every token (sidesteps cursor fights with the annotator editing during dictation). On stop, the final transcript is committed via `setRangeText` at the captured selection — replacing the selection if any, inserting at cursor otherwise, with a leading space when needed. Lets the annotator point at a specific word to replace, dictate, and have the new text land where she pointed.

### Fixed (per-field STT language hint)
- `annotator/index.html`: Soniox `languageHints` was hardcoded to `['ta']` for every mic, so the English field's mic transcribed English speech into Tamil characters. `makeTextField` and `makeListField` now accept a `lang` parameter (defaults to `'ta'`); the English-translation field passes `lang: 'en'`. All other free-text fields stay on Tamil.

### Fixed (Wiktionary attribution in popover)
- `annotator/index.html`: dictionary popover attribution updated from a hardcoded "University of Madras Tamil Lexicon · via Agarathi" string to the correct "Source: Tamil Wiktionary (CC BY-SA)" linking to the actual article on `ta.wiktionary.org`. Empty-result popovers also now link to Wiktionary so the annotator can check the article directly or contribute the missing word upstream. The hardcoded UMTL/Agarathi string was a leftover from before the Wiktionary migration in [ADR 0006](docs/decisions/0006-tamil-wiktionary-for-dictionary-lookup.md) and was mis-crediting Wiktionary content as UMTL — caught after the May 2 deploy.

### Fixed (frontend build)
- `netlify.toml`: pinned `PYTHON_VERSION = "3.11"` in `[build.environment]`. Without this, recent Netlify build images don't have `python3` on PATH, so `python3 scripts/build_annotator_data.py` fails before producing any log output (we saw a "Loading" log with no content on May 2). The script only uses stdlib so any 3.8+ would work; 3.11 is the safe default.

### Added (one-time OAuth consent helper)
- `annotator/google_apps_script.gs`: new `authorize()` function that calls each scoped API (`UrlFetchApp`, `SpreadsheetApp`, `ScriptApp`) once. Running it from the editor (function dropdown → `authorize` → Run) triggers Apps Script's OAuth consent flow for every scope the manifest declares, in a single deliberate step. Without this, `clasp push` and `clasp deploy` succeed but the live web app fails at runtime with `You do not have permission to call UrlFetchApp.fetch` whenever it tries to reach Wiktionary or Soniox — because consent is only granted when a function runs from the editor, never from CI. We hit exactly this on May 2: GET annotation reads worked (spreadsheet scope was already consented because the script is bound to a Sheet), but POST `/lookup` failed silently because the `script.external_request` scope had never been consented to.
- `DEPLOY.md`: new "One-time OAuth consent" subsection in Step 3 documents the helper. Troubleshooting section now lists the `UrlFetchApp.fetch permission` error with the same fix.

### Changed (backend auto-deploy hardening)
- `.github/workflows/deploy-backend.yml`, `Makefile`, `DEPLOY.md`: backend deploy upgraded from `@google/clasp@2.4.2` to `@google/clasp@3.3.0`, and the single `clasp deploy --deploymentId` step replaced with three explicit steps: `clasp push --force` → `clasp version` (creates a new versioned snapshot, captures the version number) → `clasp redeploy $DEPLOYMENT_ID -V $VERSION` (binds the deployment to that exact version).
  - Why: the old single-step path is the root cause of [clasp issue #63](https://github.com/google/clasp/issues/63) — without an explicit `-V`, redeploys can silently shadow into a fresh deployment under certain Apps Script project states, which produces a new `/exec` URL and breaks any device with a bookmark to the annotator. We hit this twice on May 2 before tracking it down. Pinning the version eliminates the ambiguity.
  - The CI workflow now also runs a manifest guard step that fails the build if `annotator/appsscript.json` is missing `"webapp": {"access": "ANYONE", "executeAs": "USER_DEPLOYING"}`. The web app's "Anyone" access setting persists across redeploys only because the manifest declares it; if the field is dropped, every redeploy from then on silently reverts the live deployment to "Only myself" and the annotator URL stops working on phones. The guard catches that before any deploy can happen.
  - `Makefile` `deploy-backend` mirrors the same three-step pattern and the same manifest guard, so local `make deploy-backend` and CI behave identically.
- `DEPLOY.md`: new conditional Step 6 documents the OAuth client publishing-status quirk. clasp's default OAuth client is already published by Google, so first-time setup needs no Cloud Console work. The step only applies when CI starts failing weekly with `invalid_grant` (indicates a custom OAuth client in Testing mode) or when the operator wants a project-owned client for rate-limit or REST-API reasons.
- `DEPLOY.md`: troubleshooting section now documents the cleanup procedure for duplicate deployments (`clasp deployments` + `clasp undeploy`), the corrupted-deployment one-time UI fix to restore "Anyone" access after cleanup, and the recovery path when the manifest guard fails CI.

### Added
- `scripts/build_annotator_data.py` — populates `annotator/data/` from the canonical `data/processed/` files at deploy time, so the ~19 MB corpus is not duplicated in the repo. Invoked by Netlify (via `netlify.toml`) and by the Makefile (`make deploy-frontend`).

### Changed (dictionary backend)
- `annotator/google_apps_script.gs`: dictionary lookup now queries Tamil Wiktionary (`ta.wiktionary.org`) at runtime instead of Agarathi. No API key required. Same `/lookup` response shape as before, so the frontend popup is unchanged. Reasoning and Phase 2 plan to add a self-hosted UMTL backend recorded in [ADR 0006](docs/decisions/0006-tamil-wiktionary-for-dictionary-lookup.md).
- `annotator/index.html`: dictionary popover attribution updated to "Source: Tamil Wiktionary (CC BY-SA)" with a clickable link to the article on `ta.wiktionary.org`. Previously a hardcoded "University of Madras Tamil Lexicon · via Agarathi" string was rendered for every result, which mis-attributed Wiktionary content to UMTL — caught after the May 2 deploy when the popover started showing the wrong source. Empty-result popovers also now link to Wiktionary so annotators can check the article directly or contribute the missing word upstream.
- `annotator/SETUP.md`: removed the Agarathi subscription step (Step 3); only `SONIOX_API_KEY` is required in Script Properties now.
- `ROADMAP.md` Phase 2: added a self-hosted UMTL dictionary backend item — OCR the public-domain Internet Archive scans, publish under `indic-corpora`, add as a second backend behind the same `/lookup` proxy. Phase 1 uses Wiktionary; Phase 2 will benchmark UMTL vs Wiktionary as a project publication.

### Added (Phase 5 target)
- New ADR: [`docs/decisions/0005-nemotron-3-nano-omni-as-phase-5-target.md`](docs/decisions/0005-nemotron-3-nano-omni-as-phase-5-target.md). Records the decision to target NVIDIA's Nemotron 3 Nano Omni (released April 28, 2026; open-weights 30B-A3B mixture-of-experts multimodal model) as Phase 5's fine-tuning base. The model's announcement does not enumerate language coverage; the corpus is structured to add Tamil literary understanding via fine-tuning.

### Changed (roadmap sharpening)
- `ROADMAP.md` Phase 2: replaced "self-hosted IndicConformer from scratch" with the specific deploy-ready VEXYL-STT path. The ASR comparison item now lists four named candidates (Soniox, vasista22/whisper-tamil-medium, VEXYL-STT/IndicConformer, and Nemotron's audio modality if applicable) instead of three generic ones.
- `ROADMAP.md` Phase 3: quantization scope sharpened to TensorRT INT8 + FP8 + NVFP4 (Nemotron's first-class quantization options); HF dataset namespace explicitly named.
- `ROADMAP.md` Phase 5: replaced the vague "NeMo fine-tuning experiments" with a specific named target (Nemotron 3 Nano Omni) and connected the voice/register hypothesis test to Nemotron's audio modality.
- `docs/project-brief.md` §3 (multi-fold purpose, AI training data subsection): added a paragraph noting Nemotron 3 Nano Omni's release and the gap-filling fit for the corpus.

### Changed (attribution)
- `README.md`, `annotator/SETUP.md`, `DEPLOY.md`, and `CITATION.cff` now name Vijayalakshmi Prasad as the project's classical-Tamil expert annotator. Previously these docs used "family member" or "Mom"; with the project moving toward public contribution, naming the person whose annotation work is the most distinctive content of the corpus is the more honest framing. `CITATION.cff` lists her as a second author so any citation of the dataset credits her work.

### Changed (honesty pass: "trilingual" and "deeply annotated")
- `README.md`, `CITATION.cff`, `schemas/sentamizh_schema.json`, `docs/project-brief.md`, and `scripts/annotate_entries.py` no longer describe the corpus as "trilingual" or "deeply annotated" in the present tense. The schema is *designed* for trilingual representation, but Modern Tamil coverage is currently 0% and English coverage is ~8% (Kuruntokai and Natrinai only); the schema has 22 interpretive fields that are largely null at this stage. The revised wording frames "trilingual" as design intent and points readers to the current per-language and per-field coverage in Dataset Structure and Bias/Risks/Limitations.
- Filled in placeholder `<owner>/sentamizh-corpus` URLs in `README.md`, `CITATION.cff`, and `SECURITY.md` with the actual `indic-corpora/sentamizh-corpus` GitHub URL. Added a Hugging Face organization link to `README.md`.

### Changed
- `.gitignore`: `data/raw/` (third-party source HTML), `data/external/` (PaaPeyarchi), `exports/` (regenerable), `archive/` (local-only historical artifacts), and `annotator/data/*.json` (regenerated at deploy time, except for `manifest.json`) are no longer committed. Reproducibility is preserved through the `scripts/download_*.py` and `scripts/build_annotator_data.py` chain. See README's "Source Data" section for source URLs.
- `netlify.toml`: now invokes `scripts/build_annotator_data.py` as the build command. Frontend deploys still publish `annotator/` as before.
- `Makefile`: `deploy-frontend` now depends on a new `build-annotator-data` target; the same script Netlify runs is invoked locally before `netlify deploy --prod`.
- `docs/audit-2026-04-19.md` retired from the public docs tree (preserved locally only). Most issues it identified were resolved in the 0.1.0 release; the remaining items (missing verses, controlled-vocabulary review) are tracked in `ROADMAP.md`.
- `annotator/data/manifest.json`: corrected Kuruntokai count from 401 to 400 (the duplicate KURU-204 fix changed the entry count).
- `schemas/sentamizh_schema.json`: per-field rationale (drawn from the original v2 schema-expansion design doc) is now embedded as `description` properties on each field, where JSON Schema tools and IDEs surface it next to the fields. Top-level schema description corrected from "three layers" to "four content layers plus annotation metadata" to match the rest of the documentation.
- `schemas/sentamizh_schema.json`: removed an overclaim in the `emotional_valence` description ("global standard in UX, advertising, content recommendation") that survived from earlier drafts. Replaced with a neutral description naming Plutchik's Wheel as one of the widely-cited general-purpose emotion taxonomies (alongside Ekman and Russell), with an honest reason for choosing it (its primary/intensity/dyad structure maps cleanly to a JSON object).
- `docs/schema-expansion-v2.md` retired from the public docs tree (preserved locally only). It was a v1-to-v2 design-rationale artifact; its field-level content now lives in the schema JSON's `description` properties. Cross-references in `docs/project-brief.md` and `docs/decisions/0001-32-field-schema.md` updated to point at the schema JSON instead.
- `docs/extraction-analysis.md`: added a scope note clarifying the analysis covers one specific Project Madurai source file (which has been moved to `data/processed/_intermediates/`) and that other source extractors handle their own structural variations.

## [0.1.0] - 2026-04-30 — Initial public release

### Added
- 10,393 schema-validated entries across 9 source texts: Purananuru (388), Akananuru (400), Kuruntokai (400), Natrinai (396), Thevaram (4,043), Divya Prabandham (3,928), Silappatikaram (10), Manimekalai (493), Thirumanthiram (335).
- 32-field JSON Schema (Draft 2020-12) covering Core, Tamil-native, Interpretive, and Cross-cultural Bridge layers.
- Phase 1 annotator: mobile-first web app under `annotator/` with Soniox Tamil dictation and Agarathi dictionary lookup. Backed by Google Apps Script and Google Sheets.
- Apache 2.0 LICENSE and `CITATION.cff` for attribution.
- Deployment automation: `netlify.toml` (frontend auto-deploy), `.clasp.json` + `.github/workflows/deploy-backend.yml` (Apps Script auto-deploy), `Makefile` (local deploy shortcuts), `DEPLOY.md` (runbook).
- Repository documentation: this CHANGELOG, plus `ROADMAP.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, and the README rewritten as a Hugging Face dataset card.
- `docs/decisions/` — first four Architecture Decision Records, covering the schema design, the Soniox choice, the manual-annotation choice, and the proxy contract.
- `docs/project-brief.md` — long-form vision and motivation, replacing the earlier `.docx` brief (which is preserved locally but not committed; the canonical brief is now this markdown file).
- `scripts/validate.py` now performs corpus-wide duplicate-`verse_id` detection and gracefully skips files that fail to read with an OSError or JSON parse error, rather than crashing the run.

### Changed
- Schema: dropped `period` from required fields. The field exists in the schema but is not populated on any current entry; making it required would be dishonest.
- `data/processed/`: moved Purananuru intermediate part files (`Purananuru_Ed*_Part*.json`) to `data/processed/_intermediates/` so directory-wide pipelines do not double-count them. The validator now skips top-level files starting with `_`.
- `scripts/run_all.py`: removed the redundant `--skip-annotation` flag (its default value made it a no-op). Stage 4 (LLM annotation) is opt-in via `--annotate`. JSON merge errors are now logged with the failing file path rather than being silently swallowed.
- `scripts/annotate_entries.py`: prompts now wrap untrusted verse text in `<verse>...</verse>` and `<translation>...</translation>` delimiters with a system-prompt note, so prompt-injection from extraction artifacts is contained. Transient API errors (408, 425, 429, 5xx) are retried with exponential backoff that honors `Retry-After`.
- `annotator/index.html`: lookup pill and dictionary popover switched from `position: fixed` to `position: absolute` so they correctly anchor to the selected word on scrolled pages.
- `annotator/index.html`: Soniox model updated from the retired `stt-rt-preview` to the current `stt-rt-v4`. The previous identifier was sunset on 2025-11-30.
- `docs/integration-strategy.md` (renamed from `dataset_integration_strategy.md`): the "What this buys us" section now reflects that PaaPeyarchi integration has not yet been executed; counts are described as upper bounds rather than as outcomes.

### Fixed
- Removed duplicate `KURU-204` entry — a 1,299-character commentary blob captured alongside the canonical Kuruntokai 204 verse during scraping. The canonical short verse remains; the commentary blob has been removed.
- `annotator/google_apps_script.gs`: corrected Agarathi proxy URL from `/dictionary` to `/dictionary/search`. Also added handling for the `description` field in Agarathi's response, which is where the actual definition text lives — the previous response normalizer never read it, so the dictionary popup would have shown empty results.

### Known issues (carried forward into Unreleased and Roadmap)
- 17 verses missing across three texts: Purananuru is missing 35, 55, 80, 95, 104, 109, 186, 187, 267, 268, 349, 364; Natrinai is missing 25, 234, 242, 385; Kuruntokai is missing 370 and contains an anomalous KURU-401 whose canonical numbering needs scholarly review.
- 22 of 32 schema fields are largely unannotated across the corpus. Phase 1 manual annotation is just beginning.
- Bhakti and Spiritual texts have uniform extractor-applied default values in `rasa_primary`, `speaker_role`, etc. that have not been verse-by-verse reviewed. They should be treated as defaults pending review.
- `modern_tamil` is 0% populated. The PaaPeyarchi integration plan is documented but has not been executed; license segregation is required before any CC-BY-NC content can be merged.
