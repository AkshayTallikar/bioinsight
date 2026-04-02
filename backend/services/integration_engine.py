"""
Integration Engine — correlates ClinVar-enriched genetic variants with
normalized blood biomarker values, grouped by health domain.
"""

# Maps genetic traits (from ClinVar) and biomarkers to health domains
DOMAIN_TRAIT_MAP = {
    "cardiovascular": {
        "traits": ["coronary artery disease", "heart disease", "hypertension", "atrial fibrillation", "stroke"],
        "biomarkers": ["LDL Cholesterol", "HDL Cholesterol", "Total Cholesterol", "Triglycerides", "CRP (C-Reactive Protein)"],
    },
    "metabolic": {
        "traits": ["type 2 diabetes", "insulin resistance", "obesity", "metabolic syndrome"],
        "biomarkers": ["HbA1c", "Blood Glucose", "Triglycerides"],
    },
    "inflammation": {
        "traits": ["inflammatory bowel disease", "rheumatoid arthritis", "autoimmune"],
        "biomarkers": ["CRP (C-Reactive Protein)", "White Blood Cell Count"],
    },
    "nutrition": {
        "traits": ["folate metabolism", "vitamin d deficiency", "iron deficiency", "b12 deficiency"],
        "biomarkers": ["Vitamin D (25-OH)", "Vitamin B12", "Ferritin", "Hemoglobin"],
    },
    "liver": {
        "traits": ["non-alcoholic fatty liver", "liver disease"],
        "biomarkers": ["ALT", "AST", "Alkaline Phosphatase"],
    },
    "kidney": {
        "traits": ["chronic kidney disease", "renal disease"],
        "biomarkers": ["Creatinine", "BUN", "Sodium", "Potassium"],
    },
    "thyroid": {
        "traits": ["hypothyroidism", "hyperthyroidism", "thyroid disease"],
        "biomarkers": ["TSH"],
    },
}


def integrate(enriched_variants: list[dict], biomarkers: dict[str, dict]) -> dict:
    """
    Group genetic variants and blood biomarkers by health domain.

    Returns a domain-keyed dict with relevant variants and biomarker signals.
    """
    integrated = {domain: {"variants": [], "biomarkers": {}} for domain in DOMAIN_TRAIT_MAP}

    for variant in enriched_variants:
        clinvar = variant.get("clinvar", {})
        traits = [t.lower() for t in clinvar.get("traits", [])]
        significance = clinvar.get("clinical_significance", "unknown").lower()

        if significance in ("benign", "likely benign"):
            continue

        for domain, mapping in DOMAIN_TRAIT_MAP.items():
            if any(kw in trait for kw in mapping["traits"] for trait in traits):
                integrated[domain]["variants"].append({
                    "rsid": variant["rsid"],
                    "gene": clinvar.get("gene", ""),
                    "significance": clinvar.get("clinical_significance", ""),
                    "traits": clinvar.get("traits", []),
                })

    for domain, mapping in DOMAIN_TRAIT_MAP.items():
        for marker_name in mapping["biomarkers"]:
            if marker_name in biomarkers:
                integrated[domain]["biomarkers"][marker_name] = biomarkers[marker_name]

    return {d: v for d, v in integrated.items() if v["variants"] or v["biomarkers"]}
