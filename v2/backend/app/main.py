from pathlib import Path
import hashlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.core.config import settings
from app.routers import auth_router, products_router, prices_router, policies_router, st_rebates_router
from app.routers.bootstrap import router as bootstrap_router
from app.routers.price_overview import router as price_overview_router
from app.routers.backups import router as backups_router

app = FastAPI(title=settings.app_name, version="1.0.0")

if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )

app.include_router(auth_router, prefix="/api/auth", tags=["认证与成员"])
app.include_router(products_router, prefix="/api/products", tags=["商品档案"])
app.include_router(prices_router, prefix="/api", tags=["价格档案"])
app.include_router(policies_router, prefix="/api/policies", tags=["月度政策价"])
app.include_router(st_rebates_router, prefix="/api", tags=["ST返利档案"])
app.include_router(price_overview_router, prefix="/api", tags=["价格总览"])
app.include_router(bootstrap_router, prefix="/api/bootstrap", tags=["初始化"])
app.include_router(backups_router, prefix="/api/backups", tags=["备份管理"])


@app.get("/", include_in_schema=False)
def frontend():
    index_file = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
    return FileResponse(index_file)


@app.get("/api/health", tags=["系统"])
def health():
    return {"status": "ok"}

@app.get("/api/version", tags=["系统"])
def app_version():
    index_file = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
    try:
        digest = hashlib.md5(index_file.read_bytes()).hexdigest()
    except OSError:
        digest = "unknown"
    return {"html_md5": digest}
