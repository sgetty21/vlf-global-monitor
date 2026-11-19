#!/usr/bin/env python3
"""
VLF Spectral State Engine JSON exporter
---------------------------------------
Processes a 1 Hz amplitude-only MATLAB (.mat) recording and exports the
canonical full-record and hourly metrics for the vlf-global-monitor dashboard.

Requirements:
    pip install numpy scipy

Usage:
    python vlf_json_exporter.py input.mat
    python vlf_json_exporter.py input.mat --output latest_global_vlf.json

Assumptions:
    - Input samples are uniformly sampled at exactly 1 Hz.
    - The MATLAB variable `data` is preferred. If absent, the largest
      numeric one-dimensional array is selected.
    - No resampling, padding, interpolation, or missing-value repair is done.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.io import loadmat
from scipy.signal import butter, filtfilt, welch


FS = 1.0
FILTER_ORDER = 5
LOW_HZ = 0.001
HIGH_HZ = 0.1
HOUR_SAMPLES = 3600
OUTLIER_SIGMA = 2.5


def load_amplitude_array(mat_path: Path) -> np.ndarray:
    """Load `data`, or otherwise the largest numeric 1-D MATLAB variable."""
    contents = loadmat(mat_path)

    if "data" in contents:
        candidate = np.asarray(contents["data"])
        candidate = np.squeeze(candidate)
        if candidate.ndim != 1 or not np.issubdtype(candidate.dtype, np.number):
            raise ValueError("MATLAB variable 'data' is not a numeric 1-D array.")
        signal = candidate
    else:
        candidates = []
        for name, value in contents.items():
            if name.startswith("__"):
                continue
            arr = np.squeeze(np.asarray(value))
            if arr.ndim == 1 and arr.size > 1 and np.issubdtype(arr.dtype, np.number):
                candidates.append((arr.size, name, arr))
        if not candidates:
            raise ValueError("No numeric 1-D signal array found in the MAT file.")
        _, selected_name, signal = max(candidates, key=lambda item: item[0])
        print(f"Note: MATLAB variable 'data' not found; using '{selected_name}'.",
              file=sys.stderr)

    signal = np.asarray(signal, dtype=np.float64).reshape(-1)
    if signal.size < 2:
        raise ValueError("Signal contains fewer than two samples.")
    if not np.all(np.isfinite(signal)):
        raise ValueError("Signal contains NaN or infinite values; no imputation was applied.")

    return signal


def normalize_and_filter(signal: np.ndarray) -> np.ndarray:
    """Apply median normalization and a 5th-order zero-phase Butterworth bandpass."""
    med = float(np.median(signal))
    if med == 0.0:
        raise ValueError("Median amplitude is zero; median normalization is undefined.")

    normalized = (signal - med) / med

    # The Nyquist frequency at 1 Hz sampling is 0.5 Hz.
    if not (0.0 < LOW_HZ < HIGH_HZ < FS / 2.0):
        raise ValueError("Bandpass limits are invalid for the assumed 1 Hz sample rate.")

    b, a = butter(
        FILTER_ORDER,
        [LOW_HZ, HIGH_HZ],
        btype="bandpass",
        fs=FS,
        output="ba",
    )

    # filtfilt is zero-phase; reject records too short for its edge requirements.
    try:
        filtered = filtfilt(b, a, normalized)
    except ValueError as exc:
        raise ValueError(
            "Signal is too short for the selected zero-phase filter. "
            "Provide a longer recording; the data will not be padded."
        ) from exc

    return np.asarray(filtered, dtype=np.float64)


def calculate_metrics(values: np.ndarray) -> dict:
    """Return RMS energy A, Welch centroid-band fraction T, and persistence tau."""
    values = np.asarray(values, dtype=np.float64)
    if values.size == 0:
        raise ValueError("Cannot calculate metrics for an empty window.")

    energy = float(np.sqrt(np.mean(np.square(values))))

    frequencies, power = welch(values, fs=FS, nperseg=min(4096, values.size))
    total_power = float(np.sum(power))

    if total_power <= 0.0:
        coherence = 0.0
    else:
        centroid = float(np.sum(frequencies * power) / total_power)
        lower = 0.9 * centroid
        upper = 1.1 * centroid
        in_band = (frequencies >= lower) & (frequencies <= upper)
        coherence = float(np.sum(power[in_band]) / total_power)

    threshold = OUTLIER_SIGMA * float(np.std(values))
    persistence = int(np.count_nonzero(np.abs(values) > threshold))

    return {
        "A": round(energy, 4),
        "T": round(coherence, 4),
        "tau": persistence,
    }


def classify_state(tau: int, coherence: float) -> str:
    """Apply the frozen operational state rules in priority order."""
    if tau > 600:
        return "A"
    if tau > 250 and coherence >= 0.075:
        return "B"
    if tau > 100:
        return "C"
    return "D"


def build_export(signal: np.ndarray, filtered: np.ndarray, filename: str) -> dict:
    full_metrics = calculate_metrics(filtered)

    hourly = []
    complete_hours = filtered.size // HOUR_SAMPLES
    trailing_samples = int(filtered.size % HOUR_SAMPLES)

    for hour_index in range(complete_hours):
        start = hour_index * HOUR_SAMPLES
        stop = start + HOUR_SAMPLES
        metrics = calculate_metrics(filtered[start:stop])
        hourly.append({
            "hour": hour_index,
            "tau": metrics["tau"],
            "A": metrics["A"],
            "T": metrics["T"],
            "state": classify_state(metrics["tau"], metrics["T"]),
        })

    peak = None
    if hourly:
        peak_hour = max(hourly, key=lambda record: record["tau"])
        peak = dict(peak_hour)

    return {
        "file": filename,
        "summary": {
            "samples": int(signal.size),
            "sample_rate_hz": FS,
            "duration_seconds": int(signal.size),
            "complete_hours": int(complete_hours),
            "trailing_partial_hour_samples": trailing_samples,
            "A": full_metrics["A"],
            "T": full_metrics["T"],
            "tau": full_metrics["tau"],
            "state": classify_state(full_metrics["tau"], full_metrics["T"]),
            "filter": {
                "type": "Butterworth bandpass",
                "order": FILTER_ORDER,
                "low_hz": LOW_HZ,
                "high_hz": HIGH_HZ,
                "zero_phase": True,
            },
            "normalization": "24-hour median: (x - median(x)) / median(x)",
        },
        "hourly": hourly,
        "peak": peak,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export canonical VLF spectral-state metrics from a 1 Hz MAT file."
    )
    parser.add_argument("input", type=Path, help="Input MATLAB .mat file")
    parser.add_argument(
        "--output", "-o", type=Path, default=None,
        help="Output JSON path (default: input filename with .json extension)",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"Input file does not exist: {args.input}")

    output_path = args.output or args.input.with_suffix(".json")

    try:
        signal = load_amplitude_array(args.input)
        filtered = normalize_and_filter(signal)
        result = build_export(signal, filtered, args.input.name)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, allow_nan=False)
            handle.write("\n")

        print(f"Exported {len(result['hourly'])} complete hourly records to {output_path}")
        if result["summary"]["trailing_partial_hour_samples"]:
            print(
                "Note: trailing partial hour contains "
                f"{result['summary']['trailing_partial_hour_samples']} samples; "
                "it was reported but not padded or included as an hourly record."
            )
        return 0

    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
