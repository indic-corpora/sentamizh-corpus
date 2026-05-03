# Deployment

This project deploys to two surfaces, each on its own auto-deploy pipeline:

- **Frontend (`annotator/`)** → Netlify, auto-deployed on every push to `main`.
- **Backend (`annotator/google_apps_script.gs`)** → Google Apps Script via `clasp`, auto-deployed by GitHub Actions on every push to `main` that touches the backend.

After the one-time setup below, the iterative loop is just:

```
edit → git commit → git push → test on phone
```

Both URLs stay the same across deploys (Netlify reuses the site URL; clasp updates an existing deployment ID), so Vijayalakshmi never has to update her bookmark.

---

## One-time setup (~30 minutes total)

You'll do this once. Most of it is OAuth dialogs and copying IDs.

### Step 1 — Install local CLIs

```
npm install -g @google/clasp@3.3.0 netlify-cli
clasp login    # opens browser, sign in with the same Google account that owns the Apps Script
netlify login  # opens browser, sign in with your Netlify account
```

`clasp login` writes `~/.clasprc.json` — you'll need its contents in Step 4.

> **Pin the clasp major version.** clasp 3.x split `deploy` into `create-deployment` and `redeploy`; the GitHub Actions workflow depends on the 3.x command shape. If you bump to 4.x or beyond, re-verify the workflow's `clasp version` and `clasp redeploy` calls before merging.

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
VERSION=$(clasp version "first clasp deploy" | grep -oE '[0-9]+' | tail -n 1)
clasp redeploy "$(cat .clasp-deployment-id)" -V "$VERSION" -d "first clasp deploy"
```

Open the Web App URL on your phone and make sure it still works (mic / lookup / Sheet write). If yes, clasp is set up.

> **Why two steps (`clasp version` + `clasp redeploy -V`) instead of one `clasp deploy`?**
> Letting clasp infer the version on a redeploy is the root cause of clasp issue #63 — the inferred-version path can silently shadow into a fresh deployment, which gives you a new `/exec` URL and breaks bookmarks. Creating the version explicitly and binding it with `-V` avoids that.

#### One-time OAuth consent (this is the step that always trips us up)

`clasp push` uploads code. `clasp deploy` / `clasp redeploy` make it live. **Neither of them prompts for OAuth consent.** Consent only happens when a function runs from the editor with a logged-in user. The web app runs as `USER_DEPLOYING` (the account whose `~/.clasprc.json` we used), and any scope `USER_DEPLOYING` hasn't consented to throws a runtime error like:

```
Exception: You do not have permission to call UrlFetchApp.fetch.
Required permissions: https://www.googleapis.com/auth/script.external_request
```

So after the first push, run the `authorize()` helper once:

1. Apps Script editor → in the function dropdown at the top of the editor, select **`authorize`**.
2. Click **Run**.
3. Apps Script shows a "Authorization required" dialog → click **Review permissions** → pick the deploying Google account → click **Allow**.
4. The function runs (its only job is to touch every scoped API to trigger consent on each one). You'll see a success log; the function itself returns nothing.

Re-run `authorize()` whenever you change the OAuth scopes in `annotator/appsscript.json` — the consent grant covers only the scopes consented to at run time, so adding a new scope without re-consenting will fail at runtime in production.

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
3. Add three secrets:
   - **Name:** `CLASPRC_JSON`. **Value:** the JSON blob from step 1.
   - **Name:** `APPS_SCRIPT_DEPLOYMENT_ID`. **Value:** the deployment ID from Step 2.
   - **Name:** `WEB_APP_URL`. **Value:** the live `/exec` URL from Step 3 (e.g. `https://script.google.com/macros/s/AKfy.../exec`). This is optional but strongly recommended — the workflow uses it to probe the live deployment after each redeploy and fail the build if Apps Script silently reset the deployment's access setting (a known quirk that has bitten this project multiple times). Without this secret, you find out access reverted only when the annotator's popover stops working.
4. Push a small change to `annotator/google_apps_script.gs` (or trigger the workflow manually from the Actions tab via "Run workflow"). Watch the Actions tab — the workflow should run, push, deploy, and probe in under a minute.

If the workflow logs say `clasp status` succeeded but `clasp push` failed, you most likely have a manifest scope mismatch — see Troubleshooting.

### Step 6 — (Conditional) OAuth client publishing status

**Skip this step if you used `clasp login` without `--creds`.** clasp's default OAuth client is owned by Google and is already in "In production" publishing status, so refresh tokens minted from it do not expire on the 7-day Testing clock. For Phase 1 hobby-scale use this is sufficient.

You only need to revisit this section if either of the following happens:

1. **CI starts failing weekly with `invalid_grant` or `Token has been expired or revoked`.** This means the refresh token expired on a 7-day cycle, which means you're using a custom OAuth client in Testing mode. The fix:
   1. Open <https://console.cloud.google.com/apis/credentials/consent>.
   2. Make sure the project at the top is the one whose OAuth client you used to log into clasp.
   3. Under **Publishing status**, click **Publish app**, confirm. Status flips to **In production**.
   4. Run `clasp logout && clasp login` once locally to mint a fresh, long-lived refresh token.
   5. Re-set the `CLASPRC_JSON` GitHub secret with the new `~/.clasprc.json`.

2. **You want to use a project-owned OAuth client** — for example, to escape clasp's shared default client because it's hitting rate limits (unlikely at Phase 1 scale), or because you want to use the Apps Script REST API directly:
   1. Cloud Console → **APIs & Services → Credentials → Create credentials → OAuth client ID → Desktop app**.
   2. Download the JSON. Save as `~/clasp-oauth.json` (anywhere — the path is just for `clasp login`).
   3. `clasp logout && clasp login --creds ~/clasp-oauth.json`.
   4. Re-paste the resulting `~/.clasprc.json` into the `CLASPRC_JSON` GitHub secret.
   5. Then publish the OAuth client per case (1) above so its refresh tokens don't expire weekly.

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
# GitHub Actions auto-runs clasp push + clasp version + clasp redeploy in ~1 min
# Apps Script Web App URL unchanged; new code live
```

### Both at once

A single push that touches both files triggers both pipelines in parallel.

### Local fast-path (skip git)

When you're tweaking and just want to see the result immediately on your phone, without going through a commit:

```
make deploy-frontend     # netlify deploy --prod --dir=annotator
make deploy-backend      # clasp push + clasp version + clasp redeploy
make deploy              # both
```

Useful for "I'm in front of the phone and want to test this CSS change RIGHT NOW." Just remember to commit after — otherwise CI deploys revert your changes on the next push.

---

## Troubleshooting

**`clasp push` says "manifest mismatch" or "scope changes require new authorization."**
Apps Script's `appsscript.json` lists OAuth scopes. If the script's actual code requires a scope not listed in the manifest, push fails. The simplest fix: from the project root, `clasp clone <scriptId>` into a temporary directory, copy the resulting `appsscript.json` into `annotator/`, then `clasp push` again.

**Netlify build fails with "publish directory does not exist."**
`netlify.toml` says `publish = "annotator"`. Check that the `annotator/` folder is actually committed (`git ls-tree HEAD annotator/`). If not, `git add annotator && git commit && git push`.

**Netlify deploy fails with an empty "Loading" log and no error output.**
The build command runs `python3 scripts/build_annotator_data.py` but Netlify's build image doesn't have `python3` on PATH unless you tell it to. `netlify.toml`'s `[build.environment] PYTHON_VERSION = "3.11"` block fixes this — without it, the build dies before producing any log lines. If the block is present and you still see this, bump to a different supported Python version (Netlify supports 3.8 through 3.11 currently).

**GitHub Actions: `clasp` fails with "Could not read API credentials."**
The `CLASPRC_JSON` secret is malformed or missing. Re-copy the entire output of `cat ~/.clasprc.json` (it's a single-line JSON blob; don't add quotes around it in the GitHub UI).

**`clasp redeploy` created a NEW deployment instead of updating the existing one.**
This is clasp issue #63 and it happens when the version number isn't pinned explicitly. Always create the version first and pass it via `-V`:

```
clasp push --force
VERSION=$(clasp version "describe this deploy" | grep -oE '[0-9]+' | tail -n 1)
clasp redeploy "$DEPLOYMENT_ID" -V "$VERSION" -d "describe this deploy"
```

The GitHub Actions workflow already does this (see `.github/workflows/deploy-backend.yml`). If you're deploying from your laptop with `make deploy-backend`, the Makefile does it too. The trap is `clasp deploy --deploymentId <id>` without `-V` — that path can shadow into a fresh deployment under some Apps Script project states.

**Cleaning up after a duplicate deployment.**
If a duplicate has already been created (you see two entries in **Deploy → Manage deployments**, or `clasp deployments` shows more than one):

```
clasp deployments
# Note the deployment IDs and descriptions. The original was created at setup
# time with the description you wrote in Step 3 ("first clasp deploy").
# Anything dated later is a duplicate.

clasp undeploy <duplicate-deployment-id>
# Repeat for each duplicate. Confirm only the original remains:
clasp deployments
```

Then verify the GitHub secret `APPS_SCRIPT_DEPLOYMENT_ID` matches the surviving deployment ID. If it doesn't, update the secret. From then on, every CI run updates this same deployment — the URL stays stable.

After cleanup, the surviving deployment may still be in a corrupted state where its "Who has access" reads as something other than "Anyone" — open it in **Manage deployments**, edit, set **Who has access** to **Anyone**, and click **Deploy**. This is a one-time UI fix; the manifest guard in CI ensures it doesn't drift again.

**Vijayalakshmi's bookmark suddenly stops working after a deploy.**
Most likely a duplicate deployment was created and the live `/exec` URL got reassigned (see above). Run `clasp deployments`, undeploy the duplicate, and confirm the surviving deployment's URL matches `CONFIG.APPS_SCRIPT_URL` in `annotator/index.html`.

**Lookup or transcription fails with `You do not have permission to call UrlFetchApp.fetch` (or any other scope).**
The deploying user hasn't consented to that scope yet. `clasp push` and `clasp deploy` don't trigger OAuth consent — only running a function from the editor does. Open the Apps Script editor, select **`authorize`** from the function dropdown, click **Run**, grant permissions when prompted. The error stops immediately for all subsequent web app calls. Re-run `authorize()` any time you add a new scope to `annotator/appsscript.json`.

**The `Guard the web app access setting` step in CI fails.**
Someone edited `annotator/appsscript.json` and dropped or changed the `webapp.access` or `webapp.executeAs` field. The guard fails fast so we don't ship a deploy that would silently revert the live deployment to "Only myself" and break access for annotators. Restore the manifest:

```json
"webapp": {
  "executeAs": "USER_DEPLOYING",
  "access": "ANYONE"
}
```

Commit and push. The guard passes and the deploy proceeds.

**Soniox or NVIDIA API key seems to have disappeared after `clasp push`.**
Don't worry — Script Properties live server-side and aren't part of the source code clasp manages. They survive every push and deploy. If they really did get cleared, re-add them at Apps Script editor → ⚙️ → Script Properties (`SONIOX_API_KEY`, `NVIDIA_API_KEY`).

**"Suggest translation" returns "NVIDIA_API_KEY not configured."**
The NIM key isn't set in Script Properties. Get one free at <https://build.nvidia.com> (sign in → pick a model → **Get API key** → copy `nvapi-…`). Apps Script editor → ⚙️ → Script Properties → add `NVIDIA_API_KEY` with that value. After saving, run `authorize()` once from the editor's function dropdown so the deploying user grants OAuth consent for the new outbound host (`integrate.api.nvidia.com`). Reasoning for using NIM is in [ADR 0007](docs/decisions/0007-translation-backend.md).

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

- **Adding API keys.** `SONIOX_API_KEY` (required) and `NVIDIA_API_KEY` (optional, for AI translation suggestions) live in Apps Script Script Properties, not in code. Set them once in Apps Script editor → ⚙️ → Script Properties; clasp doesn't touch them. After adding a new key, run `authorize()` from the editor's function dropdown so OAuth consent is granted for any new outbound hosts.
- **Connecting GitHub to Netlify.** One-time UI step. Once done, every push triggers a deploy.
- **Telling Vijayalakshmi about a new feature.** No automation can replace "hey, try the new save toast."
