# 0004 — Proxy contract for pluggable backends

- **Status:** Accepted
- **Date:** 2026-04-26 (decision); recorded 2026-04-30

## Context

The Phase 1 annotator currently calls Soniox for STT and Agarathi for dictionary lookup. Both are commercial services. The roadmap (Phase 2 onward) anticipates swapping in self-hosted alternatives — IndicConformer for ASR, possibly Open-Tamil + a self-hosted dictionary for lookup — partly to reduce per-use cost at scale, and partly to demonstrate the project's roadmap of self-hosted Indic AI.

If the frontend hard-codes Soniox URLs, Soniox response shapes, and Agarathi response shapes, every backend swap means a frontend rewrite. That is the opposite of what we want — backend evolution should not affect the annotator UI or the annotator's workflow.

## Decision

Define a small set of stable proxy endpoints between the frontend (`annotator/index.html`) and the backend (`annotator/google_apps_script.gs`). The frontend never speaks directly to a vendor API; it always speaks to the proxy. Each response includes a `provider` field that tells the *log* which backend served the call but is opaque to the frontend.

The contract:

| Endpoint | Method | Request | Response |
|---|---|---|---|
| `/transcribe` (key) | POST `{action: "transcribe-token", session_id, expires_in_seconds}` | `{api_key, expires_at, provider, latency_ms}` |
| `/lookup` | POST `{action: "lookup", text}` | `{entries: [{form, lemma, definitions[], source}], provider, latency_ms}` |
| `/annotation` | POST `{verse_id, source_text, ...fields}` | `{ok: bool, _updated_at}` |
| `/annotations` | GET `?text=<corpus_id>` | `{verse_id: {fields}}` |
| `/log` | POST `{action: "log", endpoint, provider, status, latency_ms, ...}` | `{ok: bool}` |

The `provider` field is the load-bearing element. Replacing Soniox with self-hosted IndicConformer means changing the Apps Script implementation of `/transcribe` (or moving the proxy off Apps Script entirely, behind the same URL); the frontend doesn't change. The telemetry log records *which* provider served each call, so phase-comparison analysis (Phase 1 Soniox latency/cost vs Phase 2 IndicConformer latency/cost) becomes a SQL-over-Sheets query rather than an A/B retrofit.

## Alternatives considered

- **Direct calls from frontend to vendor APIs.** Simplest to build initially, but locks the frontend to a specific vendor's request/response shape and exposes API keys to the public-facing page. Rejected for both reasons.
- **A single `/api` endpoint with a dispatch field.** Considered, but ergonomically clumsy compared to one endpoint per concern. The current shape (`/transcribe`, `/lookup`, etc.) maps each call to its semantic meaning rather than to its dispatch implementation.
- **Versioning the contract from day one (`/v1/transcribe`).** Rejected as premature for a single-tenant Phase 1 system. Versioning is added if/when the contract starts being consumed by code outside this repository.

## Consequences

- **Positive:** Backend evolution is invisible to the annotator and to the annotator's workflow. Provider swaps are a server-side change.
- **Positive:** API keys live in Apps Script Script Properties — never in the public frontend.
- **Positive:** The telemetry log captures provider identity per call, which is the foundation for Phase 2's empirical comparison of providers.
- **Negative:** Adds a server-side hop for every call (`browser → Apps Script → vendor`). Apps Script latency adds ~100-300ms vs direct vendor calls. For Phase 1 dictation, that's negligible (the user is talking, not waiting); for high-volume bulk processing, the same indirection would matter more.
- **Mitigation for the negative:** If/when latency becomes the constraint, the proxy can be reimplemented in a serverless function (Cloud Run, Vercel, etc.) closer to the vendor without touching the frontend. The contract is what's load-bearing; the proxy implementation is replaceable.

## References

- `annotator/google_apps_script.gs` — current proxy implementation.
- `annotator/index.html` — frontend that consumes the contract.
- ADR 0002 — Soniox choice, which depends on this contract being in place.
- ADR 0003 — manual-annotation choice, which routes through the same `/annotation` endpoint as Phase 2 LLM-assist will.
