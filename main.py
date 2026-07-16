"""标普500基金每日报告 — 入口

用法:
  python main.py          # 常驻调度模式（本地运行）
  python main.py --once   # 单次执行模式（GitHub Actions 用）
"""
import logging
import sys
import os
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s/%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("main")


def load_config() -> dict:
    config_path = Path(__file__).parent / "config" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def push_report(report: str, config: dict):
    """根据配置的推送方式发送报告。"""
    # 邮件配置：优先环境变量（GitHub Secrets），其次本地配置
    email_cfg = config.get("notification", {}).get("email", {})
    to_addr = os.environ.get("EMAIL_TO", "") or email_cfg.get("to", "")
    smtp_user = os.environ.get("EMAIL_USER", "") or email_cfg.get("smtp_user", "")
    smtp_pass = os.environ.get("EMAIL_PASS", "") or email_cfg.get("smtp_pass", "")

    if to_addr and smtp_user and smtp_pass:
        from utils.email_notifier import send_email
        from datetime import datetime
        subject = f"标普500基金每日快报 {datetime.now().strftime('%Y-%m-%d')}"
        if send_email(subject, report, to_addr, smtp_user, smtp_pass):
            logger.info(f"邮件推送成功 -> {to_addr}")
        else:
            logger.warning("邮件推送失败")
    else:
        # 回退到 Server酱
        sendkey = os.environ.get("SERVERCHAN_SENDKEY", "") or config.get("notification", {}).get("sendkey", "")
        if sendkey:
            from utils.notifier import send_fund_report
            if send_fund_report(report, sendkey):
                logger.info("Server酱推送成功")
            else:
                logger.warning("Server酱推送失败")
        else:
            logger.warning("未配置推送方式，报告仅保存到本地 data/report.md")


def run_once(config: dict) -> bool:
    """单次执行：抓取数据 -> 生成报告 -> 推送。"""
    from utils.trading_day import is_today_trading_day
    from core.fund_fetcher import FundFetcher
    from core.table_generator import generate_full_report

    if not is_today_trading_day():
        logger.info("今日非交易日，跳过执行")
        return True

    etf_codes = config.get("funds", {}).get("etf", [])
    index_codes = config.get("funds", {}).get("index", [])

    logger.info(f"开始抓取数据: ETF {len(etf_codes)} 只, 指数基金 {len(index_codes)} 只")

    fetcher = FundFetcher()
    etf_data = fetcher.batch_fetch_etf_data(etf_codes)
    index_data = fetcher.batch_fetch_index_data(index_codes)

    report = generate_full_report(etf_data, index_data)

    report_path = Path(__file__).parent / "data" / "report.md"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    logger.info(f"报告已保存到 {report_path}")

    push_report(report, config)
    return True


def run_daemon(config: dict):
    """常驻调度模式。"""
    from scheduler.runner import start

    trigger_time = config.get("schedule", {}).get("trigger_time", "09:45:00")
    sendkey = os.environ.get("SERVERCHAN_SENDKEY", "") or config.get("notification", {}).get("sendkey", "")
    etf_codes = config.get("funds", {}).get("etf", [])
    index_codes = config.get("funds", {}).get("index", [])

    logger.info(f"常驻模式: 每天 {trigger_time} 触发, ETF {len(etf_codes)} 只, 指数基金 {len(index_codes)} 只")
    start(trigger_time, str(Path(__file__).parent / "config" / "config.yaml"), etf_codes, index_codes, sendkey)


def main():
    config = load_config()

    if "--once" in sys.argv:
        logger.info("单次执行模式")
        run_once(config)
    else:
        logger.info("常驻调度模式（加 --once 可单次执行）")
        run_daemon(config)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("程序已停止")
    except Exception as e:
        logger.error(f"程序异常: {e}", exc_info=True)
        sys.exit(1)
