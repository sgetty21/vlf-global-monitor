#!/usr/bin/env python3
"""Classify CRAAM Open VLF filename variants for the current amplitude engine.

The mapping follows the Open VLF frontend's typeABCDF map. This module does
not inspect MAT-file contents; metadata and sampling rate must still be
validated independently.
"""
from pathlib import Path
import re

TYPE_MAP = {
    "A": {"band": "narrowband", "measurement": "amplitude"},
    "B": {"band": "narrowband", "measurement": "phase"},
    "C": {"band": "broadband", "measurement": "amplitude"},
    "D": {"band": "broadband", "measurement": "phase"},
    "F": {"band": "broadband", "measurement": "group_delay"},
}

_FILENAME_TYPE = re.compile(r"_\d{3}([ABCDF])\.mat$", re.IGNORECASE)


def classify_archive_file(filename: str) -> dict:
    """Return the verified band/measurement classification from its suffix."""
    match = _FILENAME_TYPE.search(Path(filename).name)
    if not match:
        raise ValueError(f"Unrecognized CRAAM A/B/C/D/F filename suffix: {filename}")
    code = match.group(1).upper()
    return {"code": code, **TYPE_MAP[code]}


def eligible_for_current_engine(filename: str, archive_band: str) -> bool:
    """Only narrowband amplitude (type A) is eligible for the frozen engine."""
    metadata = classify_archive_file(filename)
    return (
        archive_band.lower() == "narrowband"
        and metadata["code"] == "A"
        and metadata["band"] == "narrowband"
        and metadata["measurement"] == "amplitude"
    )


if __name__ == "__main__":
    examples = [
        "FE151022000500NAA_008A.mat",
        "FE151022000500NAA_008B.mat",
    ]
    for item in examples:
        print(item, classify_archive_file(item))
