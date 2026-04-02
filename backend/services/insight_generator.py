"""
Insight Generator — produces lifestyle recommendations from integrated
domain data (genetic variants + blood biomarker signals).

Confidence scoring:
  - high   = genetic risk variant + abnormal blood marker in same domain
  - medium = genetic risk variant only, OR abnormal blood marker only
  - low    = all values normal, weak or no variant associations
"""

DOMAIN_RECOMMENDATIONS: dict[str, dict[str, list[str]]] = {
    "cardiovascular": {
        "high": [
            "Prioritise a heart-healthy diet: limit saturated fats, increase omega-3s (fatty fish, flaxseed, walnuts)",
            "Aim for 150+ minutes of moderate cardio per week (brisk walking, cycling, swimming)",
            "Monitor blood pressure weekly; reduce sodium intake to < 2,300 mg/day",
            "Discuss statin therapy eligibility with your doctor given combined genetic and blood risk",
            "Quit smoking if applicable — it doubles cardiovascular risk independent of genetics",
        ],
        "medium": [
            "Adopt a Mediterranean-style diet to support cardiovascular health",
            "Include regular aerobic exercise at least 5 days/week",
            "Avoid smoking and limit alcohol to ≤ 1 drink/day (women) or ≤ 2 drinks/day (men)",
            "Check blood pressure at least twice yearly",
        ],
        "low": [
            "Maintain a balanced diet with plenty of fibre, vegetables, and lean protein",
            "Stay physically active — 30 minutes of movement daily is sufficient for low-risk individuals",
        ],
    },
    "metabolic": {
        "high": [
            "Significantly reduce refined carbohydrates, sugary drinks, and ultra-processed foods",
            "Prioritise high-fibre foods (legumes, oats, vegetables) to improve insulin sensitivity",
            "Incorporate resistance training 3× per week to improve glucose metabolism",
            "Consider continuous glucose monitoring (CGM) to identify personalised food responses",
            "Discuss metformin prophylaxis with your doctor if HbA1c is in the pre-diabetic range",
        ],
        "medium": [
            "Choose low-glycaemic-index foods and reduce refined carbohydrate portions",
            "Even a 5–10% reduction in body weight significantly improves metabolic markers",
            "Eat consistent meal times to stabilise blood sugar throughout the day",
        ],
        "low": [
            "Maintain a balanced carbohydrate intake and avoid long gaps between meals",
            "Annual fasting glucose check is sufficient for low-risk individuals",
        ],
    },
    "inflammation": {
        "high": [
            "Adopt an anti-inflammatory diet: turmeric, leafy greens, berries, olive oil, fatty fish",
            "Eliminate ultra-processed foods, trans fats, and excessive refined sugar",
            "Prioritise 7–9 hours of quality sleep — poor sleep elevates CRP and IL-6",
            "Manage chronic stress through mindfulness, yoga, or therapy; cortisol drives inflammation",
            "Discuss elevated CRP findings with your doctor to rule out occult infection or autoimmune disease",
        ],
        "medium": [
            "Increase antioxidant-rich foods (colourful vegetables, green tea, dark chocolate in moderation)",
            "Reduce alcohol intake — alcohol promotes systemic inflammation",
            "Exercise regularly but avoid overtraining, which paradoxically raises inflammatory markers",
        ],
        "low": [
            "Maintain an active lifestyle and a diet rich in whole foods",
            "Annual CRP check is appropriate for monitoring at low risk",
        ],
    },
    "nutrition": {
        "high": [
            "Get tested for specific deficiencies (vitamin D, B12, ferritin, folate) and supplement based on results",
            "Increase dietary sources of deficient nutrients: fatty fish and sun exposure for D, meat and dairy for B12",
            "Your genetics may impair absorption — therapeutic doses (with medical supervision) may be needed",
            "Review medications that deplete key nutrients (e.g., metformin depletes B12, PPIs reduce magnesium)",
        ],
        "medium": [
            "Ensure a varied whole-food diet covering key micronutrients",
            "Consider a baseline-quality multivitamin if dietary variety is limited",
            "Recheck deficient markers after 3 months of dietary changes or supplementation",
        ],
        "low": [
            "Maintain dietary variety — no specific supplementation needed at current levels",
            "Annual check of vitamin D in winter months if you live at high latitude",
        ],
    },
    "liver": {
        "high": [
            "Eliminate alcohol completely while liver enzymes (ALT/AST) are elevated",
            "Adopt a low-saturated-fat, high-fibre diet to reduce hepatic fat accumulation",
            "Avoid hepatotoxic supplements: high-dose niacin, kava, excess vitamin A, bodybuilding supplements",
            "Lose weight gradually if BMI > 25 — rapid weight loss can worsen fatty liver",
        ],
        "medium": [
            "Reduce alcohol and processed food intake",
            "Maintain a healthy body weight — liver health correlates strongly with BMI",
        ],
        "low": [
            "Limit alcohol to recommended guidelines and maintain a healthy weight",
        ],
    },
    "kidney": {
        "high": [
            "Reduce dietary sodium (< 2,000 mg/day) and moderate protein intake if creatinine is elevated",
            "Stay well hydrated (2–3 L water/day) unless your doctor advises fluid restriction",
            "Avoid regular NSAIDs (ibuprofen, naproxen) — they reduce renal blood flow",
            "Control blood pressure aggressively — hypertension is the leading driver of kidney decline",
        ],
        "medium": [
            "Monitor blood pressure regularly — target < 130/80 mmHg",
            "Maintain healthy blood sugar — diabetes is the second leading cause of kidney disease",
        ],
        "low": [
            "Stay hydrated and avoid chronic NSAID use",
            "Annual creatinine/eGFR check is appropriate",
        ],
    },
    "thyroid": {
        "high": [
            "Discuss TSH result with your doctor immediately — thyroid dysfunction requires clinical management",
            "Ensure adequate iodine (seafood, iodised salt) and selenium (Brazil nuts, eggs) intake",
            "Avoid excessive raw cruciferous vegetables (broccoli, kale) if hypothyroidism is suspected",
            "Recheck TSH in 6–8 weeks after any dietary or medication changes",
        ],
        "medium": [
            "Ensure adequate dietary iodine — deficiency is a common, correctable cause of thyroid dysfunction",
            "Reduce chronic stress, which can dysregulate the HPT axis",
        ],
        "low": [
            "Annual TSH screening is sufficient for low-risk individuals over 35",
        ],
    },
}


def generate_insights(integrated: dict) -> list[dict]:
    """
    Generate domain-level insights with confidence scores and lifestyle recommendations.

    Args:
        integrated: output of integration_engine.integrate()

    Returns:
        List of insight dicts sorted by priority (high → medium → low)
    """
    insights = []

    for domain, data in integrated.items():
        variants = data.get("variants", [])
        biomarkers = data.get("biomarkers", {})

        abnormal_markers = {
            k: v for k, v in biomarkers.items()
            if isinstance(v, dict) and v.get("status") != "normal"
        }

        has_risk_variants = len(variants) > 0
        has_abnormal_blood = len(abnormal_markers) > 0

        if has_risk_variants and has_abnormal_blood:
            confidence = "high"
        elif has_risk_variants or has_abnormal_blood:
            confidence = "medium"
        else:
            confidence = "low"

        recs = (
            DOMAIN_RECOMMENDATIONS.get(domain, {}).get(confidence)
            or DOMAIN_RECOMMENDATIONS.get(domain, {}).get("medium")
            or []
        )

        insights.append({
            "domain": domain,
            "confidence": confidence,
            "risk_variants": variants,
            "abnormal_biomarkers": abnormal_markers,
            "all_biomarkers": biomarkers,
            "recommendations": recs,
            "variant_count": len(variants),
            "abnormal_marker_count": len(abnormal_markers),
        })

    insights.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["confidence"]])
    return insights
