"""定时任务：APScheduler，每天凌晨 2 点跑爬虫任务。"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .crawler.tenaa import TennaCrawler

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def daily_crawl_job() -> None:
    """每日爬虫任务（v1 先打日志占位，链路跑通后再接入真实抓取与入库）。"""
    logger.info("[scheduler] 每日爬虫任务开始")
    # 1. 入网许可：新机预警第一优先级
    records = TennaCrawler().fetch()
    logger.info("[scheduler] TENAA 抓取到 %d 条（占位）", len(records))
    # TODO: 2. 品牌官网价格 / 3. 酷安 / 4. 资讯站 / 5. 商城 / 6. 抖音 / 7. 博主小道消息
    # TODO: 时效过滤后入库，并触发大模型解读
    logger.info("[scheduler] 每日爬虫任务结束")


def start_scheduler() -> None:
    """启动定时器（应用启动时调用一次）。"""
    if scheduler.running:
        return
    scheduler.add_job(
        daily_crawl_job,
        trigger="cron",
        hour=2,
        minute=0,
        id="daily_crawl",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("[scheduler] 定时器已启动：每天 02:00 执行爬虫任务")
