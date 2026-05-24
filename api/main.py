from fastapi import FastAPI
from api.routers.holdings import router as holdings_router

app = FastAPI(title="Dudunomics API")

app.include_router(holdings_router)

@app.get("/health")
def health():
    return {"status": "ok"}
