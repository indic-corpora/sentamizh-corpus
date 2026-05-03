# Sentamizh Annotator — Phase 1 Setup

This is a one-time setup. After it's done, Vijayalakshmi Prasad — the project's classical-Tamil expert annotator — opens a link on her phone and starts annotating. Her work flows into a Google Sheet you control. Audio dictation goes through Soniox (a speech-to-text service). Per-word dictionary lookups go through Tamil Wiktionary (no signup, free). The optional "Suggest translation" button calls NVIDIA NIM (Nemotron 3 Nano Omni) for an AI-assisted draft the annotator can edit before saving.

**Total time: about 25 minutes.**

You'll end up with:
- A Google Sheet that fills with annotations as she works.
- A telemetry tab showing latency, cost, and call counts so you can write data-grounded blog posts later.
- A public URL she can open on her phone.

---

## Step 1 — Create the Google Sheet

1. Go to <https://sheets.new>.
2. Rename it to **"Sentamizh Annotations"**.
3. The script will add tabs automatically — one per text she annotates, plus a `_telemetry` tab.

---

## Step 2 — Get a Soniox API key

Soniox provides the streaming speech-to-text for Tamil dictation. The choice of provider, the alternatives I considered, and the basis for the comparison are recorded in [docs/decisions/0002-soniox-over-whisper-for-tamil-stt.md](../docs/decisions/0002-soniox-over-whisper-for-tamil-stt.md). Pricing as of April 2026 is roughly **$0.10/hour of audio**. For an annotation effort of, say, 50 hours of dictation, that's ~$5 of API spend.

1. Go to <https://soniox.com> and sign up for an account.
2. Add a payment method. Set a low spending cap if you want a hard ceiling (~$20 is plenty).
3. From the dashboard, generate an API key. It'll start with `sk_…`. **Copy it.**

---

## Step 3 — (No dictionary signup needed)

Phase 1's dictionary lookup uses [Tamil Wiktionary](https://ta.wiktionary.org/) at runtime. No API key, no signup, no captcha. The Apps Script proxy queries Wiktionary's public MediaWiki API directly when Vijayalakshmi long-presses a word.

The choice and the Phase 2 plan to add a self-hosted UMTL backend are documented in [`docs/decisions/0006-tamil-wiktionary-for-dictionary-lookup.md`](../docs/decisions/0006-tamil-wiktionary-for-dictionary-lookup.md). If a previous version of this project used Agarathi, that integration has been retired; you don't need to subscribe to Agarathi.

---

## Step 4 — Add the backend script

1. In the Sheet, open **Extensions → Apps Script**. A new browser tab will open.
2. Delete the contents of the default `Code.gs` file.
3. Open `annotator/google_apps_script.gs` from this project, copy its entire contents, and paste it into the Apps Script editor.
4. Click the floppy-disk **Save** icon (or `Ctrl+S` / `⌘+S`). Name the project **"Sentamizh Annotator"**.

---

## Step 5 — Store API keys in Script Properties

In the Apps Script editor:

1. Click the gear icon (⚙️) on the left rail → **Project Settings**.
2. Scroll to **Script Properties** → click **Add script property**.
3. Add these properties:
   - **`SONIOX_API_KEY`**: your Soniox `sk_…` key.
   - **`NVIDIA_API_KEY`** *(optional, only needed if you want the "Suggest translation" feature)*: your NVIDIA NIM API key. Get one free at <https://build.nvidia.com> — sign in, click any model card (e.g. Nemotron), click **Get API key**, copy the `nvapi-…` value.
   - **`TRANSLATION_MODEL`** *(optional, defaults to `nvidia/nemotron-3-nano-omni`)*: any model identifier supported by NVIDIA NIM. Useful if you want to swap models without redeploying. The reasoning for the default and the eval methodology for picking a different one are recorded in [`docs/decisions/0007-translation-backend.md`](../docs/decisions/0007-translation-backend.md) and [`0008-open-model-eval-classical-tamil.md`](../docs/decisions/0008-open-model-eval-classical-tamil.md).
4. Click **Save script properties**.

API keys live server-side. Vijayalakshmi's phone never sees them — the script mints short-lived (10-minute) Soniox tokens on demand, calls NIM with the key in the `Authorization` header, and forwards Wiktionary requests through its own anonymous client. Dictionary lookups don't require any key.

---

## Step 6 — Deploy as a Web App

1. In the Apps Script editor, click **Deploy → New deployment** (top right).
2. Click the gear next to "Select type" → **Web app**.
3. Fill in:
   - **Description:** Sentamizh annotator backend (phase 1)
   - **Execute as:** Me (your Google account)
   - **Who has access:** **Anyone** ← important
4. Click **Deploy**.
5. The first time, Google asks you to authorise. Click **Authorize access**, pick your account, **Advanced** → **Go to Sentamizh Annotator (unsafe)** → **Allow**. ("Unsafe" just means Google hasn't reviewed your script — it's your own code.)
6. After deployment, copy the **Web app URL**. It looks like:
   ```
   https://script.google.com/macros/s/AKfy…/exec
   ```

---

## Step 7 — Plug the URL into the annotator

1. On your computer, open `annotator/index.html` in any text editor.
2. Find the line near the top of the script section:
   ```javascript
   APPS_SCRIPT_URL: '',
   ```
3. Paste your Web App URL inside the quotes:
   ```javascript
   APPS_SCRIPT_URL: 'https://script.google.com/macros/s/AKfy…/exec',
   ```
4. Save.

---

## Step 8 — Host the annotator

The `annotator/` folder needs to live on the web (over HTTPS — voice input requires it).

**Easiest option — Netlify Drop (no account needed):**

1. Go to <https://app.netlify.com/drop>.
2. **Drag the entire `annotator/` folder** onto the drop zone.
3. Wait a few seconds. You'll get a public URL like `https://radiant-puppy-12345.netlify.app`.
4. (Optional) Click **Claim** to keep editing later — creates a free Netlify account.
5. **That URL is what Vijayalakshmi opens on her phone.**

Alternatives if you already have GitHub or your own hosting: anything that serves static files over HTTPS works.

---

## Step 9 — Smoke test on your own phone first

1. Open the Netlify URL on your phone.
2. Tap **அகநானூறு** or any text.
3. Tap the 🎤 mic next to the modern Tamil field. Phone may ask for microphone permission — allow it. Speak in Tamil. The button pulses red while listening. Tap again to stop. Transcript should appear in the field.
4. In the verse text, long-press a word (e.g. கண்ணி). A 🔎 பொருள் pill appears above. Tap it. A dictionary popup should show definitions.
5. Open your Google Sheet. The first text's tab should now have a row. Open `_telemetry` — you'll see rows for each call you made.

If all three work, the system is ready for Vijayalakshmi.

---

## How comprehension help works (the new way)

There is no "Show meaning" button anymore. We removed it because Google Translate's classical Tamil quality was poor and gave anchoring suggestions she'd have to fight rather than work from.

Instead:

- **Long-press a word** in the verse text. A small **🔎 பொருள்** pill appears just above her finger. Tap it.
- The pill calls Agarathi, which queries the **University of Madras Tamil Lexicon** (compiled 1924–36, comprehensive for classical Tamil). She sees the actual lemma definition, not an AI guess.
- If the word is a compound she didn't split right, she selects a smaller chunk and tries again.
- If the word truly isn't in the dictionary, the popup says so honestly. She can move on.

The "Scholarly translation" card stays as a placeholder for now — most Sangam verses don't have a freely-licensed verse-by-verse English translation aligned to Project Madurai's numbering. As suitable reference translations are sourced (public-domain editions, or material under explicit permission from the translator), they'll fill that card.

---

## Telemetry — the `_telemetry` tab

Every API call (transcribe-token, lookup, annotation save) writes one row. Columns:

| | |
|---|---|
| `timestamp` | ISO time |
| `session_id` | Per-app-session random ID |
| `endpoint` | `/transcribe`, `/lookup`, `/annotation` |
| `provider` | `soniox`, `agarathi`, `sheets` |
| `status` | `success`, `error`, `auth_failed` |
| `latency_ms` | Inner call time (proxy round-trip excluded) |
| `input_chars`, `output_chars` | For lookups and transcripts |
| `audio_seconds` | For STT |
| `cost_estimate_usd` | Computed at log-write time using current pricing |
| `verse_id` | Which verse triggered the call |
| `extra_json` | Anything else worth recording |

This is where your blog-post graphs come from. Don't delete it.

---

## Reviewing her work

Each text gets its own tab in the Sheet. Each row is one verse_id. You can:
- Sort by `_updated_at` to see her latest work.
- Edit cells directly to fix typos (next time she opens that verse, she'll see your edit).
- Delete a row to "un-annotate" a verse.

When you want to fold annotations back into the canonical corpus JSON, that's a separate Python script we'll build later — not in Phase 1. For now the Sheet is canonical.

---

## Troubleshooting

**Mic button does nothing or shows "Soniox SDK not loaded".**
The page must be served over HTTPS (Netlify gives you that). On `file://` or insecure HTTP it won't work. Also confirm the `<script type="module">` block at the top of `index.html` is intact.

**Mic shows "Could not get STT key".**
Either `SONIOX_API_KEY` isn't set in Apps Script Script Properties, or the deployment isn't set to "Anyone" access. Check Step 5 and Step 6.

**Dictionary popup says "அகராதி அணுக முடியவில்லை" (couldn't reach dictionary).**
Tamil Wiktionary's API may be temporarily unreachable or rate-limited. Try again in a few minutes; usage is unauthenticated and free, so persistent errors usually indicate a transient network or Wikimedia issue. If a specific word reliably returns "not in dictionary," it may simply not have a Tamil Wiktionary entry.

**The Sheet isn't updating.**
- Confirm the deployment is set to **Anyone** access (Step 6).
- Confirm the URL ends in `/exec` (not `/dev`).
- If you used **New deployment** instead of editing the existing one, you got a fresh URL — update `CONFIG.APPS_SCRIPT_URL` in `index.html`.

**I updated `google_apps_script.gs` — do I need a new URL?**
No, as long as you redeploy via the same deployment. **Deploy → Manage deployments → ✏️ → Version: "New version" → Deploy.** URL stays the same. Use **New deployment** only when you actually want a fresh URL.

**She tapped the mic but the transcript came out wrong.**
Soniox is the best free-tier-comparable Tamil STT but isn't perfect — proper nouns, archaic vocabulary in spoken form, and noisy environments push errors up. She can edit the textarea after dictating, or skip the field.

**She's offline / no internet.**
Annotations queue in `localStorage` and sync when online. Voice and dictionary lookup require internet (audio streams to Soniox, dictionary calls hit Agarathi).

---

## Automating the deploy loop

After this manual run-through is working, you can switch to "edit → push → auto-deploy" by following [DEPLOY.md](../DEPLOY.md). It connects the GitHub repo to Netlify (frontend) and adds a small GitHub Actions workflow that runs `clasp push` + `clasp deploy` (backend). Both URLs stay the same; Vijayalakshmi's bookmark is unaffected.

## What's next (Phase 2 and beyond)

This is intentionally Phase 1. Things deferred for later phases:

- **Self-host IndicConformer ASR.** Replace Soniox with an open-source Indic-language model on your own GPU. Same `transcribe-token` endpoint shape; we'd swap the proxy logic. This becomes the next major blog post.
- **Sandhi splitting for compounds.** Open-Tamil's rule-based splitter ported to JavaScript so a single long-press of `கார்நறுங்கொன்றை` resolves to three sub-word lookups automatically.
- **LLM lemma fallback.** When the rule-based lookup misses, Gemini Flash (or self-hosted Llama/Qwen) suggests a lemma and we re-query Agarathi.
- **Reference translation ingestion.** As public-domain or licensed translations become available, populate `verse.reference_translation` in the corpus JSON and the green card lights up.
- **Merge-back script.** Pull annotations from Sheets → validate against schema → overlay onto canonical corpus JSON.

Each of those is a self-contained next chapter. Phase 1 ships a working tool first; everything else builds on top.
