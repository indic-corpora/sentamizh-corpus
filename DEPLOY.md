# Deployment

This project deploys to two surfaces, each on its own auto-deploy pipeline:

- **Frontend (`annotator/`)** → Netlify, auto-deployed on every push to `main`.
- **Backend (`annotator/google_apps_script.gs`)** → Google Apps Script via `clasp`, auto-deployed by GitHub Actions on every push to `main` that touches the backend.

After the one-time setup below, the iterative loop is just:

```
edit → git commit → git push → test on phone
```

Both URLs stay the same across deploys (Netlify reuses the site URL; clasp updates an existing deployment ID), so Mom never has to update her bookmark.

---

## One-time setup (~30 minutes total)

You'll do this once. Most of it is OAuth dialogs and copying IDs.

### Step 1 — Install local CLIs

```
npm install -g @google/clasp@2.4.2 netlify-cli
clasp login    # opens browser, sign in with the same Google account that owns the Apps Script
netlify login  # opens browser, sign in with your Netlify account
```

`clasp login` writes `~/.clasprc.json` — you'll need its contents in Step 4.

### Step 2 — Find your Apps Script `scriptId` and `deploymentId`

Open your Sheet → **Extensions → Apps Script**. In the editor:

- **scriptId**: click the gear icon (⚙️) on the left rail → Project settings → "Script ID". Long opaque string.
- **deploymentId**: click **Deploy → Manage deployments**. The active deployment has a "Deployment ID" field. Long string starting with `AKfy...`.

Paste the scriptId into `.clasp.json`:

```json
{
  "scriptId": "<paste-here>",
  "rootDir": "annotator"
}
```

Save the deploymentId locally (kept out of git):

```
echo "<paste-deploymentId-here>" > .clasp-deployment-id
```

### Step 3 — Verify clasp can talk to your Apps Script

From the project root:

```
clasp status
```

It should list `google_apps_script.gs` and `appsscript.json` as files that would be pushed. If it complains about manifest mismatches, see "Troubleshooting" below.

Then (carefully — this overwrites the script editor's copy with your local one):

```
clasp push --force
clasp deploy --deploymentId "$(cat .clasp-deployment-id)" --description "first clasp deploy"
```

Open the Web App URL on your phone and make sure it still works (mic / lookup / Sheet write). If yes, clasp is set up.

### Step 4 — Wire up GitHub → Netlify (frontend auto-deploy)

1. Push the repo to GitHub if you haven't already (`gh repo create sentamizh-corpus --public --source=. --push`).
2. Go to <https://app.netlify.com/start>, click **Import from Git → GitHub**, pick this repo.
3. Netlify reads `netlify.toml` and pre-fills the build settings (publish dir = `annotator/`, no build command). Click **Deploy site**.
4. Netlify gives you a URL like `https://sentamizh-corpus.netlify.app`. (You can rename it under Site settings → Change site name.)
5. Update `annotator/index.html` if needed so `CONFIG.APPS_SCRIPT_URL` still points to your Apps Script Web App URL — that doesn't change just because Netlify did.

After this, every `git push origin main` triggers a Netlify build. You'll see deploy status as a check on your commit and in the Netlify dashboard.

### Step 5 — Wire up GitHub Actions (backend auto-deploy)

GitHub needs two secrets: your clasp credentials, and your deployment ID.

1. Get the contents of your local `~/.clasprc.json`:
   ```
   cat ~/.clasprc.json
   ```
   Copy the entire output (it's a JSON blob).
2. In GitHub: repo → **Settings → Secrets and variables → Actions → New repository secret**.
3. Add two secrets:
   - **Name:** `CLASPRC_JSON`. **Value:** the JSON blob from step 1.
   - **Name:** `APPS_SCRIPT_DEPLOYMENT_ID`. **Value:** the deployment ID from Step 2.
4. Push a small change to `annotator/google_apps_script.gs` (or trigger the workflow manually from the Actions tab via "Run workflow"). Watch the Actions tab — the workflow should run, push, and deploy in under a minute.

If the workflow logs say `clasp status` succeeded but `clasp push` failed, you most likely have a manifest scope mismatch — see Troubleshooting.

---

## Iterative flow (after setup)

### Frontend changes (`annotator/index.html`, CSS, manifest, verse JSONs)

```
# edit
git add annotator/index.html
git commit -m "fix: pill spacing on small screens"
git push
# Netlify auto-deploys in ~30s; refresh on phone
```

### Backend changes (`annotator/google_apps_script.gs`)

```
# edit
git add annotator/google_apps_script.gs
git commit -m "feat: log retry-after on Soniox 429"
git push
# GitHub Actions auto-runs clasp push + clasp deploy in ~1 min
# Apps Script Web App URL unchanged; new code live
```

### Both at once

A single push that touches both files triggers both pipelines in parallel.

### Local fast-path (skip git)

When you're tweaking and just want to see the result immediately on your phone, without going through a commit:

```
make deploy-frontend     # netlify deploy --prod --dir=annotator
make deploy-backend      # clasp push + clasp deploy
make deploy              # both
```

Useful for "I'm in front of the phone and want to test this CSS change RIGHT NOW." Just remember to commit after — otherwise CI deploys revert your changes on the next push.

---

## Troubleshooting

**`clasp push` says "manifest mismatch" or "scope changes require new authorization."**
Apps Script's `appsscript.json` lists OAuth scopes. If the script's actual code requires a scope not listed in the manifest, push fails. The simplest fix: from the project root, `clasp clone <scriptId>` into a temporary directory, copy the resulting `appsscript.json` into `annotator/`, then `clasp push` again.

**Netlify build fails with "publish directory does not exist."**
`netlify.toml` says `publish = "annotator"`. Check that the `annotator/` folder is actually committed (`git ls-tree HEAD annotator/`). If not, `git add annotator && git commit && git push`.

**GitHub Actions: `clasp` fails with "Could not read API credentials."**
The `CLASPRC_JSON` secret is malformed or missing. Re-copy the entire output of `cat ~/.clasprc.json` (it's a single-line JSON blob; don't add quotes around it in the GitHub UI).

**`clasp deploy` creates a NEW deployment instead of updating the existing one.**
You forgot `--deploymentId` (or `APPS_SCRIPT_DEPLOYMENT_ID` is unset in GitHub Actions). The CLI silently creates a new versioned deployment if no ID is passed, which gives you a fresh URL — not what you want. Always pass `--deploymentId`.

**Mom's bookmark suddenly stops working after a deploy.**
You probably created a new Apps Script deployment (see above) and didn't update `CONFIG.APPS_SCRIPT_URL` in `annotator/index.html`. Easiest fix: in Apps Script editor, **Deploy → Manage deployments**, delete the new one, keep the original. The original URL goes back to working.

**Soniox or Agarathi key seems to have disappeared after `clasp push`.**
Don't worry — Script Properties live server-side and aren't part of the source code clasp manages. They survive every push and deploy. If they really did get cleared, re-add them at Apps Script editor → ⚙️ → Script Properties.

---

## Rollback

### Frontend

```
git revert <bad-commit>
git push
# Netlify deploys the revert in ~30s
```

Or instantly: Netlify dashboard → Deploys → click any prior deploy → "Publish deploy."

### Backend

`clasp deploy --deploymentId <id>` always points at the latest pushed code. To roll back:

```
git revert <bad-commit>
git push
# Actions re-pushes the previous version
```

For an instant rollback without git, in the Apps Script editor: **Deploy → Manage deployments → ✏️ → Version: pick an earlier version → Deploy.**

---

## What's still manual (and should stay that way)

- **Adding API keys.** `SONIOX_API_KEY` and `AGARATHI_API_KEY` live in Apps Script Script Properties, not in code. Set them once in Apps Script editor → ⚙️ → Script Properties; clasp doesn't touch them.
- **Connecting GitHub to Netlify.** One-time UI step. Once done, every push triggers a deploy.
- **Telling Mom about a new feature.** No automation can replace "hey, try the new save toast."
