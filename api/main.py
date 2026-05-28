import logging
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.repository import get_engine
from core.scheduler import create_scheduler
from api.routers.holdings import router as holdings_router
from api.routers.portfolio import router as portfolio_router
from api.routers.fx import router as fx_router
from api.routers.backtest import router as backtest_router
from api.routers.screener import router as screener_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

_scheduler = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    get_engine()
    _scheduler = create_scheduler()
    _scheduler.start()
    yield
    if _scheduler:
        _scheduler.shutdown()

app = FastAPI(title="Dudunomics API", lifespan=lifespan)

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3333").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(holdings_router)
app.include_router(portfolio_router)
app.include_router(fx_router)
app.include_router(backtest_router)
app.include_router(screener_router)

@app.get("/health")
def health():
    return {"status": "ok"}
