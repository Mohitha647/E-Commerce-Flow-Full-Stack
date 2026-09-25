from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import init_db
from app.routers import auth, cart, orders, products, recommendations
from app.seed import seed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("commerceflow")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed()
    logger.info("Database initialized (%s)", settings.database_url.split("://")[0])
    yield


FRONTEND_DIR = __import__("pathlib").Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(
    title=settings.app_name,
    description="Distributed full-stack commerce platform: catalog, cart, concurrency-safe checkout, caching, recommendations.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(recommendations.router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api", tags=["health"])
async def api_info():
    return {
        "message": f"{settings.app_name} API is running.",
        "docs": "/docs",
        "endpoints": ["/auth", "/products", "/cart", "/orders", "/recommendations"],
    }
