# Dashboard operations

## Data flow
1. Run **Actions → Validate Patricia NAA archive reference → Run workflow**.
2. The workflow downloads the checksum-verified CRAAM type-A recording, runs the frozen exporter, and creates an immutable record at `published/runs/<run-id>-<run-attempt>.json` on branch `data`.
3. It appends that record to `published/index.json`. The separate `published/annotations.json` file is not generated or overwritten by the workflow.
4. GitHub Pages deploys the static dashboard. The dashboard fetches the index and latest record from the public `data` branch. Actions artifacts remain short-lived diagnostics only.

## One-time setup
- Repository must remain public for unauthenticated raw.githubusercontent.com reads.
- Settings → Actions → General → Workflow permissions: grant read and write permissions.
- Settings → Pages: set Source to **GitHub Actions**.
- No branch protection is currently required for the data branch. If you later add protection, permit the workflow bot to push.

## Human annotations
Edit `published/annotations.json` on the `data` branch. Example:
```json
{"schema_version":1,"annotations":[{"recording_file":"FE151022000500NAA_008A.mat","indicator":"B","reviewer":"Reviewer name","reviewed_at_utc":"2026-11-19T00:00:00Z","notes":"Human interpretation","provenance":"Describe evidence and review method"}]}
```
Only exact A, B, C or D values with reviewer, timestamp and provenance are accepted. Invalid or absent annotations display as Unassigned. No indicator is inferred from A, T or tau.

## Immutability and retry behavior
A publication key includes both GitHub run ID and run attempt. Re-running a workflow creates a distinct record. Repeating the same publication is idempotent; conflicting content under an existing key fails. Workflow concurrency serializes publisher runs. The frozen signal engine and its equations are not modified by publication infrastructure.

## Validation checks
- Confirm a successful validation run and a new immutable record on `data`.
- Confirm the index points to that record.
- Confirm annotations survive a later publication unchanged.
- Confirm dashboard shows measured A, T and tau, timestamp, and human annotation separately.
- Confirm empty/error states do not display fabricated measurements.
