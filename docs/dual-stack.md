# FirmShake API dual-stack

Devo (`firmshake-dev`, staging Cloud Run us-central1) vs prod (`firmshake-prod`, Cloud Run **us-east1**). Sibling web docs: `../firmshake/docs/devo-prod-stacks.md`.

## What you need to do

1. **Keep staging on deovo** — `.cloudrun.env.yaml` with `FIREBASE_PROJECT_ID=firmshake-dev`, `GCS_BUCKET=firmshake-dev-images`, control-panel CORS, `PAYMENTS_ENABLED=true` (**mock deposits only** — no Stripe keys).
2. **Fill prod env** — `.cloudrun.env.prod.yaml`: replace `RECAPTCHA_SITE_KEY`, optionally Typesense; leave `PAYMENTS_ENABLED=false`; never add Stripe keys or control-panel origins.
3. **Assert / readiness before deploy** (dry-run only)
   ```bash
   bash scripts/preflight-api.sh deovo
   bash scripts/preflight-api.sh prod   # fails until placeholders gone
   # same as: bash scripts/assert-cloudrun-env.sh deovo|prod
   bash scripts/check-prod-readiness.sh  # cross-repo: lists ALL web+API blockers
   ```
4. **Deploy**
   ```bash
   bash scripts/deploy-staging.sh   # or deploy-devo.sh
   bash scripts/deploy-prod.sh      # only when assert passes
   ```
5. **Smoke `/health`** (after deploy — requires stack-aware payload)
   ```bash
   bash scripts/smoke-health.sh https://firmshake-api-staging-….run.app deovo
   # prod: bash scripts/smoke-health.sh https://…us-east1.run.app prod
   ```
   Expected JSON includes `stack`, `firebaseProjectId`, `paymentsEnabled` (no secrets).
6. **Wire web** — copy printed prod Cloud Run URL into firmshake `.env.production.local` `VITE_API_BASE_URL`.
7. **CI** — Environment `prod` secrets + leave `PROD_DEPLOY_ENABLED` unset until a manual prod deploy is proven (see firmshake `docs/ci-promote-pipeline.md`).

## Module map (parallel-agent friendly)

| Concern | Module |
|---|---|
| Payments flag | `services/payments_flag.py` |
| Stack IDs + CORS catalogs | `services/stack_config.py` |
| `/health` payload | `services/health_payload.py` → `routes/health.py` |
| Env YAML assert | `scripts/assert-cloudrun-env.sh` (also refuses active `STRIPE_*` on prod) |
| Preflight (assert only) | `scripts/preflight-api.sh` |
| Cross-repo prod readiness | `scripts/check-prod-readiness.sh` → sibling web dry-run |
| Health smoke | `scripts/smoke-health.sh` |
| Deploy | `scripts/deploy-staging.sh`, `scripts/deploy-prod.sh` |
| Stripe / deposits | `services/stripe_deposits.py` (gates on payments flag) |

`config.py` re-exports `are_payments_enabled` and resolves `APP_STACK` for convenience.

## CORS

| Stack | Origins |
|---|---|
| Devo (transitional) | deovo Hosting + control panel + localhost + **firm-shake.com / www** (while apex still on deovo) |
| Devo (post-cutover) | drop prod domains — constants in `stack_config.DEVO_CORS_ORIGINS_POST_CUTOVER` |
| Prod | apex, www, firmshake-prod Hosting, Capacitor — **no** control panel |

## Payments (no processor this phase)

Full prod dual-stack ships **without a payment processor**. Do not add Stripe keys or plan live checkout in cutover.

| Stack | Flag | Behavior |
|---|---|---|
| Prod | `PAYMENTS_ENABLED=false` | Deposit creation **503**; webhook `{ "mode": "disabled" }` |
| Devo | `PAYMENTS_ENABLED=true` | Mock deposit confirmation only when Stripe is unset |

Never configure `STRIPE_SECRET_KEY` / live keys for this phase.

## Human-only (not automatable here)

- Create Typesense **prod** cluster + keys (optional for first deploy — Firestore fallback)
- **Exact gate:** `.cloudrun.env.prod.yaml` → `RECAPTCHA_SITE_KEY: 'REPLACE_ME_PROD_RECAPTCHA_SITE_KEY'` blocks `deploy-prod.sh`
- Sibling web gate: `firmshake/.env.production.local` → `VITE_API_BASE_URL=...REPLACE-ME...` blocks `npm run deploy:prod` until Cloud Run URL is pasted
- GCP IAM / Artifact Registry / Cloud Run first deploy credentials
- GitHub Environment secrets + WIF migration
- DNS / Firebase custom domain cutover (web runbook)
- Leave repo variable `PROD_DEPLOY_ENABLED` unset until a manual prod deploy is proven

Confirm anytime: `bash scripts/check-prod-readiness.sh` (or from web: `npm run check:prod-readiness`).

Sibling checklist: `firmshake/docs/devo-prod-stacks.md` → **Human-only leftovers**.

## `/health` contract

```json
{
  "status": "ok",
  "service": "firmshake-api",
  "stack": "devo",
  "firebaseProjectId": "firmshake-dev",
  "paymentsEnabled": true
}
```

Prod smoke expects `stack=prod`, `firebaseProjectId=firmshake-prod`, `paymentsEnabled=false`.

## Tests

```bash
.venv/bin/pytest tests/test_payments_enabled.py tests/test_stack_config.py tests/test_assert_cloudrun_env.py tests/test_check_prod_readiness.py tests/test_health_stack.py tests/test_smoke_health_script.py tests/test_env_contracts.py -q
```

## Workflow YAML patch (apply with `workflow` scope)

Agent HTTPS tokens often lack GitHub `workflow` scope, so CI edits ship as a patch:

```bash
git apply docs/ci-deploy-api.workflow.patch
```

Then push with a `workflow`-scoped credential. Soft gate `PROD_DEPLOY_ENABLED` stays unset until a manual prod deploy is proven. Sibling web: `firmshake/docs/ci-deploy-web.workflow.patch`.

