from __future__ import annotations

from typing import Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.integration_engine import integrate
from services.insight_generator import generate_insights
from services.disease_risk import compute_disease_risks

router = APIRouter()


class InsightRequest(BaseModel):
    enriched_variants: List[dict]
    biomarkers: Dict[str, dict]  # name → {value, unit, status}


@router.post("/generate")
async def generate(body: InsightRequest):
    """
    Cross-reference genetic variants with blood biomarkers.
    Returns domain insights + ranked disease risk list.
    """
    if not body.enriched_variants and not body.biomarkers:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "no_data",
                "message": "At least one data source (genomic variants or blood markers) is required.",
            },
        )

    try:
        integrated = integrate(body.enriched_variants, body.biomarkers)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "integration_failed", "message": str(e)},
        )

    try:
        insights = generate_insights(integrated)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "insight_generation_failed", "message": str(e)},
        )

    try:
        disease_risks = await compute_disease_risks(body.enriched_variants, body.biomarkers)
    except Exception as e:
        # Non-fatal — return insights without disease risks rather than failing
        disease_risks = []
        return {
            "insights": insights,
            "disease_risks": disease_risks,
            "disease_risk_warning": f"Disease risk computation failed: {e}",
        }

    return {
        "insights": insights,
        "disease_risks": disease_risks,
    }
