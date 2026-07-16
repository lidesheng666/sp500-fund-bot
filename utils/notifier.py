import requests
from typing import Optional


SERVER_CHAN_URL = "https://sctapi.ftqq.com/{}.send"


def send_notification(title: str, content: str, sendkey: str) -> bool:
    if not sendkey:
        return False

    url = SERVER_CHAN_URL.format(sendkey)
    try:
        resp = requests.post(
            url,
            data={"title": title, "desp": content},
            timeout=10,
            proxies={"http": None, "https": None}
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 0:
            return True
        return False
    except Exception:
        return False


def send_fund_report(content: str, sendkey: str) -> bool:
    title = "📊 标普500基金每日快报"
    return send_notification(title, content, sendkey)