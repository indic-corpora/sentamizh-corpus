# 0006 — Tamil Wiktionary for Phase 1 dictionary lookup, with self-hosted UMTL on the Phase 2 roadmap

- **Status:** Accepted
- **Date:** 2026-05-02

## Context

The Phase 1 annotator's `/lookup` endpoint was originally designed to proxy [Agarathi](https://agarathi.com/api/dictionary), a Tamil dictionary API that proxies the University of Madras Tamil Lexicon (UMTL) and other dictionaries. Two issues surfaced during Phase 1 launch:

1. **Agarathi signup is non-functional at the time of launch.** The subscription form returns HTTP 500 on submit, and a captcha-step issue appears to block account creation. This may be a transient outage on their end, but it blocks the Phase 1 launch from proceeding.
2. **License compatibility.** Many readily-available Tamil dictionary digitizations are licensed CC BY-NC-ND (DSAL Tamil Lexicon at UChicago) or GPL-3.0 (linuxkathirvel/eng2tamildictionary). Both are incompatible with this corpus's Apache 2.0 license for redistribution. Public-domain UMTL scans exist on Internet Archive but require OCR and cleanup that is a multi-day effort, not a same-day patch.

The annotator's expert annotator (Vijayalakshmi) is a Classical-Tamil-fluent native speaker who can productively annotate without dictionary lookup, but the popup is a real UX convenience for words she wants quick clarification on, and removing it altogether would be a meaningful regression vs. the original design.

## Decision

Phase 1 launches with **Tamil Wiktionary** ([ta.wiktionary.org](https://ta.wiktionary.org/)) as the dictionary backend, queried at runtime through the Apps Script `/lookup` proxy. Implementation queries the MediaWiki `extracts` API with `explaintext=1` for clean plain-text definitions; no authentication required.

The `/lookup` endpoint's response shape (`{form, lemma, definitions[], source}`) is unchanged, so the frontend popup is unaffected. The `provider` field on the response now reads `"wiktionary"` instead of `"agarathi"`.

Phase 2 plans to add a **self-hosted UMTL** backend behind the same `/lookup` endpoint. The UMTL would be reconstructed from public-domain scans on Internet Archive, OCR'd with Tesseract Tamil, manually cleaned, and structured into a queryable JSON corpus published under the `indic-corpora` HuggingFace namespace. When the UMTL backend exists, the `/lookup` endpoint can route between Wiktionary and UMTL based on a query flag or fall back from one to the other when coverage gaps appear.

## Alternatives considered

- **Wait for Agarathi to recover.** Their 500 error may resolve on its own. Rejected for Phase 1 launch because the wait is open-ended and Phase 1 needs to ship now; Agarathi can be reintroduced as an alternative backend later if their service stabilizes.
- **DSAL/UChicago Tamil Lexicon** — comprehensive but CC BY-NC-ND. Cannot be redistributed in Apache 2.0 corpus. Rejected on license grounds.
- **GPL-3.0 community dictionaries** (e.g., linuxkathirvel/eng2tamildictionary). Rejected on license grounds.
- **Skip dictionary lookup entirely for Phase 1.** Rejected because the popup is a real UX feature; Wiktionary unblocks at low engineering cost.
- **Self-host UMTL OCR'd from public-domain Internet Archive scans** — the right long-term solution, but a multi-day engineering project. Deferred to Phase 2 (see Roadmap).

## Consequences

- **Positive:** Phase 1 ships with working dictionary lookup. No API key, no signup, no captcha. Tamil Wiktionary entries for classical terms (verified for `காமம்`) include citations from Kuruntokai and Tirukkural — exactly the corpus we are annotating against, which is a happy fit.
- **Positive:** The proxy contract from [ADR 0004](0004-proxy-contract-for-pluggable-backends.md) carries through cleanly. Replacing or adding a dictionary backend in Phase 2 is a server-side change; the frontend popup code is unaffected.
- **Negative:** Wiktionary's coverage of classical Tamil is community-edited and uneven. Some Sangam-era terms have rich entries; obscure ones may have stub entries or no entry at all. Vijayalakshmi will see "இந்த வார்த்தை அகராதியில் இல்லை" ("not in the dictionary") for words Wiktionary lacks.
- **Negative:** Wiktionary's data is CC BY-SA. We don't redistribute it (we query at runtime), so the license restriction doesn't propagate to this corpus's Apache 2.0 license. But any annotator workflow that copies Wiktionary content into the corpus directly would carry the CC BY-SA obligation; the annotator UI and the Sheets storage do not currently do this, but it's a constraint to remember.
- **Open question:** how Wiktionary's coverage actually compares to UMTL in practice for the kinds of words Vijayalakshmi looks up. Phase 2 will benchmark this empirically once the self-hosted UMTL backend exists.

## Phase 2 plan: self-hosted UMTL

Briefly so the Phase 2 work has a starting point. Detail will be expanded in a future ADR when the work begins.

1. Source data: [Tamil Lexicon scans on Internet Archive](https://archive.org/details/in.ernet.dli.2015.85194) (public domain, 1924–36 print edition).
2. Process: Tesseract Tamil OCR + manual cleanup + structuring into JSON entries. Scope: ~104,000 lemmas. Estimated effort: 1–2 weeks of focused work.
3. Distribution: publish the cleaned data as a separate dataset under `indic-corpora` on HuggingFace, with provenance to the Internet Archive scans.
4. Integration: add UMTL as a second backend behind the existing `/lookup` endpoint. Possibly query both Wiktionary and UMTL in parallel and merge results, or fall back from one to the other based on coverage.
5. Comparison artifact: publish a coverage and quality benchmark of UMTL vs Wiktionary for a sample of classical Tamil words, as a project blog post.

## References

- [Tamil Wiktionary](https://ta.wiktionary.org/)
- [MediaWiki API: action=query&prop=extracts](https://www.mediawiki.org/wiki/Extension:TextExtracts)
- [Tamil Lexicon at DSAL (CC BY-NC-ND)](https://dsal.uchicago.edu/dictionaries/tamil-lex/) — incompatible with our license but a useful reference for what UMTL coverage looks like.
- [Tamil Lexicon scans on Internet Archive (public domain)](https://archive.org/details/in.ernet.dli.2015.85194) — Phase 2 OCR source.
- [ADR 0004 — Proxy contract for pluggable backends](0004-proxy-contract-for-pluggable-backends.md): the architectural pattern that makes this swap a server-side change.
