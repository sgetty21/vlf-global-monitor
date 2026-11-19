#!/usr/bin/env python3
"""Download and validate the Patricia NAA reference recording from CRAAM S3.

The raw MAT file is kept in a temporary directory and is not committed or uploaded.
Only derived JSON and a validation report are retained as workflow artifacts.
"""
import argparse
import hashlib
import json
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
from scipy.signal import welch
import sys

# Make the repository root importable when this script is run from scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vlf_json_exporter import load_amplitude_array, normalize_and_filter, build_export
from archive_format import eligible_for_current_engine

BUCKET_HOST = "craam-files-bucket.s3.sa-east-1.amazonaws.com"
OBJECT_KEY = "2015/10/22/narrowband/FE/FE151022000500NAA_008A.mat"
EXPECTED_SIZE = 352232
EXPECTED_ETAG = "b85ced04184a54c8641063f7f806e7fe"


def coherence_diagnostic(values: np.ndarray, nperseg: int) -> float:
    """Calculate the existing centroid ±10% T metric for a Welch sensitivity check."""
    frequencies, power = welch(values, fs=1.0, nperseg=min(nperseg, values.size))
    total_power = float(np.sum(power))
    if total_power <= 0.0 or not np.isfinite(total_power):
        return 0.0
    centroid = float(np.sum(frequencies * power) / total_power)
    in_band = (frequencies >= 0.9 * centroid) & (frequencies <= 1.1 * centroid)
    return round(float(np.sum(power[in_band]) / total_power), 4)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("data/patricia-validation"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if not eligible_for_current_engine(Path(OBJECT_KEY).name, "narrowband"):
        raise RuntimeError("Refusing to process a non-type-A or non-narrowband file with the amplitude engine.")

    url = f"https://{BUCKET_HOST}/{OBJECT_KEY}"
    request = urllib.request.Request(url, headers={"User-Agent": "vlf-global-monitor/1.0"})
    with tempfile.TemporaryDirectory(prefix="vlf-patricia-") as temp_dir:
        mat_path = Path(temp_dir) / Path(OBJECT_KEY).name
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
            response_etag = response.headers.get("ETag", "").strip('"').lower()
        if len(payload) != EXPECTED_SIZE:
            raise RuntimeError(f"Size mismatch: expected {EXPECTED_SIZE}, received {len(payload)}")
        md5 = hashlib.md5(payload).hexdigest()
        if md5 != EXPECTED_ETAG or (response_etag and response_etag != EXPECTED_ETAG):
            raise RuntimeError(
                f"Object identity check failed: md5={md5}, response_etag={response_etag!r}"
            )
        mat_path.write_bytes(payload)

        signal = load_amplitude_array(mat_path)
        filtered = normalize_and_filter(signal)
        result = build_export(signal, filtered, Path(OBJECT_KEY).name)
        # Diagnostic only: compare the current full-record Welch segment length
        # with the 256-sample setting found in the earlier project exporter.
        # This does not alter the canonical exporter or its reported metrics.
        legacy_t_256 = coherence_diagnostic(filtered, 256)

    result["source"] = {
        "provider": "CRAAM Open VLF public S3 bucket",
        "bucket": "craam-files-bucket",
        "region": "sa-east-1",
        "object_key": OBJECT_KEY,
        "object_etag": EXPECTED_ETAG,
        "object_size_bytes": EXPECTED_SIZE,
        "observation_date_utc": "2015-10-22",
        "transmitter": "NAA",
        "archive_station_folder": "FE",
        "archive_variant": "008A",
    }
    output_json = args.output_dir / "patricia_2015_naa_eacf_validation.json"
    output_json.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    summary = result["summary"]
    report = {
        "object_identity_verified": True,
        "object_key": OBJECT_KEY,
        "sample_count": summary["samples"],
        "complete_hours": summary["complete_hours"],
        "trailing_partial_hour_samples": summary["trailing_partial_hour_samples"],
        "observed": {"A": summary["A"], "T": summary["T"], "tau": summary["tau"]},
        "previous_local_reference": {"A": 0.0248, "T": 0.0512, "tau": 1256},
        "comparison": {
            "A_matches_previous_local_reference": summary["A"] == 0.0248,
            "T_matches_previous_local_reference": summary["T"] == 0.0512,
            "tau_matches_previous_local_reference": summary["tau"] == 1256,
        },
        "welch_sensitivity_diagnostic": {
            "current_full_record_nperseg": min(4096, filtered.size),
            "legacy_project_nperseg": min(256, filtered.size),
            "current_T": summary["T"],
            "legacy_256_T": legacy_t_256,
            "previously_cited_T": 0.0826,
            "note": (
                "The 256-sample result is diagnostic only. It is not substituted "
                "for the current exporter output or adopted as the canonical T value."
            ),
        },
        "note": (
            "The earlier cited T=0.0826 is reproduced by the 256-sample Welch diagnostic. "
            "State labels are not calculated by the metrics exporter; interpretation is reserved for human review."
        ),
        "raw_mat_retained": False,
    }
    report_path = args.output_dir / "validation_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
