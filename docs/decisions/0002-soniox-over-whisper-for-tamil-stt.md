# 0002 — Soniox for Phase 1 Tamil dictation

- **Status:** Accepted
- **Date:** 2026-04-26 (decision); recorded 2026-04-30

## Context

The Phase 1 annotator (`annotator/`) needs streaming speech-to-text for Tamil dictation by a single expert annotator working on a mobile device. The full Phase 1 annotation effort is on the order of tens of hours of audio. The annotator works in classical-Tamil literary registers (with code-switching to modern Tamil and English), often in non-studio environments.

The candidate STT options considered for Phase 1 fall into three groups:

1. **Browser-native `SpeechRecognition`** — free, but its Tamil support varies by browser/OS and the API offers no SLA, no audio retention guarantees, and no quality guarantees. Earlier prototypes used this and the dictation quality on classical Tamil was consistently poor.
2. **OpenAI Whisper (hosted or self-hosted)** — open weights, batch-mode rather than streaming, well-supported. Whisper-large-v3 has reasonable Tamil performance on conversational benchmarks, but the relevant question for this project is its accuracy on classical-Tamil literary registers, which is a different distribution.
3. **Soniox real-time STT (commercial)** — streaming WebSocket API, multilingual, ~$0.10/hour audio. Soniox publicly claims strong Tamil performance.
4. **Self-hosted IndicConformer (AI4Bharat)** — open weights, Indic-specialized. Requires GPU infrastructure to serve at low latency.

## Decision

Use **Soniox** for Phase 1 dictation. The frontend talks to Soniox via WebSocket using a short-lived temporary key minted server-side by the Apps Script proxy.

The proxy contract (see [ADR 0004](0004-proxy-contract-for-pluggable-backends.md)) is designed so the STT provider can be swapped without changing the frontend. Phase 2 will evaluate self-hosted IndicConformer behind the same `/transcribe` endpoint.

## Alternatives considered

- **Browser-native `SpeechRecognition`.** Rejected based on prototype-stage observations: noticeably weaker on classical-Tamil dictation than the alternatives, and no telemetry/quality controls available. Free, but the time cost of correcting transcription errors outweighs the savings at the volumes Phase 1 needs.
- **Whisper (hosted via OpenAI / via a hosted provider).** Whisper is a competent general-purpose ASR; its Tamil training data is a portion of its multilingual mix, optimized for conversational rather than literary speech. We did not run a formal benchmark against Soniox on classical-Tamil dictation; the choice is based on Soniox's published Tamil-specific claims plus prototype observation. **A rigorous head-to-head benchmark on classical-Tamil dictation has not yet been run; this is on the Phase 2 roadmap.**
- **Self-hosted IndicConformer.** Strongest fit on paper for Indic languages, but requires a GPU host, model serving infrastructure, and operational overhead that Phase 1 doesn't justify. Deferred to Phase 2 where the same proxy contract lets us swap it in behind `/transcribe` without frontend changes.

## Consequences

- **Positive:** Streaming dictation works on day one; pricing scales linearly with use; mobile-friendly.
- **Positive:** The temporary-key pattern keeps the Soniox API key server-side; the public annotator URL never sees it.
- **Negative:** A commercial vendor in the Phase 1 critical path. If Soniox changes pricing, deprecates the model, or has reliability issues, annotation work is affected.
- **Negative:** Provider-comparison evidence is informal at this stage. The published numbers and the prototype observations led to a defensible Phase 1 choice, but the claim "Soniox is more accurate than Whisper for classical-Tamil dictation" is not yet backed by a benchmark from this project. This ADR is honest about that gap.
- **Mitigation:** The proxy contract (ADR 0004) is the load-bearing design decision that makes the Soniox choice reversible. Phase 2 benchmarking will close the evidence gap.

## References

- Soniox docs: https://soniox.com/docs/stt — model list, languages, real-time API.
- AI4Bharat IndicConformer: https://github.com/AI4Bharat/NeMo
- OpenAI Whisper: https://github.com/openai/whisper
- ADR 0004 — proxy contract, which makes this choice swappable.
