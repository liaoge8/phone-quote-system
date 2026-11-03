"""FastAPI 入口：挂载路由、CORS、建表、启动定时器，顺带托管前端页面。"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .db.session import init_db
from .routers import auth_router, intel_router, products_router, sales_router
from .scheduler import start_scheduler

# 前端静态文件目录（部署时把 index.html 放到 ./static/，与后端同源，免跨域）
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
INDEX_HTML = STATIC_DIR / "index.html"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时建表 + 启动定时器；关闭时释放资源。"""
    init_db()
    logger.info("数据库表已就绪")
    start_scheduler()
    yield


app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan)

# CORS 全开：方便前端联调
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全部接口挂 /api 前缀；登录除外，其余均需 JWT
app.include_router(auth_router, prefix="/api/auth", tags=["登录"])
app.include_router(products_router, prefix="/api/products", tags=["商品与价格"])
app.include_router(intel_router, prefix="/api/intel", tags=["情报中心"])
app.include_router(sales_router, prefix="/api/sales", tags=["销量分析"])


@app.get("/api/health", summary="健康检查（无需登录）")
def health() -> dict:
    return {"status": "ok", "app": settings.APP_NAME}


# 前端托管：/ 返回 index.html（同源，前端用相对路径 /api 调用接口）
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def frontend():
    if INDEX_HTML.exists():
        return FileResponse(str(INDEX_HTML))
    return {"message": "前端尚未部署：请把 index.html 放到 static/ 目录"}
