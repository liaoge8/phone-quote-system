"""路由汇总导出。"""
from .auth import router as auth_router
from .intel import router as intel_router
from .products import router as products_router
from .sales import router as sales_router

__all__ = ["auth_router", "intel_router", "products_router", "sales_router"]
