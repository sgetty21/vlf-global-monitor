# CRAAM Open VLF archive filename and measurement types

## Verified source convention

The Open VLF frontend source defines the archive `typeABCDF` mapping in
`src/store/demo.ts` (`mapABCDF`):

| Code | Band | Measurement |
|---|---|---|
| A | Low frequency / narrowband | Amplitude |
| B | Low frequency / narrowband | Phase |
| C | High frequency / broadband | Amplitude |
| D | High frequency / broadband | Phase |
| F | High frequency / broadband | Group delay |

Source: https://github.com/open-vlf/frontend/blob/main/src/store/demo.ts

The archive inventory's filename suffix agrees with the API's `typeABCDF`
field convention. For example, `FE151022000500NAA_008A.mat` is a low-band
amplitude recording; the matching `..._008B.mat` is phase, not another
independent transmitter-receiver corridor.

## VLF Global Monitor ingestion policy (current engine)

The current frozen engine accepts 1 Hz narrowband amplitude data only.
Therefore, its eligible archive input is **type A** (low/narrowband amplitude).

- Accept type A for the current amplitude engine, subject to metadata and
  sampling-rate validation.
- Do not send B (phase), C (broadband amplitude), D (broadband phase), or F
  (group delay) through the current engine.
- Do not treat A/B (or other measurement types) as separate corridors.
  Corridor identity is determined by receiver, transmitter, frequency, and
  observation time; measurement type is a separate dimension.
- Preserve excluded variants in archive discovery metadata so they can be
  studied later with separately specified and validated engines.
- Never silently convert phase or broadband measurements into amplitude data.

## Naming and metadata cautions

The final letter is a measurement-type code, not a receiver or transmitter
identifier. The numeric portion before it is an archive/file sequence and
must not be assumed to identify a distinct corridor without metadata checks.

The folder `FE` is the archive station-folder code. Do not infer that it is
identical to a MAT-file's internal receiver-station metadata (the Patricia
fixture reports EACF).

## Evidence boundary

This mapping is verified from the Open VLF frontend source code. It does not
by itself establish all MAT-file internal metadata, sampling rates, channel
calibration, or the scientific suitability of every archive record. Those
must be checked per recording before processing.
