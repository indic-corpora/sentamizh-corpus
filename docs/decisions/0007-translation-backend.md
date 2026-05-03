# 0007 — NVIDIA NIM (Nemotron) for Phase 1 translation, behind a `/translate` proxy, with context-stacking from Modern Tamil and Wiktionary

- **Status:** Accepted
- **Date:** 2026-05-03

## Context

The Phase 1 annotator has fields for `modern_tamil` (a paraphrase of the verse in contemporary Tamil) and `english` (a free English rendering). For 10,393 verses across 9 source texts, the per-verse annotation budget is tight — even at 5 minutes per verse, the corpus is hundreds of hours of work, and these two translation fields are the most time-consuming parts of the annotation. The expert annotator (Vijayalakshmi) is fluent in classical Tamil, but typing out a complete paraphrase + English rendering for thousands of verses is the labor bottleneck, not the linguistic skill.

A "suggest translation" feature that drafts a starting paraphrase the annotator can edit (rather than start from a blank field) is a standard productivity move. Three constraints shape the choice:

1. **No proprietary lock-in.** The corpus's open-source ethos extends to the tools we build on top of it. Choosing a closed-weight API (Anthropic, OpenAI) would tie Phase 1 quality to a vendor whose pricing or availability we cannot control.
2. **Phase 5 alignment.** The roadmap targets fine-tuning [NVIDIA's Nemotron 3 Nano Omni](0005-nemotron-3-nano-omni-as-phase-5-target.md) on this corpus. If Phase 1 translation runs on the same model family, our prompts, our test set, and our quality intuitions transfer 1:1 to the Phase 5 fine-tune. With a different vendor's model, Phase 5 would be a cold start.
3. **Honest LLM quality on classical Tamil.** No frontier LLM — Claude, GPT-4o, Nemotron, DeepSeek, Llama — is *good* at classical Tamil. They're roughly equally mediocre. The question of which open model is best for classical Tamil specifically requires an empirical comparison, which is the subject of [ADR 0008](0008-open-model-eval-classical-tamil.md). This ADR commits to the architecture; the model choice is swappable.

## Decision

Phase 1 ships a **`/translate`** proxy endpoint on Apps Script that calls **NVIDIA NIM** (`integrate.api.nvidia.com`) with **Nemotron 3 Nano 30B-A3B** (`nvidia/nemotron-3-nano-30b-a3b`) as the default model — the text-only variant of the Nemotron 3 Nano family. The Omni multimodal variant (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`) is overkill for text translation; we reserve it for the Phase 5 voice/register fine-tune ([ADR 0005](0005-nemotron-3-nano-omni-as-phase-5-target.md)). The model identifier is read from a Script Property (`TRANSLATION_MODEL`) so swapping to a different model is a property change, not a code change.

The frontend renders a "Suggest translation" button on the `modern_tamil` and `english` fields. Tapping it POSTs to `/translate` with a payload that includes:

- `classical_tamil`: the verse being annotated.
- `modern_tamil` or `english` (whichever the annotator has already filled): used as additional context.
- `word_definitions`: a `{word: [definitions]}` map pre-fetched from Tamil Wiktionary for words in the verse (per [ADR 0006](0006-tamil-wiktionary-for-dictionary-lookup.md)).
- `target`: which field to generate (`modern_tamil` or `english`).

The script's prompt to NIM stacks all this context. The LLM is asked to translate **from** the most-LLM-friendly representation available — the annotator's modern Tamil paraphrase if she's filled it, otherwise the dictionary-anchored classical Tamil — rather than translate from raw classical Tamil where every model performs poorly.

The response is rendered as an italic light-grey draft in the textarea with an "AI-assisted draft — review before saving" badge. The draft is **not committed** to the corpus until the annotator edits it (any keystroke or dictation), at which point the draft becomes her text. Saves never write the un-edited draft.

## Why a proxy, not direct frontend → NIM

Per [ADR 0004 (proxy contract for pluggable backends)](0004-proxy-contract-for-pluggable-backends.md), our policy is that the annotator frontend talks only to Apps Script, never to third-party APIs. This:

- **Hides the API key.** `NVIDIA_API_KEY` lives in Script Properties, not in any client bundle.
- **Decouples vendor choice from the frontend.** When we swap to a different model — including Phase 5's self-hosted Nemotron fine-tune, or a self-hosted IndicTrans2, or DeepSeek, or anything else — only the script changes.
- **Centralizes telemetry.** Latency, success rate, and token cost per call are logged to the Sheet's `_telemetry` tab uniformly.
- **Lets us inject project-specific prompt logic** (the context-stacking pattern below) without leaking it into the client bundle.

## Why context-stacking is the architecture, not just the prompt

The translation feature's quality on classical Tamil is structurally limited by LLM pretraining — none of the candidates have meaningful classical Tamil exposure. The architecture's job is to route around that weakness, not pretend it doesn't exist. Two project-specific signals materially improve quality:

1. **The annotator's modern Tamil paraphrase.** If `modern_tamil` is already filled when the annotator clicks "Suggest English translation," the script's prompt translates from her modern Tamil — a register every model handles well — instead of from raw classical. This is a much easier task for the LLM and produces noticeably better English.
2. **Tamil Wiktionary definitions.** The frontend pre-fetches definitions for words in the verse on verse load (background, cached). When "Suggest translation" is clicked, those definitions are passed alongside the verse as `{word: [definitions]}` pairs. The script's prompt instructs the LLM to use these as authoritative — anchoring its interpretation in real dictionary data instead of guessing on rare classical words.

Together, these two stack. Suggesting English from `(classical Tamil + her modern Tamil paraphrase + 8 Wiktionary definitions)` is a substantially different prompt than suggesting English from `(classical Tamil)` alone, and produces meaningfully better drafts.

The annotator does not see this complexity — she sees a "Suggest translation" button. The architecture makes the button worth clicking.

## Alternatives considered

- **Anthropic Haiku or OpenAI GPT-4o-mini.** Strong models, cheap. Rejected on lock-in grounds: closed weights, no self-host path, no Phase 5 alignment.
- **Direct frontend → NIM call (skip the proxy).** Faster to ship by ~2 hours. Rejected for the reasons listed above (API key exposure, vendor coupling, no telemetry).
- **IndicTrans2 (AI4Bharat) only.** Purpose-built Indic translation, free, runs locally. Rejected as the *sole* backend because it's translation-only — it doesn't paraphrase to modern Tamil from classical Tamil, which is the harder of our two fields. Worth keeping in scope as a supplementary backend in Phase 2 if the eval shows it dominates on the English field.
- **No "suggest" feature at all.** Rejected because the annotation workload is the binding constraint on the project's Phase 1 timeline, and the AI draft pattern is well-suited to expert-edit workflows where the human is the final authority.
- **Auto-translate every verse on load (no button).** Rejected because cost grows with traffic regardless of whether the annotator wants the suggestion, and silent automation makes the AI draft easy to confuse with a real annotation.

## Consequences

- **Positive:** Phase 1 has a translation feature that's open-weights-aligned, vendor-swappable, and architecturally consistent with [ADR 0004](0004-proxy-contract-for-pluggable-backends.md).
- **Positive:** The context-stacking pattern (Wiktionary + Modern-Tamil-as-context) routes around the LLMs' weakness on classical Tamil, producing materially better drafts than a naive "translate this verse" prompt would.
- **Positive:** The Phase 5 Nemotron fine-tune ([ADR 0005](0005-nemotron-3-nano-omni-as-phase-5-target.md)) gets a head start: prompts, test set, and quality intuitions all carry over.
- **Negative:** NVIDIA NIM is a newer platform than OpenAI's API. Documentation is less polished, occasional service hiccups expected. Mitigated by the proxy contract — when NIM is down or the model is bad, swap `TRANSLATION_MODEL` and retry.
- **Negative:** Free NIM credits are bounded. Once they're consumed, paid tier is roughly $1–10 for the full 10K-verse pass. Not a blocker but worth budgeting.
- **Negative:** AI drafts that are wrong can anchor the annotator on a misinterpretation. Mitigated by the visual cue (italic, badge), the explicit "review before saving" framing, and the architectural rule that drafts are never committed without an edit.
- **Open question:** which open-weight model is actually best for classical Tamil. Resolved by [ADR 0008](0008-open-model-eval-classical-tamil.md).

## Implementation summary

- **Backend** (`annotator/google_apps_script.gs`):
  - New `handleTranslate(body)` function. POST `action=translate` is dispatched to it.
  - Reads `NVIDIA_API_KEY` and `TRANSLATION_MODEL` (default `nvidia/nemotron-3-nano-30b-a3b`) from Script Properties.
  - Builds an OpenAI-compatible chat completion request to `https://integrate.api.nvidia.com/v1/chat/completions`.
  - System prompt explicitly anchors the LLM in the supplied Wiktionary definitions and the annotator's modern Tamil paraphrase, in that order of trust.
  - Telemetry: logs latency, model, token cost estimate to the Sheet's `_telemetry` tab.
- **Frontend** (`annotator/index.html`):
  - "Suggest translation" button on `modern_tamil` and `english` fields.
  - On verse load, pre-fetch Wiktionary definitions for ~10 representative words from the verse, in the background, with per-word caching.
  - On Suggest click, POST `/translate` with the relevant context. Render result as italic light-grey draft. Badge: "AI-assisted draft — review before saving".
  - On user edit (keystroke, paste, dictation), commit the draft to the field as her text and clear the draft state.
- **Setup** (`annotator/SETUP.md`, `DEPLOY.md`):
  - Documents adding `NVIDIA_API_KEY` to Script Properties, where to obtain it (build.nvidia.com), and that `authorize()` should be re-run if the OAuth scope set was changed.

## References

- [ADR 0004 — Proxy contract for pluggable backends](0004-proxy-contract-for-pluggable-backends.md): the architectural pattern this ADR follows.
- [ADR 0005 — Nemotron 3 Nano Omni as Phase 5 target](0005-nemotron-3-nano-omni-as-phase-5-target.md): the Phase 5 alignment rationale.
- [ADR 0006 — Tamil Wiktionary for dictionary lookup](0006-tamil-wiktionary-for-dictionary-lookup.md): the definition source we pre-fetch and pass as context.
- [ADR 0008 — Open-model evaluation methodology for classical Tamil](0008-open-model-eval-classical-tamil.md): the empirical comparison that informs the eventual `TRANSLATION_MODEL` choice.
- [NVIDIA NIM API reference](https://docs.nvidia.com/nim/index.html).
- [Nemotron 3 Nano Omni announcement (April 28, 2026)](https://developer.nvidia.com/blog/nvidia-nemotron-3-nano-omni-powers-multimodal-agent-reasoning-in-a-single-efficient-open-model/).
