Subject: Thank You + BioInsight POC — From Design to Deployment

---

Hi [Interviewer Name],

Thank you for the time and the opportunity — I genuinely enjoyed the conversation and the challenge you put in front of me.

I wanted to follow up by sharing something I built as a direct result of it.

---

**BioInsight — Live App**
🔗 https://bioinsight-frontend.fly.dev

---

**What it does**

BioInsight is a biological data integration tool that takes two inputs most people already have access to — a genomic file (23andMe export or VCF) and a standard blood lab report (CSV) — and turns them into actionable health insights.

Under the hood it:
- Parses genomic variants and maps them to clinical significance via the NCBI ClinVar API
- Scores disease risk across 7 health domains (cardiovascular, metabolic, inflammation, liver, kidney, nutrition, thyroid) by cross-referencing Open Targets Platform's GraphQL API and a curated SNP risk table
- Amplifies genetic risk scores using blood biomarker data (e.g. high LDL + APOE ε3/ε4 → elevated cardiovascular risk)
- Generates plain-language lifestyle recommendations ranked by confidence level

---

**How I built it — Design to Deployment**

The process moved through four phases:

1. **System Design**
   Started by mapping the data sources, APIs, and failure modes before writing a line of code. Chose FastAPI for the backend (async, typed, auto-documented) and Streamlit for the frontend (rapid iteration, no JS overhead for a POC). Defined the integration contract early: genomic variants + blood markers → domain risk scores → recommendations.

2. **Backend Development**
   Built a modular Python backend with dedicated parsers (genomic + blood), service layers (ClinVar, Open Targets, integration engine, insight generator), and REST endpoints. Handled edge cases explicitly — wrong file types, encoding errors, API timeouts, partial data — so the app degrades gracefully rather than crashing.

3. **Frontend Development**
   Three-tab Streamlit UI: Upload → Insights → Disease Risk. Added sample file downloads so anyone can test it immediately. Built session-state-aware error handling so intermittent server errors surface as readable messages rather than raw stack traces.

4. **Deployment**
   - Backend: Railway (auto-deploys from GitHub, configured via `railway.json`)
   - Frontend: Fly.io (always-on Docker container, `min_machines_running=1` to prevent session expiry on file uploads)
   - Environment secrets managed separately from code

Total time from blank repo to live URL: one focused session.

---

**How I used AI in this process**

I used Claude as an engineering collaborator throughout — not as a code generator I blindly accepted output from, but as a thinking partner I directed and corrected.

Specifically:
- I drove the system design decisions (which APIs, which architecture, what tradeoffs)
- I used AI to accelerate the implementation of well-defined modules — parsers, API clients, scoring logic
- When things broke (Python 3.9 type hint incompatibilities, a ClinVar API format change mid-build, Fly.io session expiry bugs, Railway GraphQL auth issues), I diagnosed the root cause myself and directed the fix
- I reviewed every piece of generated code for correctness before it went in

The result is code I understand and can defend, not a black box. I think that's the right way to use these tools — AI handles the mechanical parts faster than any human can type; the engineer stays responsible for the decisions.

---

**A note on this being a POC**

This is a proof of concept, not a production medical tool. A few known limitations worth flagging:

- ClinVar and Open Targets data is publicly available research-grade data — it's not a substitute for clinical interpretation
- The disease risk scores are heuristic (weighted combinations of evidence scores and curated tables), not validated clinical models
- Quest Diagnostics OAuth integration is stubbed — it would require a real API key agreement with Quest to activate
- No authentication layer yet — this is open to anyone with the link
- There may be edge cases in file parsing that haven't been caught yet

I'd add auth (Google OAuth), rate limiting, and proper medical disclaimers before treating this as anything more than a technical demonstration.

---

Happy to walk through any part of it in more detail — the architecture, the scoring model, the deployment setup, or anything else. And again, thank you for the time.

Best,
Akshay Tallikar
