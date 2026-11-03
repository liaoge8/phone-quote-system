"""爬虫基类：统一来源标识、抓取时间与时效过滤规则。"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone


class Freshness(str):
    """时效等级（与前端情报中心展示口径一致）。"""

    LATEST = "latest"  # 24 小时内：最新
    VALID = "valid"  # 7 天内：时效内
    STALE = "stale"  # 8~30 天：降权展示
    DROP = "drop"  # 超过 30 天：直接丢弃


def classify_freshness(published_at: datetime) -> str:
    """按发布时间判定情报的时效等级。

    规则（用户已确认）：
    - 24 小时内 -> latest（最新）
    - 7 天内    -> valid（时效内）
    - 8~30 天   -> stale（降权）
    - 超过 30 天 -> drop（丢弃；两年前的旧微博之类毫无价值）
    """
    now = datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_days = (now - published_at).total_seconds() / 86400
    if age_days <= 1:
        return Freshness.LATEST
    if age_days <= 7:
        return Freshness.VALID
    if age_days <= 30:
        return Freshness.STALE
    return Freshness.DROP


class BaseCrawler(ABC):
    """所有爬虫的抽象基类。

    数据来源优先级（用户已确认）：
    1. 工信部入网许可 / TENAA（新机预警第一优先级）
    2. 品牌官网（上市/下市状态与官方价）
    3. 酷安
    4. 数码资讯站
    5. 各大商城（京东/天猫/拼多多）
    6. 抖音
    7. 数码博主小道消息（最后，须交叉验证）
    """

    # 数据来源名称，如 "tenaa" / "official" / "coolapk"
    source: str = "unknown"

    @abstractmethod
    def fetch(self) -> list[dict]:
        """执行一次抓取，返回原始数据列表（每个子类实现具体逻辑）。"""
        raise NotImplementedError

    def filter_fresh(self, items: list[dict], key: str = "published_at") -> list[dict]:
        """时效过滤：只保留 30 天内的情报，并打上时效标签。"""
        kept = []
        for item in items:
            published_at = item.get(key)
            if not published_at:
                continue
            level = classify_freshness(published_at)
            if level == Freshness.DROP:
                continue  # 过期直接丢弃
            item["freshness"] = level
            kept.append(item)
        return kept
