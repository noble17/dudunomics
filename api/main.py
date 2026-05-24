from fastapi import FastAPI
from api.routers.holdings import router as holdings_router
from api.routers.portfolio import router as portfolio_router
from api.routers.fx import router as fx_router
from api.routers.backtest import router as backtest_router

app = FastAPI(title="Dudunomics API")

app.include_router(holdings_router)
app.include_router(portfolio_router)
app.include_router(fx_router)
app.include_router(backtest_router)

@app.get("/health")
def health():
    return {"status": "ok"}
