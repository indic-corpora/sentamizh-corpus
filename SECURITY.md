# Security policy

The Sentamizh Corpus is a research dataset and a small annotation tool. The plausible security concerns are limited but real:

- Bugs in the annotator (`annotator/`) that could leak Soniox or Agarathi API keys, or expose someone's Google Sheet to unintended readers.
- Bugs in the Apps Script proxy (`annotator/google_apps_script.gs`) that could be misused to call the upstream APIs in ways the operator did not intend.
- Issues in the deployment configuration (`netlify.toml`, `.github/workflows/deploy-backend.yml`) that could expose secrets through CI logs.

If you find one of these, please report it privately rather than opening a public issue.

## How to report

- Open a private security advisory on GitHub:
  `https://github.com/indic-corpora/sentamizh-corpus/security/advisories/new`
- Or email: prasadrevathi.2021@gmail.com

Please include enough detail to reproduce the issue, plus the version of the project (commit SHA) where you observed it.

## What to expect

The maintainer will acknowledge reports within 5 working days. As a one-person project with no SLA, no commitments beyond that are offered. Fixes will be prioritized based on impact and reproducibility.

## What is *not* in scope for security reports

- Disagreements about the corpus's annotations or interpretive choices. Those belong in regular issues or in a Code of Conduct conversation, not in security reports.
- Concerns about whether a third-party service (Soniox, Agarathi, Google Apps Script) handles your data the way you expect. Those should go to the third-party.
- Generic dependency-version concerns where there is no demonstrated exploit path for this project specifically.
