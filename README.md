# VLF Global Monitor

An open, exploratory project for examining how fixed-path Very Low Frequency (VLF) radio propagation responds to changing conditions in the Earth-ionosphere waveguide, particularly the D-region (approximately 60–90 km altitude).

The project is intended as a transparent scientific monitoring and analysis resource. It does not predict earthquakes, provide pre-seismic forecasts, or directly estimate wind speed.

## Current processing scope

The current processing pipeline is limited to **1 Hz narrowband amplitude recordings** from the CRAAM Open VLF archive.

- CRAAM type A: narrowband amplitude — included in the current engine.
- CRAAM type B: narrowband phase — not processed by the current amplitude engine.
- CRAAM types C, D and F: broadband measurement types — not processed by the current amplitude engine.

These archive type codes identify measurement products; they do not identify separate propagation corridors. Each transmitter–receiver path should be treated independently rather than averaged with other paths.

See [CRAAM archive format and ingestion policy](docs/CRAAM_ARCHIVE_FORMAT.md) for the archive mapping and filtering rules.

## Measurement outputs and interpretation

The engine reports three quantitative measurements for each complete hourly window:

- **A — amplitude energy:** RMS of the filtered, normalized amplitude signal.
- **T — spectral coherence:** fraction of Welch power spectral density within the defined band around the spectral centroid.
- **τ — persistence:** count of samples whose absolute filtered value exceeds 2.5 times the filtered signal's standard deviation.

The current frozen processing definition uses median normalization, a fifth-order zero-phase Butterworth bandpass from 0.001 to 0.1 Hz, and complete 3,600-sample hourly windows. Incomplete trailing hours are not padded into a full window.

**A/B/C/D state indicators are human interpretations, not automatic classifications.** The engine does not infer these labels from A, T or τ. If an indicator is supplied, it must be entered separately by a human reviewer and should be treated as an annotation whose provenance and interpretation are documented. Missing indicators remain unassigned.

Historical benchmark labels displayed in the dashboard are retained for context only. They are not current engine outputs, and their provenance and interpretation require human review.

## Patricia reference validation

The project includes a reference validation for the 2015-10-22 NAA–EACF narrowband-amplitude archive recording. The recorded full-file metrics are A = 0.0248, T = 0.0512 and τ = 1256.

A Welch sensitivity check reproduced the historical full-record T = 0.0826 when using the earlier project setting of nperseg = 256. The current setting (up to nperseg = 4096) produces T = 0.0512. This explains the historical full-record T difference as a Welch segment-length configuration difference. The current 4096-based result remains the canonical pipeline output; the 256-based result is retained as a diagnostic comparison, not substituted into the engine. The earlier hourly-result discrepancy is a separate issue and remains under investigation. No processing equations or thresholds were changed to force agreement.

The raw MATLAB recording is not stored in this repository. The validation JSON and report are derived artifacts; consult their metadata and the workflow logs when reproducing the validation.

## Workflows and dashboard

GitHub Actions workflows support CRAAM archive discovery and the Patricia reference validation. The dashboard source is located at [dashboard/vlf-d-region-monitor.html](dashboard/vlf-d-region-monitor.html). It can load JSON containing hourly A, T and τ measurements, with an optional separately supplied `human_indicator` field.

The dashboard is a repository artifact. Public hosting (for example, GitHub Pages) must be configured and tested separately before it should be described as a live service.

## Open science and reuse

This repository is released under the MIT License. Contributions, independent replication, issue reports and clearly documented alternative analyses are welcome. Please preserve the distinction between measured quantities, human annotations and hypotheses when extending the project.
