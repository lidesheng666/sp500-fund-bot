import requests
import json
import re
import time
from typing import Dict, Any, Optional, List


class FundFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.proxies = {"http": None, "https": None}
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://fund.eastmoney.com/",
        })

    def _fetch(self, url: str) -> Optional[str]:
        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = "utf-8"
            return resp.text
        except Exception:
            return None

    def _fetch_json(self, url: str) -> Optional[Any]:
        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = "utf-8"
            return resp.json()
        except Exception:
            return None

    def _clean_html(self, text: str) -> str:
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _parse_jbgk(self, fund_code: str) -> Dict[str, str]:
        """从 jbgk_{code}.html 解析基本概况信息。"""
        info = {}
        url = f"https://fund.eastmoney.com/f10/jbgk_{fund_code}.html"
        html = self._fetch(url)
        if not html:
            return info

        clean = self._clean_html(html)

        patterns = {
            "fund_full_name": r'基金全称\s*(.*?)\s*基金简称',
            "fund_short_name": r'基金简称\s*(.*?)\s*基金代码',
            "fund_type": r'基金类型\s*(.*?)\s*发行日期',
            "management_fee": r'管理费率\s*([\d.]+%（每年）)',
            "custody_fee": r'托管费率\s*([\d.]+%（每年）)',
            "max_purchase_fee": r'最高申购费率\s*([\d.]+%|---)',
            "max_redemption_fee": r'最高赎回费率\s*([\d.]+%|---)',
            "manager": r'管理人：\s*(.*?)\s*净资产',
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, clean)
            if match:
                val = match.group(1).strip()
                if val and val != "---":
                    info[key] = val

        return info

    def _parse_jjfl(self, fund_code: str) -> Dict[str, str]:
        """从 jjfl_{code}.html 解析阶梯费率信息。"""
        info = {}
        url = f"https://fund.eastmoney.com/f10/jjfl_{fund_code}.html"
        html = self._fetch(url)
        if not html:
            return info

        clean = self._clean_html(html)

        # 解析阶梯赎回费率
        redemption_section = re.search(r'赎回费率.*?(?=认购费率|申购费率|管理费|$)', clean, re.DOTALL)
        if redemption_section:
            tier_match = re.findall(r'(\d+[年天月日以内]+)[：:]*([\d.]+%)', redemption_section.group())
            if tier_match:
                info["redemption_tiers"] = "；".join([f"{t[0]} {t[1]}" for t in tier_match])

        # 解析阶梯申购费率
        purchase_section = re.search(r'申购费率.*?(?=赎回费率|管理费|$)', clean, re.DOTALL)
        if purchase_section:
            tier_match = re.findall(r'(\d+[万元以内]+)[：:]*([\d.]+%)', purchase_section.group())
            if tier_match:
                info["purchase_tiers"] = "；".join([f"{t[0]} {t[1]}" for t in tier_match])

        return info

    def _get_nav(self, fund_code: str) -> float:
        """获取 T-1 日确认净值（用于计算溢价率）。"""
        url = f"https://api.fund.eastmoney.com/f10/lsjz?fundCode={fund_code}&pageIndex=1&pageSize=5"
        data = self._fetch_json(url)
        if data and isinstance(data.get("Data"), dict):
            nav_list = data["Data"].get("LSJZList", [])
            if len(nav_list) >= 2:
                try:
                    return float(nav_list[1].get("DWJZ", "0"))
                except ValueError:
                    pass
            elif nav_list:
                try:
                    return float(nav_list[0].get("DWJZ", "0"))
                except ValueError:
                    pass
        return 0

    def _get_realtime_price(self, fund_code: str) -> float:
        """通过腾讯财经 API 获取场内 ETF 实时价格。"""
        prefix = "sh" if fund_code.startswith("5") else "sz"
        url = f"http://qt.gtimg.cn/q={prefix}{fund_code}"
        text = self._fetch(url)
        if not text:
            return 0
        try:
            # 格式: v_sh513500="1~标普500ETF博时~513500~2.573~..."
            # 索引3 是当前价格
            match = re.search(r'"([^"]+)"', text)
            if match:
                parts = match.group(1).split("~")
                if len(parts) > 3:
                    return float(parts[3])
        except (ValueError, IndexError):
            pass
        return 0

    def _get_premium_data(self, fund_code: str) -> Dict[str, str]:
        """获取 ETF 溢价率数据。"""
        result = {"premium_rate": "当日数据未公示", "premium_status": ""}

        nav = self._get_nav(fund_code)
        price = self._get_realtime_price(fund_code)

        if nav > 0 and price > 0:
            premium = (price - nav) / nav * 100
            result["premium_rate"] = f"{premium:+.2f}%"
            result["premium_status"] = "高估" if premium > 0 else "低估"

        return result

    def get_etf_data(self, fund_code: str) -> Optional[Dict[str, Any]]:
        data = {
            "fund_code": fund_code,
            "fund_name": "当日数据未公示",
            "management_fee": "当日数据未公示",
            "custody_fee": "当日数据未公示",
            "total_fee": "当日数据未公示",
            "premium_rate": "当日数据未公示",
            "premium_status": "",
            "commission": "券商默认万3，可协商至万1",
            "manager": "当日数据未公示",
            "subscription_status": "开放",
        }

        try:
            jbgk = self._parse_jbgk(fund_code)
            if jbgk.get("fund_full_name"):
                data["fund_name"] = jbgk["fund_full_name"]
            elif jbgk.get("fund_short_name"):
                data["fund_name"] = jbgk["fund_short_name"]
            if jbgk.get("management_fee"):
                data["management_fee"] = jbgk["management_fee"]
            if jbgk.get("custody_fee"):
                data["custody_fee"] = jbgk["custody_fee"]
            if jbgk.get("manager"):
                data["manager"] = jbgk["manager"]

            data["total_fee"] = self._calculate_total_fee(data["management_fee"], data["custody_fee"])

            premium = self._get_premium_data(fund_code)
            data["premium_rate"] = premium["premium_rate"]
            data["premium_status"] = premium["premium_status"]

        except Exception:
            pass

        return data

    def get_index_fund_data(self, fund_code: str) -> Optional[Dict[str, Any]]:
        data = {
            "fund_code": fund_code,
            "fund_name": "当日数据未公示",
            "management_fee": "当日数据未公示",
            "custody_fee": "当日数据未公示",
            "total_fee": "当日数据未公示",
            "purchase_fee": "当日数据未公示",
            "original_purchase_fee": "当日数据未公示",
            "redemption_fee": "当日数据未公示",
            "quota": "无限制",
            "manager": "当日数据未公示",
            "is_c_class": False,
            "holding_suggestion": "",
        }

        try:
            jbgk = self._parse_jbgk(fund_code)
            if jbgk.get("fund_full_name"):
                data["fund_name"] = jbgk["fund_full_name"]
            elif jbgk.get("fund_short_name"):
                data["fund_name"] = jbgk["fund_short_name"]

            name = jbgk.get("fund_short_name", "") + jbgk.get("fund_full_name", "")
            data["is_c_class"] = "C" in jbgk.get("fund_short_name", "") or "C类" in jbgk.get("fund_full_name", "")

            if jbgk.get("management_fee"):
                data["management_fee"] = jbgk["management_fee"]
            if jbgk.get("custody_fee"):
                data["custody_fee"] = jbgk["custody_fee"]
            if jbgk.get("manager"):
                data["manager"] = jbgk["manager"]
            if jbgk.get("max_purchase_fee"):
                data["purchase_fee"] = jbgk["max_purchase_fee"]
                data["original_purchase_fee"] = jbgk["max_purchase_fee"]
            if jbgk.get("max_redemption_fee"):
                data["redemption_fee"] = jbgk["max_redemption_fee"]

            # 补充阶梯费率
            jjfl = self._parse_jjfl(fund_code)
            if jjfl.get("redemption_tiers"):
                data["redemption_fee"] = jjfl["redemption_tiers"]

            # 获取限购信息
            data["quota"] = self._fetch_quota_info(fund_code)

            data["total_fee"] = self._calculate_total_fee(data["management_fee"], data["custody_fee"])

            if data["is_c_class"]:
                data["holding_suggestion"] = "短期持有"
            else:
                data["holding_suggestion"] = "长期持有"

        except Exception:
            pass

        return data

    def _fetch_quota_info(self, fund_code: str) -> str:
        """从天天基金网获取基金限购信息和交易状态。"""
        url = f"https://fund.eastmoney.com/{fund_code}.html"
        html = self._fetch(url)
        if not html:
            return "无限制"

        # 提取 buyWayStatic 区域
        buyway_pattern = r'<div class="buyWayStatic">(.*?)</div>'
        buyway_match = re.search(buyway_pattern, html, re.DOTALL)
        if buyway_match:
            buyway_content = buyway_match.group(1)
            clean = re.sub(r'<[^>]+>', ' ', buyway_content)
            clean = re.sub(r'\s+', ' ', clean).strip()

            if "快取" in clean:
                pass
            else:
                # 提取交易状态（暂停申购/限大额/开放申购）
                status_pattern = r'交易状态：\s*([^()]+?)\s*[\(（]'
                status_match = re.search(status_pattern, clean)
                status = status_match.group(1).strip() if status_match else ""

                quota_pattern = r'单日累计购买上限([\d.]+)\s*(元|万元|亿)'
                quota_match = re.search(quota_pattern, clean)
                
                if quota_match:
                    amount = quota_match.group(1)
                    unit = quota_match.group(2)
                    return f"{status}（限额{amount}{unit}）"
                else:
                    if "暂停申购" in clean:
                        return "暂停申购"
                    if "限大额" in clean:
                        return "限大额"
                    if "开放申购" in clean:
                        return "开放申购"

        return "无限制"

    def _calculate_total_fee(self, management_fee: str, custody_fee: str) -> str:
        try:
            mgmt_match = re.search(r'([\d.]+)%', management_fee)
            cust_match = re.search(r'([\d.]+)%', custody_fee)
            mgmt_rate = float(mgmt_match.group(1)) if mgmt_match else 0
            cust_rate = float(cust_match.group(1)) if cust_match else 0
            total = mgmt_rate + cust_rate
            return f"{total:.2f}%" if total > 0 else "当日数据未公示"
        except Exception:
            return "当日数据未公示"

    def get_fee_value(self, fee_str: str) -> float:
        if "当日数据未公示" in fee_str or "未公示" in fee_str:
            return 99999
        try:
            match = re.search(r'([\d.]+)', fee_str)
            return float(match.group(1)) if match else 99999
        except Exception:
            return 99999

    def batch_fetch_etf_data(self, fund_codes: List[str]) -> List[Dict[str, Any]]:
        results = []
        for code in fund_codes:
            data = self.get_etf_data(code)
            if data:
                results.append(data)
            time.sleep(0.5)  # 避免请求过快被限流
        return sorted(results, key=lambda x: self.get_fee_value(x["total_fee"]))

    def batch_fetch_index_data(self, fund_codes: List[str]) -> List[Dict[str, Any]]:
        results = []
        for code in fund_codes:
            data = self.get_index_fund_data(code)
            if data:
                results.append(data)
            time.sleep(0.5)
        return sorted(results, key=lambda x: (self.get_fee_value(x["total_fee"]), self.get_fee_value(x["purchase_fee"])))