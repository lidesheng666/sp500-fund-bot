import time
import logging
from datetime import datetime
import schedule

from utils.trading_day import is_today_trading_day
from core.fund_fetcher import FundFetcher
from core.table_generator import generate_full_report
from utils.notifier import send_fund_report

logger = logging.getLogger("scheduler.runner")


def _parse_hms(t: str) -> tuple[int, int, int]:
    try:
        parts = t.split(":")
        return int(parts[0]), int(parts[1]), int(parts[2])
    except Exception:
        return 9, 45, 0


def _seconds_until_today_hms(t: str) -> float:
    h, m, s = _parse_hms(t)
    now = datetime.now()
    target = now.replace(hour=h, minute=m, second=s, microsecond=0)
    return (target - now).total_seconds()


def run_daily_task(config_path: str, etf_codes: list[str], index_codes: list[str], sendkey: str) -> None:
    if not is_today_trading_day():
        today_str = datetime.now().strftime("%Y-%m-%d")
        logger.info(f"今日({today_str})非交易日，跳过推送任务")
        return

    logger.info("开始执行每日基金数据抓取任务...")

    try:
        fetcher = FundFetcher()

        logger.info("抓取场内ETF数据...")
        etf_data = fetcher.batch_fetch_etf_data(etf_codes)

        logger.info("抓取场外指数基金数据...")
        index_data = fetcher.batch_fetch_index_data(index_codes)

        logger.info("生成报告...")
        report = generate_full_report(etf_data, index_data)

        logger.info("推送报告...")
        if send_fund_report(report, sendkey):
            logger.info("推送成功！")
        else:
            logger.warning("推送失败")

        logger.info("每日任务执行完成")

    except Exception as e:
        logger.error(f"每日任务执行异常: {e}", exc_info=True)


def _wait_and_run(trigger_time: str, config_path: str, etf_codes: list[str], index_codes: list[str], sendkey: str) -> None:
    now = datetime.now()
    h, m, s = _parse_hms(trigger_time)
    target_today = now.replace(hour=h, minute=m, second=s, microsecond=0)

    if now >= target_today:
        diff_sec = (now - target_today).total_seconds()
        if diff_sec < 300:
            logger.warning(f"任务已过当日触发时间 {trigger_time}（{int(diff_sec)}秒前），跳过本轮触发")
            return
        logger.info(f"任务于 {trigger_time} 触发（当前已过 {int(diff_sec)}秒）")
    else:
        logger.info(f"任务将在 {trigger_time} 触发（距今 {int((target_today - now).total_seconds())}秒）")

    run_daily_task(config_path, etf_codes, index_codes, sendkey)


def setup(trigger_time: str, config_path: str, etf_codes: list[str], index_codes: list[str], sendkey: str) -> None:
    schedule.every().day.at(trigger_time).do(
        _wait_and_run,
        trigger_time=trigger_time,
        config_path=config_path,
        etf_codes=etf_codes,
        index_codes=index_codes,
        sendkey=sendkey,
    ).tag("daily_fund_report")
    logger.info(f"每日基金报告任务已注册: 每天 {trigger_time}")


def start(trigger_time: str, config_path: str, etf_codes: list[str], index_codes: list[str], sendkey: str) -> None:
    setup(trigger_time, config_path, etf_codes, index_codes, sendkey)
    logger.info("调度器已启动，等待任务触发...")
    while True:
        schedule.run_pending()
        time.sleep(1)