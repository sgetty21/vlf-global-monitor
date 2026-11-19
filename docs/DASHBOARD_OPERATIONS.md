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


## Historical Open VLF retrieval

The **Pull historical Open VLF date** workflow queries the public CRAAM S3 bucket for one UTC date. It is intentionally manual: no continuous crawler or unbounded backfill runs.

1. Open Actions → **Pull historical Open VLF date** → Run workflow.
2. Enter the observation date as `YYYY-MM-DD`.
3. Optionally filter by CRAAM station folder (for example `FE`) and transmitter (for example `NAA`).
4. Keep the default 10-file cap for the first retrieval. The workflow rejects batches above 20 files.
5. The workflow lists the date's `narrowband/` prefix, selects filename type A only, downloads each object temporarily, checks size and ETag consistency, computes a SHA-256 digest, and inspects MAT metadata.
6. A file is processed only when MAT metadata verifies 1 Hz sampling and amplitude-only, non-broadband input. Files without verifiable metadata are rejected rather than assumed compatible.
7. Each recording is passed independently to the frozen exporter. No phase/broadband conversion, resampling, interpolation, or partial-hour padding occurs.
8. Metric JSON and gzip-compressed 1 Hz raw/filtered waveform sidecars are published under `historical/<date>/<run-id>-<attempt>/` on the `data` branch. `historical/index.json` is append-only by date/run/attempt.
9. On the dashboard, choose the date in **Historical archive explorer** and browse the published recording. The waveform plot is display-decimated; the gzip sidecar retains every original sample.

The dashboard can browse only dates that have already been retrieved. Launching a new retrieval currently requires the GitHub Actions interface; the static Pages site does not dispatch workflows or request write permissions.

### First acceptance retrieval

Start with **2015-10-22**, station folder **FE**, transmitter **NAA**. Confirm the selected MAT object's internal sample rate and amplitude/band flags, then compare the resulting record with `data/patricia_2015_naa_eacf_validation.json`. Do not force a match: the documented T and τ reference discrepancies remain validation findings.

### Storage and reproducibility

Raw source MAT files are downloaded to temporary runner storage and are not committed. The compact derived waveform sidecar preserves raw amplitude and normalized/filtered samples; metrics JSON stores hourly and full-record results plus source object key, ETag, object size, download SHA-256, source metadata, and run provenance. Each run attempt has its own immutable directory. Large date collections should be processed in small, filtered batches; this repository-backed storage is intended for modest research subsets, not as a mirror of the entire CRAAM archive.
