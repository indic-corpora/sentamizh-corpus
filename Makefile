# Sentamizh Corpus — local deploy helpers.
#
# These are convenience shortcuts. You don't need them if you've set up
# auto-deploy (GitHub → Netlify for frontend, GitHub Actions for backend).
# But they're useful for fast iteration without going through git.
#
# One-time setup:
#   npm install -g @google/clasp@3.3.0 netlify-cli
#   clasp login                     # OAuth dance, opens browser
#   netlify login                   # OAuth dance, opens browser
#   echo "<your-deployment-id>" > .clasp-deployment-id
#
# See DEPLOY.md for how to find your scriptId / deploymentId.

.PHONY: help validate deploy deploy-backend deploy-frontend build-annotator-data logs status

help:
	@echo "Targets:"
	@echo "  validate              — run schema + cross-field validator on data/processed/"
	@echo "  build-annotator-data  — copy data/processed/ JSONs into annotator/data/"
	@echo "  deploy                — deploy both backend and frontend"
	@echo "  deploy-backend        — clasp push + clasp version + clasp redeploy (Apps Script)"
	@echo "  deploy-frontend       — build-annotator-data + netlify deploy --prod"
	@echo "  logs                  — tail Apps Script execution logs"
	@echo "  status                — show clasp status (which files would be pushed)"

# Read the deployment ID from a one-line file (kept out of git via .gitignore).
DEPLOYMENT_ID ?= $(shell cat .clasp-deployment-id 2>/dev/null)

validate:
	python3 scripts/validate.py data/processed/

deploy: deploy-backend deploy-frontend

deploy-backend:
	@if [ -z "$(DEPLOYMENT_ID)" ]; then \
		echo "DEPLOYMENT_ID not set. One of:"; \
		echo "  - echo <id> > .clasp-deployment-id   (then re-run make deploy-backend)"; \
		echo "  - make deploy-backend DEPLOYMENT_ID=AKfy..."; \
		exit 1; \
	fi
	@# Manifest guard — fail fast if someone's edited webapp.access away from
	@# ANYONE. Mirrors the same check the GitHub Actions workflow runs. See
	@# DEPLOY.md → Troubleshooting for why.
	@python3 -c 'import json,sys; m=json.load(open("annotator/appsscript.json")); w=m.get("webapp") or {}; sys.exit(0 if w.get("access")=="ANYONE" and w.get("executeAs")=="USER_DEPLOYING" else (print("ERROR: annotator/appsscript.json must declare webapp.access=ANYONE and webapp.executeAs=USER_DEPLOYING") or 1))'
	clasp push --force
	@# Pin the version explicitly. Letting clasp infer it on redeploy is the
	@# root cause of clasp issue #63 (silent duplicate deployments).
	$(eval VERSION := $(shell clasp version "Local $(shell date -u +%Y-%m-%dT%H:%MZ)" | grep -oE '[0-9]+' | tail -n 1))
	@if [ -z "$(VERSION)" ]; then echo "ERROR: clasp version did not return a version number"; exit 1; fi
	clasp redeploy $(DEPLOYMENT_ID) \
		-V $(VERSION) \
		-d "Local $(shell date -u +%Y-%m-%dT%H:%MZ)"

deploy-frontend: build-annotator-data
	netlify deploy --prod --dir=annotator

build-annotator-data:
	python3 scripts/build_annotator_data.py

logs:
	clasp logs --simplified

status:
	@echo "── clasp status ──────────────────────────────────────────"
	@clasp status || true
	@echo
	@echo "── deployment id ─────────────────────────────────────────"
	@echo "$(DEPLOYMENT_ID)"
	@echo
	@echo "── netlify status ────────────────────────────────────────"
	@netlify status 2>/dev/null || echo "  (netlify CLI not configured; run 'netlify login' + 'netlify init')"
