# Contributing to the Sentamizh Corpus

Thank you for considering a contribution. The corpus benefits enormously from expert review and from people closer to the source material than the project lead. The following describes how to help.

## What kinds of contributions are most useful

1. **Verse corrections.** Errors in `classical_tamil`, modern paraphrase, or English translation. Open an issue with the `verse_id` and the proposed change. Cite a published source if possible.
2. **Annotation review.** Disagreements with `rasa_primary`, `thinai`, `dhvani_layer`, etc. The schema's enum sets have not yet been independently reviewed; expert pushback is especially welcome.
3. **Missing verses.** Several verses are missing from the corpus today (see the "Known issues" section in [`CHANGELOG.md`](CHANGELOG.md)). Targeted PRs that supply these verses, with source URLs, are welcome.
4. **Schema improvements.** Field definitions, additional layers, or additional constraints. Substantial schema changes should start as an Architecture Decision Record (ADR) under [`docs/decisions/`](docs/decisions/) so the rationale is captured for future readers.
5. **Source extension.** Texts outside the current 9 (Naladiyar, Pazhamozhi, future Sanskrit/Hindi material). See [`ROADMAP.md`](ROADMAP.md) for current priorities.
6. **Tooling improvements.** Extractors, the validator, the annotator UI, the deployment pipeline. PRs welcome.

## How to file an issue

- For a single verse correction: title `[verse_id] short description`, body explains the proposed change with a source.
- For a schema change: title `[schema] short description`, body explains the motivation. If accepted, the change will be recorded as an ADR.
- For a question or open-ended discussion: use GitHub Discussions if available, otherwise open an issue tagged `discussion`.

## How to submit a pull request

- Fork the repo and create a branch named after the change (`fix/kuru-204`, `add/naladiyar`, `schema/ullurai-required-for-akam`, etc.).
- Run `python3 scripts/validate.py data/processed/` before committing. Validation must pass.
- One PR per logical change.
- Reference the related issue in the PR description.
- For changes affecting the dataset (verse content, annotations, schema), include a brief note in the PR description explaining what downstream users should know.

## What to do when you disagree with the project lead

The project is small and opinionated. Disagreement is welcome and is best handled in writing — open an issue with your reasoning. Substantive disagreements that affect the schema or annotation methodology should result in an ADR (whether the outcome is "we changed our mind" or "we kept the original, here's why").

## Code of conduct

By participating, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md). Treating contributors with respect — including the maintainers and contributors of the upstream resources this project builds on (Project Madurai, Tamil Virtual Academy, Vaidehi Herbert's translations, PaaPeyarchi, and others) — is non-negotiable.
