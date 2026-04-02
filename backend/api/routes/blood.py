from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Dict
from pydantic import BaseModel
from services.quest import exchange_code_for_token, fetch_diagnostic_reports
from services.biomarker_normalizer import normalize_observations
from parsers.blood_parser import parse_blood_csv, BloodFileParseError

router = APIRouter()

SUPPORTED_BLOOD_TYPES = {".csv"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str


class ManualBloodEntry(BaseModel):
    markers: Dict[str, float]


# ── CSV File Upload ──────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_blood_file(file: UploadFile = File(...)):
    """
    Accept a blood results CSV file and return normalised biomarker values.

    Expected CSV columns: marker, value [, unit]
    """
    filename = file.filename or ""
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if suffix not in SUPPORTED_BLOOD_TYPES:
        raise HTTPException(
            status_code=415,
            detail={
                "error": "unsupported_file_type",
                "message": f"'{filename}' is not supported. Only CSV files are accepted for blood results.",
                "supported_formats": sorted(SUPPORTED_BLOOD_TYPES),
                "hint": "Export your lab results as a CSV with columns: marker, value [, unit]",
            },
        )

    content_bytes = await file.read()

    if len(content_bytes) == 0:
        raise HTTPException(
            status_code=422,
            detail={"error": "empty_file", "message": "The uploaded file is empty."},
        )

    if len(content_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "file_too_large",
                "message": f"File exceeds the 5 MB limit ({len(content_bytes) / 1024:.1f} KB uploaded).",
            },
        )

    try:
        text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = content_bytes.decode("latin-1")
        except Exception:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "encoding_error",
                    "message": "File encoding could not be determined. Please save your CSV as UTF-8.",
                },
            )

    try:
        result = parse_blood_csv(text)
    except BloodFileParseError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "parse_failed",
                "message": str(e),
                "hint": "Ensure the CSV has a header row with at minimum 'marker' and 'value' columns.",
            },
        )

    if not result.markers:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "no_valid_markers",
                "message": "No valid markers could be extracted.",
                "parse_errors": result.errors,
                "parse_warnings": result.warnings,
            },
        )

    # Normalise against reference ranges
    normalised = {
        name: _normalise_marker(name, value)
        for name, value in result.markers.items()
    }

    return {
        "biomarkers": normalised,
        "row_count": result.row_count,
        "marker_count": len(normalised),
        "warnings": result.warnings,
        "parse_errors": result.errors,
    }


def _normalise_marker(name: str, value: float) -> dict:
    """Apply reference range logic to a single marker value."""
    from services.biomarker_normalizer import LOINC_MAP
    for _, (marker_name, unit, (ref_low, ref_high)) in LOINC_MAP.items():
        if marker_name == name:
            if value < ref_low:
                status = "low"
            elif value > ref_high:
                status = "high"
            else:
                status = "normal"
            return {"value": value, "unit": unit, "status": status}
    return {"value": value, "unit": "", "status": "unknown"}


# ── Quest Diagnostics OAuth ──────────────────────────────────────────────────

@router.post("/quest/callback")
async def quest_oauth_callback(body: OAuthCallbackRequest):
    """Exchange Quest OAuth authorization code for token and fetch FHIR DiagnosticReports."""
    if not body.code:
        raise HTTPException(
            status_code=400,
            detail={"error": "missing_code", "message": "OAuth authorization code is required."},
        )
    try:
        token = await exchange_code_for_token(body.code)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "quest_auth_failed",
                "message": f"Could not exchange OAuth code with Quest Diagnostics: {e}",
                "hint": "Ensure QUEST_CLIENT_ID and QUEST_CLIENT_SECRET are correctly set in .env",
            },
        )
    try:
        reports = await fetch_diagnostic_reports(token)
        normalised = normalize_observations(reports)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "quest_fetch_failed",
                "message": f"Connected to Quest but failed to retrieve lab results: {e}",
            },
        )

    if not normalised:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "no_results",
                "message": "Quest account connected but no DiagnosticReport records were found.",
                "hint": "Ensure lab results exist in your Quest account.",
            },
        )
    return {"biomarkers": normalised}


# ── Manual Entry ─────────────────────────────────────────────────────────────

@router.post("/manual")
def manual_blood_entry(body: ManualBloodEntry):
    """Accept manually entered blood marker values as a fallback."""
    if not body.markers:
        raise HTTPException(
            status_code=400,
            detail={"error": "no_markers", "message": "No markers provided in the request body."},
        )
    normalised = {
        name: _normalise_marker(name, value)
        for name, value in body.markers.items()
        if value > 0
    }
    return {"biomarkers": normalised, "marker_count": len(normalised)}
