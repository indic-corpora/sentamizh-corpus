# 0008 — Comparing open-weight models on classical Tamil paraphrase + translation

- **Status:** Accepted (methodology); evaluation pending
- **Date:** 2026-05-03

## Context

[ADR 0007](0007-translation-backend.md) commits to NVIDIA NIM as the architectural backend for translation suggestions, with `TRANSLATION_MODEL` as a runtime-swappable Script Property. It defaults to `nvidia/nemotron-3-nano-omni` for Phase 5 alignment, but it explicitly does not claim Nemotron is the *best* model for classical Tamil paraphrase and English translation. None of the candidate open-weight LLMs are pretrained on meaningful classical Tamil corpora. Picking a model on vibes or vendor preference instead of evidence would be inconsistent with the project's framing.

This ADR defines the methodology for an empirical comparison whose result is a publishable artifact and whose chosen winner is encoded as the project's `TRANSLATION_MODEL` value.

## Decision

We run a structured comparison of **5 candidate models** on a **fixed 10-verse test set** sampled across the corpus's genre families, evaluated on **3 metrics** (lexical anchoring, semantic faithfulness, fluency), with **all prompts, scores, and outputs published** alongside the corpus.

### Candidate models

| Candidate | Why it's in the set |
|---|---|
| **NVIDIA Nemotron 3 Nano Omni** (`nvidia/nemotron-3-nano-omni`) | Phase 5 fine-tune target. Open weights, NIM-hosted, on-strategy default. |
| **DeepSeek V3** (`deepseek-ai/deepseek-v3`) | Open weights, top open-model leaderboards 2025–2026, strong multilingual. |
| **Llama 3.3 70B Instruct** (`meta/llama-3.3-70b-instruct`) | Reference open-weight baseline, well-understood failure modes. |
| **Sarvam-1 / Sarvam-M** (`sarvamai/sarvam-1` or `sarvamai/sarvam-m`) | Indian-language-focused, the strongest Tamil-aware general LLM as of 2026. |
| **IndicTrans2** (`ai4bharat/indictrans2-indic-en-1B`) | AI4Bharat translation model; Tamil → English specialized, no paraphrasing. |

Excluded by design: Anthropic Claude, OpenAI GPT (closed weights, off-strategy per [ADR 0007](0007-translation-backend.md)).

If a candidate cannot be served via NIM, we fetch it from HuggingFace and run it through any OpenAI-compatible serving layer (vLLM, TGI, Together's API) to keep the request shape consistent.

### Test set (10 verses)

Drawn deterministically (by `verse_id`) from the corpus, two verses per family, biased toward translation-difficult features:

| Family | Verses | Difficulty axes covered |
|---|---|---|
| Sangam Akam | AKAM-001, KURU-002 | Tinai-mode imagery, dhvani (suggested meaning), elliptic syntax |
| Sangam Puram | PURN-001, PURN-200 | Heroic register, named patrons, archaic compounds |
| Bhakti | THEV-100, DPRA-1500 | Theological terminology, deity epithets |
| Epic | SILA-001, MANI-100 | Narrative continuity across verses, named characters |
| Didactic | THIRU-100, KURAL-330 | Compressed aphoristic Tamil, multiple valid readings |

Each verse is run with three input variants per model:

1. **Bare:** classical Tamil only.
2. **+Wiktionary:** classical Tamil + Wiktionary definitions for 5–8 words from the verse.
3. **+Modern Tamil:** classical Tamil + a human-written modern Tamil paraphrase (provided by the project's expert annotator) + Wiktionary definitions.

Variants 1 and 2 measure raw model quality + dictionary anchoring. Variant 3 measures how much the context-stacking architecture from [ADR 0007](0007-translation-backend.md) lifts performance — i.e., *whether the architecture earns its complexity*.

For each (model × verse × variant) combination, the model is asked to produce both:
- A **modern Tamil paraphrase**.
- An **English rendering**.

Total cells: 5 models × 10 verses × 3 variants × 2 outputs = **300 model outputs**.

### Metrics

For each output, three scores. We report all three independently, not a single composite.

#### 1. Lexical anchoring (automated, 0–100)

Of the Wiktionary definitions provided in the input, what fraction does the output's vocabulary actually align with? Computed by stemming the output's content words, stemming the Wiktionary definitions' content words, and computing token-level F1.

Why: catches the most common LLM failure on classical Tamil — confidently introducing words that have no basis in the verse or the dictionary. A model can score high here without being good, but a low score reliably indicates hallucination.

#### 2. Semantic faithfulness (human, 0–5)

Per-verse rubric scored by the project's expert annotator (Vijayalakshmi):

- **5:** Captures the verse's literal meaning *and* its primary suggestion (dhvani / ullurai / theological context).
- **4:** Captures literal meaning, misses suggestion or misattributes a secondary meaning.
- **3:** Captures the gist; one or two material errors (e.g., wrong speaker, wrong landscape mode).
- **2:** Several material errors; a reader who couldn't read the original would be misled.
- **1:** Mostly invented or grossly incorrect.

Why: lexical anchoring is necessary but not sufficient. A model can name all the dictionary words and still misunderstand who is speaking, what landscape, or what the metaphor is.

#### 3. Fluency (human, 0–5)

Independent of meaning. Is the output natural-sounding modern Tamil / English?

- **5:** Reads like an educated native writer chose these words.
- **3:** Comprehensible but with stiffness or awkward phrasing.
- **1:** Word salad or grammar-broken.

Why: a faithful but unreadable draft fails the productivity goal. The annotator is supposed to be editing a draft, not rescuing a cipher.

### Statistical handling

5 models × 10 verses is a small sample. We do not claim statistical significance; we report each model's per-cell scores and show distributions. The decision criterion is dominance — if a model wins on all three metrics across most verses *and* in the +Modern Tamil variant (the production setting), that's the choice. Ties are broken by openness/availability (Nemotron > others) and Phase 5 alignment.

### Output

The eval produces:

1. A dataset (`evals/translation-comparison-2026.jsonl`) with every output, every score, every prompt, in line with the corpus's transparency policy.
2. A short paper / blog post on the methodology, results, and recommended `TRANSLATION_MODEL` setting.
3. A commit to this repo: `TRANSLATION_MODEL` Script Property in production is set to the winner; Roadmap Phase 2 references this artifact as evidence.

The dataset is published under `indic-corpora` on HuggingFace alongside the corpus, with provenance pointing back to this ADR.

## Why this much rigor for an internal tool

Three reasons.

First, the corpus's framing depends on credibility. A project that publishes "AI translations from Tamil literature" without a defensible model-choice methodology is indistinguishable from a hobby project. The eval is what makes the production choice non-arbitrary.

Second, the eval is a publishable artifact. There is no good public benchmark for "open-weight LLMs on classical Tamil." This eval, even at n=10, is more substantive than any prior published comparison we have seen. It's part of the corpus's research contribution, not just internal plumbing.

Third, Phase 5's fine-tune work needs a baseline. To claim a fine-tuned Nemotron is better than the base model on classical Tamil, we need to know how the base model does. This eval is that baseline.

## Alternatives considered

- **Skip the eval; just use Nemotron.** Faster, but defeats the project's framing. Rejected.
- **Use only automated metrics (BLEU, chrF, COMET).** Standard machine-translation metrics behave badly on free-form translations of classical Tamil to English where there is no canonical reference. Lexical anchoring is the closest automated proxy. Human rubrics fill the gap. Rejected pure-automated as misleading.
- **Use 100 verses instead of 10.** More robust, but the human scoring time scales linearly. 10 verses × 30 cells per verse = 300 outputs to score, which is already a substantial annotator commitment. We can extend to 100 if the n=10 result is ambiguous.
- **Crowdsource the human rubric.** Rejected — the test set is classical Tamil; meaningful judgments require fluency in classical Tamil + familiarity with the genres. The expert annotator (Vijayalakshmi) is the right rater. Inter-rater reliability is left as future work if the eval is extended.

## Consequences

- **Positive:** A defensible, transparent methodology for model choice. Production `TRANSLATION_MODEL` is set to the empirically-best winner, not a vendor preference.
- **Positive:** Publishable artifact (`evals/translation-comparison-2026.jsonl` + writeup) that adds to the corpus's research contribution.
- **Positive:** Establishes a baseline for measuring Phase 5 fine-tune improvement.
- **Negative:** Adds ~1 day of model-running engineering and ~3–4 hours of expert scoring time. Acceptable given the project's framing.
- **Negative:** n=10 is small. We accept that, report distributions honestly, and note that extension to n=100 is straightforward if the result is ambiguous.

## Implementation timeline

1. Phase 1 *ships* with `TRANSLATION_MODEL=nvidia/nemotron-3-nano-omni` as the default. The eval is concurrent or post-launch, not blocking.
2. Eval scripts: `scripts/run_translation_eval.py` runs each (model × verse × variant) combination, writes `evals/translation-comparison-2026.jsonl`.
3. Scoring: a structured Sheet template for the expert annotator to score outputs. ~3 days of focused review.
4. Writeup + decision: a follow-up commit updates `TRANSLATION_MODEL` in the production Script Property to the winner, references the eval artifact in `ROADMAP.md`.

## References

- [ADR 0007 — Translation backend](0007-translation-backend.md): the backend architecture this eval informs.
- [ADR 0005 — Nemotron 3 Nano Omni as Phase 5 target](0005-nemotron-3-nano-omni-as-phase-5-target.md): why Nemotron is the default starting candidate.
- [ADR 0002 — Soniox over Whisper for Tamil STT](0002-soniox-over-whisper-for-tamil-stt.md): the analogous ADR pattern for STT, which deferred its own ASR comparison to Phase 2.
