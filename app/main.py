from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.datasets import router as datasets_router
from app.api.deep import router as deep_router
from app.api.publication import router as publication_router
from app.api.models import router as models_router
from app.api.predictions import router as predictions_router
from app.api.system import router as system_router
from app.core.model_cache import warm_up_all_models, warm_up_lgbm_models, warm_up_prediction_caches
from app.core.storage import ensure_storage_dirs
from app.core.r2 import download_from_r2


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: warm up all caches before serving requests.

    Execution order:
    1. LightGBM boosters  (parallel, fast I/O)
    2. TFT models         (parallel, fast I/O after imports)
    3. Prediction caches  (feature frames for all tiers — heaviest step)
    """
    ensure_storage_dirs()
    download_from_r2()
    warm_up_lgbm_models()
    warm_up_all_models()
    warm_up_prediction_caches()
    yield
    # (クリーンアップが必要な場合はここに記述)


def create_app() -> FastAPI:
    is_prod = os.getenv("ENV", "development").lower() == "production"

    app = FastAPI(
        title="Border Analysis API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
    )

    if is_prod:
        @app.middleware("http")
        async def block_admin_endpoints(request: Request, call_next):
            path = request.url.path
            blocked_prefixes = ("/datasets", "/models", "/publication", "/deep/train")
            if any(path.startswith(prefix) for prefix in blocked_prefixes):
                return JSONResponse(status_code=404, content={"detail": "Not Found"})
            return await call_next(request)

    # Next.js 開発サーバーからの通信を許可するCORS設定
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(datasets_router)
    app.include_router(deep_router)
    app.include_router(publication_router)
    app.include_router(models_router)
    app.include_router(predictions_router)
    app.include_router(system_router)

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/ui", StaticFiles(directory=static_dir, html=True), name="ui")

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/ui/")

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


# Trigger reload to warm up cache with retrained models
app = create_app()
