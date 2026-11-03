"""模型注册：集中导入，保证 Base.metadata 能收录全部表。"""
from .policy_price import PolicyPrice
from .price_record import PriceRecord, PriceType
from .product import Product
from .sales import SalesArchive
from .tenna import TennaRecord

__all__ = ["PolicyPrice", "PriceRecord", "PriceType", "Product", "SalesArchive", "TennaRecord"]
