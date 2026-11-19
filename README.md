# vlf-global-monitor

Exploratory dashboard of how the Earth-ionosphere waveguide, specifically the D-region (≈60-90 km altitude), responds to diverse energetic forcings as observed through fixed-path Very Low Frequency (VLF) radio propagation.

## Current processing scope

The frozen spectral-state engine currently accepts **1 Hz narrowband amplitude recordings only**. CRAAM archive type A is narrowband amplitude; type B is narrowband phase. These are different measurements, not separate corridors. Broadband types C, D, and F are also excluded from the current engine.

See [CRAAM archive format and ingestion policy](docs/CRAAM_ARCHIVE_FORMAT.md) for the source-backed mapping and filtering rules.

## Validation

The Patricia 2015-10-22 NAA type-A archive object has been downloaded and processed in GitHub Actions. Its archive identity and outputs match the local reference (A=0.0248, T=0.0512, tau=1256). The earlier historical T=0.0826 discrepancy remains unresolved; no frozen metric definition or threshold was changed.

The raw MATLAB reference is not retained in the repository.
