from fastapi import FastAPI
from api.routers.holdings import router as holdings_router
from api.routers.portfolio import router as portfolio_router

app = FastAPI(title="Dudunomics API")

app.include_router(holdings_router)
app.include_router(portfolio_router)

@app.get("/health")
def health():
    return {"status": "ok"}
