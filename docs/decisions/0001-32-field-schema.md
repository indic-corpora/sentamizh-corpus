# 0001 — 32-field schema with cross-cultural bridge layer

- **Status:** Accepted
- **Date:** 2026-04-10 (decision); recorded 2026-04-30

## Context

The Sentamizh Corpus is intended to serve multiple audiences at once: Tamil literary scholars who expect Tolkappiyam-era categories; AI/ML researchers who expect machine-readable schemas; and creators (writers, designers, content makers) who want the corpus to be legible without classical-Tamil expertise.

A purely traditional schema (Thinai, Akam/Puram, Karu/Uri, dhvani) is faithful to the source tradition but opaque to readers without classical-Tamil background. A purely modern schema (themes, mood tags, sentiment) is broadly legible but flattens what makes Sangam and Bhakti literature distinctive — the very structures that make the corpus interesting in the first place. Neither alone serves all three audiences.

## Decision

Adopt a four-layer schema with 32 fields. Each layer is independently optional at query time, so a consumer can use only the layers relevant to their work:

1. **Core layer** (10 fields): identification + raw text in three languages.
   `verse_id`, `source_text`, `layer`, `period`, `verse_number`, `classical_tamil`, `modern_tamil`, `english`, `source_url`, `difficulty`.

2. **Tamil-native layer** (10 fields): Tolkappiyam-aligned categories.
   `thinai`, `turai`, `akam_or_puram`, `karu`, `uri`, `ullurai`, `speaker_role`, `metre`, `pann`, `dhvani_layer`.

3. **Interpretive layer** (7 fields): rasa, themes, philosophical concepts, storytelling seeds.
   `rasa_primary`, `rasa_secondary`, `themes`, `philosophical_concept`, `cultural_context`, `storytelling_seed_narrative`, `storytelling_seed_emotional`.

4. **Cross-cultural bridge layer** (3 fields): cross-tradition mappings.
   `nayika_bheda`, `visual_imagery`, `emotional_valence` (Plutchik-mapped, with intensity).

Plus 2 metadata fields: `annotator`, `annotation_confidence`.

## Alternatives considered

- **22-field schema** (the original proposal in the early project brief). Rejected because it lacked `speaker_role`, `metre`, `pann`, `ullurai`, and the bridge layer entirely; insufficient for Sangam dramatic structure and inaccessible to readers without Tamil-language expertise.
- **Pure DCMI / Dublin Core schema.** Designed for general digital library metadata, with no literary-specific fields. Useful for cataloging; not useful for the kind of interpretive work this corpus is meant to support.
- **Single flat namespace with no layers.** Rejected because cross-field business rules (Akam poems must have thinai; pann is Bhakti-only; nayika_bheda doesn't apply to Didactic) become harder to express and validate when the schema isn't grouped.

## Consequences

- **Positive:** Each audience can use the corpus through its own lens without the other audiences' annotations being noise.
- **Positive:** Cross-field validation rules in `scripts/validate.py` map cleanly to layer boundaries (e.g., "thinai requires `layer = Sangam` and `akam_or_puram = Akam`").
- **Negative:** 32 fields is a substantial annotation burden. Phase 1 manual annotation focuses on the subset the annotator UI exposes; the remaining fields will be addressed in later phases via LLM-assistance + human review.
- **Open question:** The enum sets for `rasa_primary`, `thinai`, `nayika_bheda`, and `metre` reflect standard literary references but have not yet been independently reviewed by Tamil literary scholars. Locked-in vocabularies risk needing remapping after such review; this is on the roadmap as a Phase 1 deliverable.

## References

- Tolkappiyam, Porul Adhikaram (basis for the Tamil-native layer fields).
- Bharata Muni, Natya Shastra (rasa framework).
- Anandavardhana, *Dhvanyaloka* (dhvani layer).
- Plutchik, R. (1980). *A general psychoevolutionary theory of emotion.* (Cross-cultural bridge layer.)
- Per-field rationale lives as `description` properties on each field in [`schemas/sentamizh_schema.json`](../../schemas/sentamizh_schema.json).
