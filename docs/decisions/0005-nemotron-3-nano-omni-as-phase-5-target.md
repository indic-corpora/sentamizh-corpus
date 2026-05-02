# 0005 — Nemotron 3 Nano Omni as Phase 5 fine-tuning target

- **Status:** Proposed
- **Date:** 2026-05-02

## Context

Phase 5 of the roadmap calls for "NeMo fine-tuning experiments using the corpus as training data" but does not name a specific base model. NVIDIA's release of [Nemotron 3 Nano Omni](https://developer.nvidia.com/blog/nvidia-nemotron-3-nano-omni-powers-multimodal-agent-reasoning-in-a-single-efficient-open-model/) on April 28, 2026 provides a concrete, well-suited target.

Nemotron 3 Nano Omni is a 30B-A3B mixture-of-experts multimodal model handling text, image, audio, and video natively in a single architecture. It is open-weights under the NVIDIA Nemotron Open Model License, and is distributed with full access to weights, training recipes, and FP8/NVFP4 quantization tooling. The announcement does not enumerate language coverage, and Tamil literary content is unlikely to be present in any general-purpose multimodal pretraining set — fine-tuning on the Sentamizh Corpus is the path to add that capability specifically.

## Decision

Phase 5 fine-tuning experiments will target Nemotron 3 Nano Omni. Fine-tune outputs will be published under the [`indic-corpora`](https://huggingface.co/indic-corpora) HuggingFace namespace alongside the corpus itself, with methodology and benchmarks documented.

## Alternatives considered

- **Whisper-large-v3 fine-tunes** ([vasista22/whisper-tamil-medium](https://huggingface.co/vasista22/whisper-tamil-medium) and similar). Already exist as community fine-tunes; useful as Phase 2 ASR comparison points but narrower in scope (audio-only, no multimodal reasoning), so a poorer fit for testing the corpus's full annotation depth.
- **Smaller open text-only models** (Llama 3.x, Qwen, Mistral). Would work for text-only fine-tuning but miss the audio modality that Phase 5's voice/register hypothesis requires.
- **Stay vendor-neutral and fine-tune multiple base models in parallel.** Defensible long-term, but Phase 5 needs a specific commitment to actually ship something. Multi-base experiments can come later; the first published fine-tune should be one well-chosen target.
- **AI4Bharat IndicConformer fine-tunes.** Well-suited for Indic ASR specifically, but ASR is the Phase 2 surface, not Phase 5. Phase 5 is about literary understanding, which is broader than transcription.

## Consequences

- **Positive:** NeMo ecosystem provides ready quantization tooling (the Phase 3 work) and serving via NIM. The pipeline from "fine-tune" → "quantize" → "serve" is documented end-to-end by the model's distributor.
- **Positive:** A concrete named target makes Phase 5 a shippable experiment rather than an open-ended one. Comparable benchmarks become possible.
- **Positive:** Naming the target now informs Phase 2's ASR comparison — testing whether Nemotron's audio modality handles Tamil at all gives us data before committing to it as the Phase 5 base.
- **Negative:** 30B-A3B requires substantial GPU resources for fine-tuning. Scoping work (which compute, what budget, what fine-tune approach — full / LoRA / QLoRA) is needed before commitment.
- **Open question:** whether Nemotron has any Tamil pretraining at all. The article does not enumerate languages. Phase 2's ASR comparison should produce empirical signal on this; if Tamil performance is at near-zero, the fine-tune effort and value are both larger than for a model with partial Tamil exposure.

## References

- [NVIDIA Developer Blog — *NVIDIA Nemotron 3 Nano Omni Powers Multimodal Agent Reasoning in a Single Efficient Open Model*](https://developer.nvidia.com/blog/nvidia-nemotron-3-nano-omni-powers-multimodal-agent-reasoning-in-a-single-efficient-open-model/) (April 28, 2026)
- [ADR 0001 — 32-field schema](0001-32-field-schema.md): the structure that the fine-tune learns from.
- [ADR 0002 — Soniox for Phase 1 STT](0002-soniox-over-whisper-for-tamil-stt.md): the Phase 1 choice this Phase 5 work eventually compares against.
- [ADR 0004 — Proxy contract for pluggable backends](0004-proxy-contract-for-pluggable-backends.md): the architectural seam that makes provider/model swaps clean.
- `ROADMAP.md` — Phase 2 (ASR comparison), Phase 3 (quantization), Phase 5 (fine-tuning).
