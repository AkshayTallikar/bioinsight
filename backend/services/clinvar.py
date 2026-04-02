"""
NCBI ClinVar enrichment service.

Uses NIH Clinical Table Search Service — a cleaner REST endpoint that returns
phenotypes and clinical significance per variant rs# ID.

Endpoint: https://clinicaltables.nlm.nih.gov/api/variants/v4/search
Docs:     https://clinicaltables.nlm.nih.gov/apidoc/variants/v4/doc.html

Rate limit: generous (NIH public API, no key needed for demo scale)
"""

from __future__ import annotations

import asyncio
import httpx

CTS_BASE = "https://clinicaltables.nlm.nih.gov/api/variants/v4/search"
BATCH_SIZE = 1          # CTS searches one rs# at a time
REQUEST_DELAY = 0.2     # seconds between requests
FIELDS = "phenotypes,clinical_sig_simple,gene_symbols,hgnc_ids"

# Curated rs# → gene fallback (CTS gene_symbols field is often empty)
RSID_GENE_MAP: dict[str, str] = {
    "rs429358": "APOE", "rs7412": "APOE",
    "rs1801133": "MTHFR", "rs1801131": "MTHFR",
    "rs9939609": "FTO", "rs17817449": "FTO",
    "rs1801282": "PPARG", "rs7903146": "TCF7L2",
    "rs1800562": "HFE", "rs1799945": "HFE",
    "rs4149056": "SLCO1B1", "rs662": "PON1",
    "rs1799853": "CYP2C9", "rs1057910": "CYP2C9",
    "rs5082": "APOA2", "rs4988235": "MCM6",
    "rs1800497": "ANKK1", "rs6983267": "CCAT2",
    "rs1447295": "MYC", "rs1695": "GSTP1",
    "rs1800629": "TNF", "rs17822931": "ABCC11",
    "rs1805009": "MC1R", "rs1801394": "MTRR",
    "rs2282679": "GC", "rs12785878": "DHCR7",
    "rs10741657": "CYP2R1", "rs1544410": "VDR",
    "rs731236": "VDR", "rs4516035": "BRCA1",
    "rs80357906": "BRCA1", "rs28897672": "BRCA2",
    "rs3218536": "BRCA2", "rs1042522": "TP53",
    "rs2395029": "HCP5",
}


async def lookup_variants(variants: list[dict]) -> list[dict]:
    """Enrich a list of variant dicts with ClinVar phenotype + significance data."""
    enriched = []
    async with httpx.AsyncClient(timeout=20) as client:
        for i, variant in enumerate(variants):
            rsid = variant.get("rsid", "")
            if not rsid.startswith("rs"):
                variant["clinvar"] = {}
                enriched.append(variant)
                continue

            data = await _lookup_rsid(client, rsid)
            variant["clinvar"] = data
            enriched.append(variant)

            if i < len(variants) - 1:
                await asyncio.sleep(REQUEST_DELAY)

    return enriched


async def _lookup_rsid(client: httpx.AsyncClient, rsid: str) -> dict:
    """Query CTS for a single rs# and return parsed ClinVar data."""
    try:
        resp = await client.get(
            CTS_BASE,
            params={
                "terms": rsid,
                "df": FIELDS,
                "maxList": 5,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        result = _parse_cts_response(data, rsid)
        # Fill gene from curated map if CTS returned empty
        if not result.get("gene"):
            result["gene"] = RSID_GENE_MAP.get(rsid, "")
        return result
    except Exception:
        # Still try to return gene from curated map even if API fails
        gene = RSID_GENE_MAP.get(rsid, "")
        return {"gene": gene, "traits": [], "clinical_significance": "Unknown"} if gene else {}


def _parse_cts_response(data: list, rsid: str) -> dict:
    """
    Parse Clinical Table Search Service response.

    Response format: [total, [ids], null, [[field1, field2, ...], ...]]
    Fields order: phenotypes, clinical_sig_simple, gene_symbols, hgnc_ids
    """
    if not data or not isinstance(data, list) or len(data) < 4:
        return {}

    rows = data[3]
    if not rows:
        return {}

    # Aggregate across all matching ClinVar entries for this rs#
    all_traits: list[str] = []
    all_sigs: list[str] = []
    gene = ""

    for row in rows:
        if not row or len(row) < 3:
            continue

        phenotype_str = row[0] if len(row) > 0 else ""
        sig_str       = row[1] if len(row) > 1 else ""
        gene_str      = row[2] if len(row) > 2 else ""

        # Phenotypes: "C1863051-Alzheimer disease 2,C0002395-Alzheimer disease,..."
        if phenotype_str:
            for part in phenotype_str.split(","):
                part = part.strip()
                if "-" in part:
                    trait_name = part.split("-", 1)[1].strip()
                    if (
                        trait_name
                        and trait_name.lower() not in ("not specified", "not provided", "see cases")
                        and trait_name not in all_traits
                    ):
                        all_traits.append(trait_name)

        # Clinical significance
        if sig_str and sig_str not in all_sigs:
            all_sigs.append(sig_str)

        # Gene symbol (take first non-empty)
        if gene_str and not gene:
            gene = gene_str.split(",")[0].strip()

    if not all_traits and not gene:  # type: ignore
        return {}

    # Pick the most severe significance reported
    sig = _resolve_significance(all_sigs)

    return {
        "clinical_significance": sig,
        "traits": all_traits[:6],
        "gene": gene,
    }


def _resolve_significance(sigs: list[str]) -> str:
    """Return the most clinically relevant significance from a list."""
    priority = [
        "pathogenic",
        "likely pathogenic",
        "pathogenic/likely pathogenic",
        "risk factor",
        "uncertain significance",
        "likely benign",
        "benign",
    ]
    sigs_lower = [s.lower() for s in sigs]
    for p in priority:
        for s in sigs_lower:
            if p in s:
                return p.title()
    return sigs[0].title() if sigs else "Unknown"
