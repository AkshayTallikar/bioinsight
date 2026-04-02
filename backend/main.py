from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import genomics, blood, insights

app = FastAPI(title="BioInsight API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(genomics.router, prefix="/genomics", tags=["Genomics"])
app.include_router(blood.router, prefix="/blood", tags=["Blood"])
app.include_router(insights.router, prefix="/insights", tags=["Insights"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
