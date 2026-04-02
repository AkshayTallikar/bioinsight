"""
Open Targets Platform API integration.

Free, open GraphQL API — no auth required.
Endpoint: https://api.platform.opentargets.org/api/v4/graphql

Used to fetch disease associations and evidence scores for a given gene symbol.
Docs: https://platform-docs.opentargets.org/data-access/graphql-api
"""

from __future__ import annotations

import asyncio
import httpx

OPEN_TARGETS_GQL = "https://api.platform.opentargets.org/api/v4/graphql"

# Known gene symbol → Ensembl ID mappings for common clinically relevant genes
# Avoids a round-trip search query for well-known targets
KNOWN_GENE_IDS: dict[str, str] = {
    "APOE":    "ENSG00000130203",
    "MTHFR":   "ENSG00000177000",
    "FTO":     "ENSG00000140718",
    "PPARG":   "ENSG00000132170",
    "TCF7L2":  "ENSG00000148737",
    "HFE":     "ENSG00000010704",
    "SLCO1B1": "ENSG00000134538",
    "PON1":    "ENSG00000005421",
    "CYP2C9":  "ENSG00000138109",
    "CYP2C19": "ENSG00000165841",
    "BRCA1":   "ENSG00000012048",
    "BRCA2":   "ENSG00000139618",
    "TP53":    "ENSG00000141510",
    "LDLR":    "ENSG00000130164",
    "PCSK9":   "ENSG00000169174",
    "COMT":    "ENSG00000093010",
    "VDR":     "ENSG00000111424",
    "GC":      "ENSG00000145321",
    "MCM6":    "ENSG00000166508",
    "EDAR":    "ENSG00000135960",
}

SEARCH_QUERY = """
query SearchGene($symbol: String!) {
  search(queryString: $symbol, entityNames: ["target"], page: {index: 0, size: 1}) {
    hits {
      id
      name
    }
  }
}
"""

DISEASE_ASSOC_QUERY = """
query DiseaseAssociations($ensemblId: String!) {
  target(ensemblId: $ensemblId) {
    approvedSymbol
    approvedName
    associatedDiseases(page: {index: 0, size: 8}) {
      rows {
        disease {
          id
          name
          therapeuticAreas {
            name
          }
        }
        score
        datatypeScores {
          componentId
          score
        }
      }
    }
  }
}
"""


async def get_disease_associations(gene_symbols: list[str]) -> dict[str, list[dict]]:
    """
    Fetch disease associations from Open Targets for a list of gene symbols.

    Returns:
        {
            "APOE": [
                {
                    "disease": "Alzheimer disease",
                    "disease_id": "MONDO_0004975",
                    "score": 0.94,
                    "therapeutic_areas": ["neurology & psychiatry"],
                    "evidence_types": ["genetic associations", "literature"]
                },
                ...
            ],
            ...
        }
    """
    results: dict[str, list[dict]] = {}
    unique_genes = list(set(g for g in gene_symbols if g))

    async with httpx.AsyncClient(timeout=30) as client:
        tasks = [_fetch_gene_associations(client, gene) for gene in unique_genes]
        gene_results = await asyncio.gather(*tasks, return_exceptions=True)

    for gene, result in zip(unique_genes, gene_results):
        if isinstance(result, Exception) or not result:
            results[gene] = []
        else:
            results[gene] = result

    return results


async def _fetch_gene_associations(client: httpx.AsyncClient, gene_symbol: str) -> list[dict]:
    """Fetch disease associations for a single gene symbol."""
    ensembl_id = KNOWN_GENE_IDS.get(gene_symbol.upper())

    if not ensembl_id:
        ensembl_id = await _search_gene(client, gene_symbol)

    if not ensembl_id:
        return []

    return await _fetch_associations(client, ensembl_id)


async def _search_gene(client: httpx.AsyncClient, gene_symbol: str) -> str | None:
    """Search Open Targets for a gene symbol and return its Ensembl ID."""
    try:
        resp = await client.post(
            OPEN_TARGETS_GQL,
            json={"query": SEARCH_QUERY, "variables": {"symbol": gene_symbol}},
        )
        resp.raise_for_status()
        hits = resp.json().get("data", {}).get("search", {}).get("hits", [])
        if hits:
            return hits[0]["id"]
    except Exception:
        pass
    return None


async def _fetch_associations(client: httpx.AsyncClient, ensembl_id: str) -> list[dict]:
    """Fetch top disease associations for an Ensembl gene ID."""
    try:
        resp = await client.post(
            OPEN_TARGETS_GQL,
            json={"query": DISEASE_ASSOC_QUERY, "variables": {"ensemblId": ensembl_id}},
        )
        resp.raise_for_status()
        target = resp.json().get("data", {}).get("target", {})
        if not target:
            return []

        rows = target.get("associatedDiseases", {}).get("rows", [])
        parsed = []
        for row in rows:
            disease = row.get("disease", {})
            areas = [a["name"] for a in disease.get("therapeuticAreas", []) if a.get("name")]
            evidence_types = [
                d["componentId"].replace("_", " ")
                for d in row.get("datatypeScores", [])
                if d.get("score", 0) > 0.1
            ]
            parsed.append({
                "disease": disease.get("name", "Unknown"),
                "disease_id": disease.get("id", ""),
                "score": round(row.get("score", 0), 3),
                "therapeutic_areas": areas[:2],
                "evidence_types": evidence_types[:3],
            })

        return sorted(parsed, key=lambda x: x["score"], reverse=True)

    except Exception:
        return []
