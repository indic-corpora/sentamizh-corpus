# 0003 — Manual annotation in Phase 1, not LLM-prefill

- **Status:** Accepted
- **Date:** 2026-04-24 (decision); recorded 2026-04-30

## Context

The corpus has 10,393 entries and a 32-field schema. Twenty-two of those fields are interpretive — `rasa_primary`, `dhvani_layer`, `themes`, `ullurai`, `karu`, `uri`, `philosophical_concept`, the storytelling seeds, etc. Most of those fields are currently null across the corpus; populating them is the single largest piece of work remaining.

Two approaches were considered:

1. **LLM-prefill, then human review.** Run an LLM (Claude/GPT) over each verse to draft all interpretive fields, then have a human scholar review and correct.
2. **Manual annotation by an expert, with optional LLM assistance later.** Build an annotation tool tuned for a single expert's workflow; let her annotate from scratch, in her own register, at her own pace.

The single Classical Tamil expert annotator working on this project is a domain expert, not a software engineer. Her time is the rate-limiting and most valuable resource. The question is which approach uses that resource best.

## Decision

Phase 1 is **manual annotation by the expert annotator, with no LLM prefill.** A custom mobile annotation tool (`annotator/`) was built around her workflow: voice dictation in Tamil, on-the-fly dictionary lookups, structured chip-style controls for the enum fields, automatic save-to-Sheets.

LLM-assisted pre-annotation is deferred to Phase 2, with the explicit constraint that any LLM annotations are clearly attributed via the `annotator` field and must be reviewed by an expert before being treated as authoritative.

## Alternatives considered

- **LLM-prefill then expert review.** Faster to first-pass results, but creates two problems for this annotator. First, anchoring: when a field is pre-filled with a plausible-sounding value, the reviewer's natural mode is to accept-with-tweaks rather than re-derive from the verse. The corpus's interpretive fields would then encode the LLM's assumptions, not the expert's, and that drift is hard to detect downstream. Second, the LLM would inevitably get some classical-Tamil readings wrong in subtle ways, and the cognitive cost of identifying *which* readings are wrong (vs just merely accepting the plausible ones) is higher than re-deriving from scratch.
- **Crowdsourcing to multiple annotators.** Not yet — Classical Tamil expertise is rare, and consistency across annotators requires the controlled vocabularies (rasa enum, thinai enum, etc.) to be locked in first. That's on the roadmap.
- **No annotation, just publish the source text.** The interpretive fields are what makes the corpus distinctive vs. existing digitized Tamil text resources. Publishing without them would replicate work others have already done.

## Consequences

- **Positive:** Annotations reflect the expert's judgment, not an LLM's. The corpus is honest about its provenance — every `annotator` field will say "expert" or, in Phase 2, "LLM (model X), reviewed by expert."
- **Positive:** The annotator UI is built around the expert's actual workflow (mobile, voice-first, chip-style enum picks, dictionary lookup). The tool was a real-world test of "how do you build an annotation tool for a single non-engineer expert" — a worthwhile design exercise on its own.
- **Negative:** Annotation throughput is much slower than LLM-prefill would be. The corpus's interpretive fields will be sparsely populated for some time.
- **Negative:** A few fields carry uniform extractor-applied default values (Bhakti `rasa_primary='Shanta'`, Bhakti `speaker_role='devotee'`, Sangam-Puram `speaker_role='bard'`). These were stamped during extraction, not by the expert. The annotator UI's `_is_annotated()` check currently treats those as annotated, which means the expert could overlook them. This is flagged on the roadmap; before Phase 2 LLM-assist runs, the placeholders need either clearing or an explicit "default" provenance tag.

## References

- `annotator/SETUP.md` — operational setup of the tool.
- `scripts/annotate_entries.py` — the LLM annotation pipeline that exists for Phase 2 use.
- ADR 0004 — proxy contract, which makes both manual and LLM annotation paths flow through the same data model.
