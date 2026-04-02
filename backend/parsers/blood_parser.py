"""
Blood sample file parser.

Supports:
  - CSV format: columns must include 'marker', 'value', 'unit'
  - Simple two-column CSV: 'marker', 'value' (unit inferred from LOINC map)

Validation:
  - Checks for required columns
  - Rejects non-numeric values
  - Warns on unrecognised marker names
  - Enforces reasonable value bounds (no negative, no absurd outliers)
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from services.biomarker_normalizer import LOINC_MAP

# Build a flat name → reference range lookup from the LOINC map
KNOWN_MARKERS: dict[str, tuple[float, float]] = {
    name: ref_range for _, (name, _, ref_range) in LOINC_MAP.items()
}

# Reasonable absolute bounds for sanity checking (catches typos / corrupt data)
ABSOLUTE_BOUNDS: dict[str, tuple[float, float]] = {
    "Total Cholesterol": (50, 1000),
    "LDL Cholesterol": (10, 800),
    "HDL Cholesterol": (5, 200),
    "Triglycerides": (10, 5000),
    "HbA1c": (2, 20),
    "Blood Glucose": (20, 2000),
    "CRP (C-Reactive Protein)": (0, 500),
    "Ferritin": (0, 10000),
    "Hemoglobin": (2, 25),
    "White Blood Cell Count": (0.5, 100),
    "Vitamin B12": (50, 5000),
    "Vitamin D (25-OH)": (1, 200),
    "ALT": (1, 5000),
    "AST": (1, 5000),
    "Alkaline Phosphatase": (1, 3000),
    "Creatinine": (0.1, 50),
    "BUN": (1, 300),
    "Sodium": (100, 180),
    "Potassium": (1, 10),
    "Calcium": (1, 20),
    "TSH": (0.001, 100),
}

REQUIRED_COLUMNS = {"marker", "value"}


@dataclass
class ParseResult:
    markers: dict[str, float]
    warnings: list[str]
    errors: list[str]
    row_count: int


class BloodFileParseError(Exception):
    """Raised when the blood file cannot be parsed at all."""


def parse_blood_csv(content: str) -> ParseResult:
    """
    Parse a blood results CSV file.

    Returns ParseResult with markers dict, warnings, and errors.
    Raises BloodFileParseError for fatal format issues.
    """
    warnings: list[str] = []
    errors: list[str] = []
    markers: dict[str, float] = {}

    if not content.strip():
        raise BloodFileParseError("File is empty.")

    try:
        reader = csv.DictReader(io.StringIO(content.strip()))
    except Exception as e:
        raise BloodFileParseError(f"Could not read CSV: {e}")

    # Normalise column names (lowercase, stripped)
    if reader.fieldnames is None:
        raise BloodFileParseError("CSV has no header row. Expected columns: marker, value [, unit]")

    normalised_fields = {f.strip().lower() for f in reader.fieldnames if f}
    missing = REQUIRED_COLUMNS - normalised_fields
    if missing:
        raise BloodFileParseError(
            f"Missing required columns: {', '.join(sorted(missing))}. "
            f"Found: {', '.join(sorted(normalised_fields))}. "
            f"Expected columns: marker, value [, unit]"
        )

    rows = list(reader)
    if not rows:
        raise BloodFileParseError("CSV has a header but no data rows.")

    for i, row in enumerate(rows, start=2):  # start=2 because row 1 is header
        # Normalise keys
        norm_row = {k.strip().lower(): (v.strip() if v else "") for k, v in row.items() if k}
        marker_name = norm_row.get("marker", "").strip()
        raw_value = norm_row.get("value", "").strip()

        if not marker_name:
            warnings.append(f"Row {i}: Empty marker name — skipped.")
            continue

        if not raw_value:
            warnings.append(f"Row {i}: No value for '{marker_name}' — skipped.")
            continue

        # Parse value
        try:
            value = float(raw_value.replace(",", ""))
        except ValueError:
            errors.append(f"Row {i}: Non-numeric value '{raw_value}' for '{marker_name}' — skipped.")
            continue

        if value < 0:
            errors.append(f"Row {i}: Negative value {value} for '{marker_name}' — skipped.")
            continue

        # Check against known markers (warn if unrecognised, still accept)
        if marker_name not in KNOWN_MARKERS:
            warnings.append(
                f"Row {i}: '{marker_name}' is not a recognised marker — included but will not be analysed."
            )
        else:
            # Sanity-check against absolute bounds
            bounds = ABSOLUTE_BOUNDS.get(marker_name)
            if bounds:
                lo, hi = bounds
                if not (lo <= value <= hi):
                    errors.append(
                        f"Row {i}: Value {value} for '{marker_name}' is outside plausible range "
                        f"({lo}–{hi}) — skipped. Check for typos."
                    )
                    continue

        markers[marker_name] = value

    if not markers and not errors:
        raise BloodFileParseError("No valid markers could be extracted from the file.")

    return ParseResult(
        markers=markers,
        warnings=warnings,
        errors=errors,
        row_count=len(rows),
    )
