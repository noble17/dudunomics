# api/main.py — skeleton, fully implemented in Tasks 2-6
from fastapi import FastAPI

app = FastAPI(title="Dudunomics API")

@app.get("/health")
def health():
    return {"status": "ok"}
