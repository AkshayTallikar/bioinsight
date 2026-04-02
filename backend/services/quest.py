"""
Quest Diagnostics FHIR R4 integration.

Flow:
  1. User is redirected to Quest OAuth 2.0 authorization URL
  2. Quest redirects back with ?code=...
  3. exchange_code_for_token() swaps code for access token
  4. fetch_diagnostic_reports() pulls FHIR DiagnosticReport + Observation resources
"""

import os
import httpx

QUEST_CLIENT_ID = os.getenv("QUEST_CLIENT_ID", "")
QUEST_CLIENT_SECRET = os.getenv("QUEST_CLIENT_SECRET", "")
QUEST_TOKEN_URL = os.getenv("QUEST_TOKEN_URL", "https://oauth.questdiagnostics.com/token")
QUEST_FHIR_BASE = os.getenv("QUEST_FHIR_BASE", "https://api.questdiagnostics.com/fhir/r4")
REDIRECT_URI = os.getenv("QUEST_REDIRECT_URI", "http://localhost:8000/blood/quest/callback")


async def exchange_code_for_token(code: str) -> str:
    """Exchange authorization code for Quest access token."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            QUEST_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": QUEST_CLIENT_ID,
                "client_secret": QUEST_CLIENT_SECRET,
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def fetch_diagnostic_reports(token: str) -> list[dict]:
    """
    Fetch the latest DiagnosticReport bundle from Quest FHIR R4.
    Returns a list of Observation resources from within each report.
    """
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/fhir+json"}
    observations = []

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{QUEST_FHIR_BASE}/DiagnosticReport",
            headers=headers,
            params={"_include": "DiagnosticReport:result", "_count": 10, "_sort": "-date"},
        )
        resp.raise_for_status()
        bundle = resp.json()

        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            if resource.get("resourceType") == "Observation":
                observations.append(resource)

    return observations
