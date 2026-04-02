"""
Disease Risk Engine.

Combines:
  1. Open Targets disease association scores (genetic evidence)
  2. Blood biomarker abnormalities (clinical evidence)
  3. Known SNP-to-disease curated mappings (high-confidence overrides)

Produces a ranked list of disease risks with contributing factors.
"""

from __future__ import annotations

from services.open_targets import get_disease_associations

# High-confidence curated SNP → disease risk mappings
# Based on well-established GWAS / ClinVar pathogenic classifications
CURATED_SNP_RISKS: dict[str, dict] = {
    # APOE ε4 allele — Alzheimer's & cardiovascular
    "rs429358": {
        "gene": "APOE",
        "diseases": ["Alzheimer disease", "Coronary artery disease", "Hyperlipoproteinemia"],
        "risk_allele": "C",
        "notes": "APOE ε4 — strongest known genetic risk factor for late-onset Alzheimer's",
    },
    "rs7412": {
        "gene": "APOE",
        "diseases": ["Alzheimer disease", "Hypercholesterolemia"],
        "risk_allele": "C",
        "notes": "APOE ε2/ε4 haplotype determinant",
    },
    # MTHFR — cardiovascular, neural tube defects, folate metabolism
    "rs1801133": {
        "gene": "MTHFR",
        "diseases": ["Homocystinuria", "Neural tube defects", "Cardiovascular disease"],
        "risk_allele": "A",
        "notes": "MTHFR C677T — reduces enzyme activity ~70% in TT homozygotes",
    },
    "rs1801131": {
        "gene": "MTHFR",
        "diseases": ["Hyperhomocysteinemia", "Cardiovascular disease"],
        "risk_allele": "C",
        "notes": "MTHFR A1298C — compound heterozygote with C677T increases risk",
    },
    # FTO — obesity, Type 2 diabetes
    "rs9939609": {
        "gene": "FTO",
        "diseases": ["Obesity", "Type 2 diabetes mellitus"],
        "risk_allele": "A",
        "notes": "Each A allele increases BMI by ~0.4 kg/m² on average",
    },
    # TCF7L2 — strongest T2D GWAS signal
    "rs7903146": {
        "gene": "TCF7L2",
        "diseases": ["Type 2 diabetes mellitus"],
        "risk_allele": "T",
        "notes": "Strongest replicated T2D GWAS variant — disrupts Wnt signaling in pancreatic beta cells",
    },
    # HFE — hereditary hemochromatosis
    "rs1800562": {
        "gene": "HFE",
        "diseases": ["Hereditary hemochromatosis", "Iron overload disorder"],
        "risk_allele": "A",
        "notes": "HFE C282Y — most common hemochromatosis mutation in Northern Europeans",
    },
    "rs1799945": {
        "gene": "HFE",
        "diseases": ["Hereditary hemochromatosis"],
        "risk_allele": "G",
        "notes": "HFE H63D — mild hemochromatosis risk, especially compound heterozygote",
    },
    # SLCO1B1 — statin-induced myopathy
    "rs4149056": {
        "gene": "SLCO1B1",
        "diseases": ["Statin-induced myopathy", "Simvastatin toxicity"],
        "risk_allele": "C",
        "notes": "Reduces statin clearance — *5 allele; dose adjustment recommended",
    },
    # PON1 — cardiovascular
    "rs662": {
        "gene": "PON1",
        "diseases": ["Coronary artery disease", "Atherosclerosis"],
        "risk_allele": "A",
        "notes": "PON1 Q192R — reduces HDL-associated antioxidant activity",
    },
    # CYP2C9 / CYP2C19 — drug metabolism
    "rs1799853": {
        "gene": "CYP2C9",
        "diseases": ["Warfarin sensitivity", "NSAID toxicity"],
        "risk_allele": "T",
        "notes": "CYP2C9 *2 — poor metabolizer; requires warfarin dose reduction",
    },
    "rs1057910": {
        "gene": "CYP2C9",
        "diseases": ["Warfarin sensitivity"],
        "risk_allele": "A",
        "notes": "CYP2C9 *3 — strongest poor metabolizer allele",
    },
    # PPARG — insulin resistance
    "rs1801282": {
        "gene": "PPARG",
        "diseases": ["Type 2 diabetes mellitus", "Insulin resistance", "Obesity"],
        "risk_allele": "C",
        "notes": "PPARG Pro12Ala — protective G allele reduces T2D risk ~20%",
    },
    # TP53 — cancer susceptibility
    "rs1042522": {
        "gene": "TP53",
        "diseases": ["Various cancers", "Li-Fraumeni syndrome"],
        "risk_allele": "G",
        "notes": "TP53 Arg72Pro — modulates apoptosis efficiency; cancer susceptibility modifier",
    },
    # BRCA1/2 — breast/ovarian cancer
    "rs80357906": {
        "gene": "BRCA1",
        "diseases": ["Breast cancer", "Ovarian cancer"],
        "risk_allele": "A",
        "notes": "BRCA1 pathogenic variant — substantially elevated breast and ovarian cancer risk",
    },
    "rs28897672": {
        "gene": "BRCA2",
        "diseases": ["Breast cancer", "Pancreatic cancer"],
        "risk_allele": "A",
        "notes": "BRCA2 pathogenic variant — elevated breast and pancreatic cancer risk",
    },
    # VDR — vitamin D receptor
    "rs731236": {
        "gene": "VDR",
        "diseases": ["Vitamin D deficiency", "Osteoporosis", "Multiple sclerosis"],
        "risk_allele": "A",
        "notes": "VDR TaqI polymorphism — affects vitamin D receptor function",
    },
    # Colon cancer
    "rs6983267": {
        "gene": "CCAT2",
        "diseases": ["Colorectal cancer"],
        "risk_allele": "G",
        "notes": "8q24 locus — most replicated colorectal cancer GWAS signal",
    },
    # Vitamin D synthesis
    "rs10741657": {
        "gene": "CYP2R1",
        "diseases": ["Vitamin D deficiency", "Rickets"],
        "risk_allele": "A",
        "notes": "CYP2R1 — 25-hydroxylase; reduces vitamin D conversion efficiency",
    },
    "rs2282679": {
        "gene": "GC",
        "diseases": ["Vitamin D deficiency"],
        "risk_allele": "C",
        "notes": "Vitamin D binding protein gene — reduces circulating 25(OH)D levels",
    },
}

# Biomarker patterns that amplify disease risk signals
BIOMARKER_DISEASE_AMPLIFIERS: dict[str, list[str]] = {
    "LDL Cholesterol":             ["Coronary artery disease", "Atherosclerosis", "Hypercholesterolemia"],
    "HDL Cholesterol":             ["Coronary artery disease", "Atherosclerosis"],
    "Total Cholesterol":           ["Coronary artery disease", "Hyperlipoproteinemia"],
    "Triglycerides":               ["Coronary artery disease", "Type 2 diabetes mellitus", "Obesity"],
    "HbA1c":                       ["Type 2 diabetes mellitus", "Insulin resistance"],
    "Blood Glucose":               ["Type 2 diabetes mellitus", "Insulin resistance"],
    "CRP (C-Reactive Protein)":    ["Coronary artery disease", "Inflammatory bowel disease", "Atherosclerosis"],
    "Ferritin":                    ["Iron overload disorder", "Hereditary hemochromatosis"],
    "Hemoglobin":                  ["Iron deficiency anemia"],
    "Vitamin D (25-OH)":           ["Vitamin D deficiency", "Osteoporosis"],
    "Vitamin B12":                 ["Hyperhomocysteinemia", "Neural tube defects"],
    "ALT":                         ["Non-alcoholic fatty liver disease", "Liver disease"],
    "AST":                         ["Non-alcoholic fatty liver disease", "Liver disease"],
    "TSH":                         ["Hypothyroidism", "Hyperthyroidism"],
    "Creatinine":                  ["Chronic kidney disease"],
    "White Blood Cell Count":      ["Infection", "Inflammatory disease"],
}


async def compute_disease_risks(
    enriched_variants: list[dict],
    biomarkers: dict[str, dict],
) -> list[dict]:
    """
    Compute a ranked disease risk list from genetic variants and blood markers.

    Steps:
      1. Extract unique gene symbols from enriched variants
      2. Fetch Open Targets disease associations for each gene
      3. Cross-reference with curated SNP risk table
      4. Amplify scores where blood biomarkers support the same disease
      5. Return ranked, deduplicated disease risk list
    """
    disease_scores: dict[str, dict] = {}

    # --- Step 1 & 2: Open Targets lookup ---
    gene_symbols = list({
        v.get("clinvar", {}).get("gene", "")
        for v in enriched_variants
        if v.get("clinvar", {}).get("gene")
    })

    ot_associations = {}
    if gene_symbols:
        ot_associations = await get_disease_associations(gene_symbols)

    # --- Step 3: Score from Open Targets ---
    for gene, associations in ot_associations.items():
        for assoc in associations:
            disease = assoc["disease"]
            existing = disease_scores.get(disease, {
                "disease": disease,
                "disease_id": assoc.get("disease_id", ""),
                "genetic_score": 0.0,
                "blood_score": 0.0,
                "contributing_genes": [],
                "contributing_variants": [],
                "contributing_biomarkers": [],
                "therapeutic_areas": assoc.get("therapeutic_areas", []),
                "evidence_types": set(),
                "curated_notes": [],
            })
            existing["genetic_score"] = max(existing["genetic_score"], assoc["score"])
            if gene not in existing["contributing_genes"]:
                existing["contributing_genes"].append(gene)
            for et in assoc.get("evidence_types", []):
                existing["evidence_types"].add(et)
            disease_scores[disease] = existing

    # --- Step 4: Curated SNP overrides ---
    for variant in enriched_variants:
        rsid = variant.get("rsid", "")
        curated = CURATED_SNP_RISKS.get(rsid)
        if not curated:
            continue
        for disease in curated["diseases"]:
            existing = disease_scores.get(disease, {
                "disease": disease,
                "disease_id": "",
                "genetic_score": 0.0,
                "blood_score": 0.0,
                "contributing_genes": [],
                "contributing_variants": [],
                "contributing_biomarkers": [],
                "therapeutic_areas": [],
                "evidence_types": set(),
                "curated_notes": [],
            })
            existing["genetic_score"] = max(existing["genetic_score"], 0.75)
            if curated["gene"] not in existing["contributing_genes"]:
                existing["contributing_genes"].append(curated["gene"])
            if rsid not in existing["contributing_variants"]:
                existing["contributing_variants"].append(rsid)
            existing["evidence_types"].add("curated SNP association")
            note = curated.get("notes", "")
            if note and note not in existing["curated_notes"]:
                existing["curated_notes"].append(note)
            disease_scores[disease] = existing

    # --- Step 5: Blood biomarker amplification ---
    abnormal = {k: v for k, v in biomarkers.items() if isinstance(v, dict) and v.get("status") != "normal"}
    for marker, info in abnormal.items():
        amplified_diseases = BIOMARKER_DISEASE_AMPLIFIERS.get(marker, [])
        for disease in amplified_diseases:
            if disease in disease_scores:
                entry = disease_scores[disease]
                entry["blood_score"] = min(entry["blood_score"] + 0.2, 1.0)
                if marker not in entry["contributing_biomarkers"]:
                    entry["contributing_biomarkers"].append(marker)
                entry["evidence_types"].add("blood biomarker")

    # --- Step 6: Compute final score + risk level ---
    output = []
    for disease, entry in disease_scores.items():
        g = entry["genetic_score"]
        b = entry["blood_score"]
        combined = round(min(g * 0.65 + b * 0.35, 1.0), 3)

        if combined >= 0.7:
            risk_level = "high"
        elif combined >= 0.4:
            risk_level = "moderate"
        else:
            risk_level = "low"

        output.append({
            "disease": entry["disease"],
            "disease_id": entry["disease_id"],
            "risk_level": risk_level,
            "combined_score": combined,
            "genetic_score": round(g, 3),
            "blood_score": round(b, 3),
            "contributing_genes": entry["contributing_genes"][:5],
            "contributing_variants": entry["contributing_variants"][:5],
            "contributing_biomarkers": entry["contributing_biomarkers"][:5],
            "therapeutic_areas": entry["therapeutic_areas"][:2],
            "evidence_types": sorted(entry["evidence_types"])[:4],
            "curated_notes": entry["curated_notes"][:2],
        })

    output.sort(key=lambda x: x["combined_score"], reverse=True)
    return output[:20]
