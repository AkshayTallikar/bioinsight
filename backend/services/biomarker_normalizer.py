from __future__ import annotations

"""
Normalize FHIR Observation resources from Quest into standard biomarker name/value pairs.

Maps LOINC codes to human-readable names and flags values as low/normal/high
based on standard reference ranges.
"""

# LOINC code → (display name, unit, (low, high) reference range)
LOINC_MAP: dict[str, tuple[str, str, tuple[float, float]]] = {
    "2093-3": ("Total Cholesterol", "mg/dL", (0, 200)),
    "13457-7": ("LDL Cholesterol", "mg/dL", (0, 100)),
    "2085-9": ("HDL Cholesterol", "mg/dL", (40, 999)),
    "2571-8": ("Triglycerides", "mg/dL", (0, 150)),
    "4548-4": ("HbA1c", "%", (0, 5.7)),
    "2345-7": ("Blood Glucose", "mg/dL", (70, 99)),
    "1988-5": ("CRP (C-Reactive Protein)", "mg/L", (0, 1.0)),
    "2276-4": ("Ferritin", "ng/mL", (12, 300)),
    "718-7": ("Hemoglobin", "g/dL", (12, 17.5)),
    "6690-2": ("White Blood Cell Count", "K/uL", (4.5, 11.0)),
    "14627-4": ("Vitamin B12", "pg/mL", (200, 900)),
    "1106-4": ("Vitamin D (25-OH)", "ng/mL", (30, 100)),
    "6768-6": ("Alkaline Phosphatase", "U/L", (44, 147)),
    "1742-6": ("ALT", "U/L", (7, 56)),
    "1920-8": ("AST", "U/L", (10, 40)),
    "2160-0": ("Creatinine", "mg/dL", (0.6, 1.2)),
    "3094-0": ("BUN", "mg/dL", (7, 20)),
    "2947-0": ("Sodium", "mEq/L", (136, 145)),
    "6298-4": ("Potassium", "mEq/L", (3.5, 5.1)),
    "49765-1": ("Calcium", "mg/dL", (8.5, 10.5)),
    "2965-2": ("TSH", "mIU/L", (0.4, 4.0)),
}


def normalize_observations(observations: list[dict]) -> dict[str, dict]:
    """
    Convert a list of FHIR Observation resources to a normalized biomarker dict.

    Returns:
        {
            "LDL Cholesterol": {
                "value": 130.0,
                "unit": "mg/dL",
                "status": "high",
                "loinc": "13457-7"
            },
            ...
        }
    """
    result = {}
    for obs in observations:
        loinc = _extract_loinc(obs)
        if loinc not in LOINC_MAP:
            continue

        name, unit, (ref_low, ref_high) = LOINC_MAP[loinc]
        value = _extract_value(obs)
        if value is None:
            continue

        if value < ref_low:
            status = "low"
        elif value > ref_high:
            status = "high"
        else:
            status = "normal"

        result[name] = {"value": value, "unit": unit, "status": status, "loinc": loinc}

    return result


def _extract_loinc(obs: dict) -> str:
    for coding in obs.get("code", {}).get("coding", []):
        if coding.get("system") == "http://loinc.org":
            return coding.get("code", "")
    return ""


def _extract_value(obs: dict) -> float | None:
    quantity = obs.get("valueQuantity", {})
    val = quantity.get("value")
    if val is not None:
        return float(val)
    return None
