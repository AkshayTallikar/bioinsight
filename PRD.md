# Product Requirements Document
**Product:** BioInsight — Biological Data Integration App
**Version:** 1.0
**Date:** 2026-04-02
**Status:** Draft

---

## 1. Problem Statement
Patients today receive genomic test results and blood lab results in isolation, with no easy way to see how their genetic predispositions interact with their current biomarker status. This makes it difficult for non-clinical users to make informed, personalized lifestyle decisions. There is no consumer-grade tool that integrates both data sources into actionable, plain-language health insights.

## 2. Product Vision
We are building BioInsight so that patients can upload their genomic data and connect their blood lab results to receive integrated, evidence-based lifestyle recommendations in one place.

## 3. Target Users & Personas

### Primary Persona: Health-Conscious Patient
- **Who:** Adult consumer, 25–55, proactively managing their health
- **Goals:** Understand how their genetics and blood markers interact; get actionable lifestyle guidance
- **Pain Points:** Genomic reports are hard to interpret; blood results come separately with no cross-reference; existing tools require clinical expertise
- **Technical Level:** Novice to intermediate — comfortable uploading files and connecting accounts, not bioinformatics-savvy

## 4. User Stories

### Must Have (P0)
- As a patient, I want to upload my 23andMe or VCF genomic file so that my variants can be analyzed
- As a patient, I want to connect my Quest Diagnostics account so that my blood lab results are pulled automatically
- As a patient, I want to see my health insights organized by domain (cardiovascular, metabolic, etc.) so that I can focus on areas most relevant to me
- As a patient, I want to see which genetic variants and blood markers are driving each insight so that I trust the recommendation
- As a patient, I want lifestyle recommendations (diet, exercise, supplements) based on my combined data so that I know what to act on
- As a patient, I want to know the confidence level of each insight so that I understand how strong the evidence is

### Should Have (P1)
- As a patient, I want to see when my Quest data was last synced so that I know if it's current
- As a patient, I want to manually enter blood marker values if I don't have Quest access
- As a patient, I want insights explained in plain language without clinical jargon

### Nice to Have (P2)
- As a patient, I want to log in with Google so that my data persists across sessions
- As a patient, I want trend graphs showing how my blood markers change over time
- As a patient, I want to share a summary report with my doctor

## 5. Functional Requirements

### Core Features
| # | Feature | Description | Priority |
|---|---------|-------------|----------|
| F1 | Genomic File Upload | Accept 23andMe .txt and VCF files; parse and extract SNP/variant rs# IDs | P0 |
| F2 | ClinVar Enrichment | Query NCBI ClinVar API per variant to retrieve clinical significance and trait associations | P0 |
| F3 | Quest FHIR Integration | OAuth 2.0 connection to Quest Diagnostics; pull DiagnosticReport + Observation FHIR resources | P0 |
| F4 | Biomarker Normalization | Map LOINC codes to standard marker names; apply reference ranges for low/normal/high flagging | P0 |
| F5 | Integration Engine | Cross-reference genetic predispositions with current blood biomarker values per health domain | P0 |
| F6 | Insight Generator | Produce ranked, confidence-scored lifestyle recommendations from integrated data | P0 |
| F7 | Patient Dashboard | Display health domain cards, insight details, and recommendations in plain language | P0 |
| F8 | Data Freshness Indicator | Show last-synced timestamp for Quest data and upload date for genomic file | P1 |
| F9 | Manual Blood Entry | Allow manual input of blood marker values as fallback | P1 |
| F10 | Google OAuth Login | Persist user session and data across visits | P2 |

### User Flows

**Happy Path: Full Integration**
1. User lands on dashboard
2. User uploads 23andMe `.txt` or `.vcf` file
3. System parses variants, queries ClinVar for each rs# ID
4. User clicks "Connect Quest Diagnostics"
5. System initiates Quest OAuth 2.0 flow; user authenticates
6. System pulls latest DiagnosticReport via FHIR R4 API
7. System normalizes LOINC-coded observations to standard biomarker names
8. Integration Engine correlates genetic risks with blood marker values
9. Insight Generator produces domain-grouped, confidence-scored recommendations
10. Dashboard renders health domain cards with insights and lifestyle actions

**Fallback Path: File Upload Only**
1. User uploads genomic file only
2. ClinVar enrichment runs
3. Partial insights shown (genetic predisposition only, no blood correlation)
4. Prompt shown to connect Quest or enter blood values manually

## 6. Non-Functional Requirements
- **Performance:** Dashboard loads in < 3s; ClinVar API calls batched to avoid rate limits
- **Security:** No patient data stored server-side in v1 (session-only); Quest OAuth tokens never logged
- **Scalability:** Demo scale — single user session, no multi-tenancy required in v1
- **Accessibility:** Readable color contrast; no color-only status indicators
- **Platform Support:** Web (Chrome, Firefox, Safari); desktop browser only in v1

## 7. Technical Recommendations

### Stack
- **Frontend:** Streamlit — rapid prototyping, Python-native, no JS required
- **Backend:** FastAPI — async, typed, OpenAPI docs auto-generated
- **Database:** None in v1 (session state only); SQLite for v2 if persistence added
- **Auth:** Google OAuth 2.0 (v2 feature)
- **Hosting:** Local / demo environment in v1

### External APIs
| API | Purpose | Auth |
|-----|---------|------|
| NCBI ClinVar (NIH) | Variant → clinical significance + trait | None (free, rate-limited) |
| Quest Diagnostics FHIR R4 | Blood lab results (DiagnosticReport, Observation) | OAuth 2.0 |

### Key Technical Decisions
1. **File-based genomic input** — avoids 23andMe API partnership requirements; users export raw data directly
2. **ClinVar E-utilities / REST** — free, no key required; batch rs# lookups to stay within rate limits (3 req/s unauthenticated, 10/s with API key)
3. **FHIR R4 DiagnosticReport** — Quest returns LOINC-coded Observations; normalize via LOINC-to-name mapping table
4. **Session-only data** — no persistence in v1; data lives in Streamlit session state to avoid storage/security complexity

## 8. Success Metrics
| Metric | Baseline | Target | Timeframe |
|--------|----------|--------|-----------|
| File parse success rate | 0% | > 95% | Demo |
| ClinVar lookup coverage | 0% | > 80% of uploaded variants return results | Demo |
| End-to-end flow completion | 0% | User reaches insight dashboard | Demo |
| Insight generation time | — | < 10s for full pipeline | Demo |

## 9. Out of Scope (v1)
- User authentication and persistent accounts (v2: Google OAuth)
- De novo variant calling or FASTQ processing
- Drug interaction lookups
- Multi-patient / cohort views
- Mobile app
- PDF report export
- EHR integrations (Epic, Cerner)
- Non-Quest lab sources (LabCorp, etc.)
- HIPAA compliance (demo only, no real patient data)

## 10. Open Questions
- What NCBI API key will be used to increase ClinVar rate limits to 10 req/s?
- Does the demo use real Quest credentials or a Quest sandbox environment?
- What health domains should be covered in v1? (suggested: cardiovascular, metabolic, inflammation, nutrition)
- How many variants does a typical 23andMe file contain? (~600k SNPs — need a filtering strategy to only process clinically relevant ones)

## 11. Milestones
| Milestone | Description | Target |
|-----------|-------------|--------|
| M1 | FastAPI backend scaffold + file parser + ClinVar integration | Week 1 |
| M2 | Quest FHIR OAuth + biomarker normalization | Week 2 |
| M3 | Integration engine + insight generator | Week 3 |
| M4 | Streamlit dashboard + end-to-end demo flow | Week 4 |
