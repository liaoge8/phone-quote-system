"""入网许可爬虫（占位实现）。

真实逻辑（待实现）：
1. 目标站点：
   - 工信部电信设备进网许可查询（jwxk.miit.gov.cn）
   - TENAA 入网许可中心（tenaa.com.cn）手机入网许可公示页
2. 抓取内容：新入网机型的入网型号（如 25128PNA1C）、证件照、公示日期、
   核心配置（屏幕尺寸、电池容量、入网制式等）。
3. 入库：写入 TennaRecord（入网台账），去重键为入网型号；
   新机型在情报中心置顶展示。
4. 频率：每天凌晨随定时任务跑一次即可（公示更新不频繁）。
5. 注意：两个站点都有反爬，正式实现建议用 Playwright 模拟浏览，
   请求间隔放宽到 3~5 秒，避免被封 IP。

当前为占位实现：只打日志、不产生真实网络请求，
保证定时任务链路能跑通，后续再替换为真实抓取。
"""
import logging

from .base import BaseCrawler

logger = logging.getLogger(__name__)


class TennaCrawler(BaseCrawler):
    source = "tenaa"

    def fetch(self) -> list[dict]:
        logger.info("[tenaa] 占位抓取：真实实现将抓取工信部/TENAA 新入网公示")
        # TODO: 接入 Playwright，解析公示列表页，返回如下结构：
        # [{"tenna_model": "25128PNA1C", "phone_model": "",
        #   "specs": "...", "published_at": datetime, ...}]
        return []
