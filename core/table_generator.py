from typing import List, Dict, Any
from datetime import datetime


def _can_purchase(quota: str) -> str:
    """根据限购规则判断能否购买。"""
    # 暂停申购：完全不能买
    if "暂停申购" in quota:
        return "❌ 暂停申购"
    
    # 提取限额
    match = __import__('re').search(r'限额([\d.]+)(元|万元|亿)', quota)
    if match:
        amount = float(match.group(1))
        unit = match.group(2)
        if unit == "元":
            if amount <= 10:
                return f"✅ 可买{int(amount)}元"
            elif amount <= 100:
                return f"✅ 可买{int(amount)}元"
            elif amount <= 1000:
                return f"✅ 可买{int(amount)}元"
            else:
                return f"✅ 可买{amount}元"
        elif unit == "万元":
            if amount >= 1:
                return "✅ 正常购买"
            else:
                return f"✅ 可买{amount}万元"
    
    if "限大额" in quota:
        return "⚠️ 限大额"
    if "开放申购" in quota:
        return "✅ 正常购买"
    if "无限制" in quota:
        return "✅ 正常购买"
    
    return "✅ 正常购买"


def generate_etf_table(etf_data: List[Dict[str, Any]]) -> str:
    if not etf_data:
        return "暂无场内标普500 ETF数据"

    header = "| 基金代码 | 基金全称 | 年管理费 | 年托管费 | 年度综合总费率 | 当日实时溢价率 | 场内买卖佣金 | 基金管理人 | 申赎状态 |\n"
    separator = "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    
    # 按溢价率升序排列（折价在前，高估在后）
    def premium_sort_key(fund):
        try:
            rate_str = fund.get("premium_rate", "")
            if "当日数据未公示" in rate_str:
                return 99999
            match = __import__('re').search(r'([+-]?[\d.]+)', rate_str)
            return float(match.group(1)) if match else 99999
        except:
            return 99999
    
    sorted_data = sorted(etf_data, key=premium_sort_key)
    
    rows = []
    for fund in sorted_data:
        premium_rate = fund.get("premium_rate", "")
        premium_status = fund.get("premium_status", "")
        if premium_status:
            premium_display = f"{premium_rate} ({premium_status})"
        else:
            premium_display = premium_rate
        
        row = f"| {fund.get('fund_code', '')} | {fund.get('fund_name', '')} | {fund.get('management_fee', '')} | {fund.get('custody_fee', '')} | {fund.get('total_fee', '')} | {premium_display} | {fund.get('commission', '')} | {fund.get('manager', '')} | {fund.get('subscription_status', '')} |"
        rows.append(row)
    
    return header + separator + "\n".join(rows)


def generate_index_fund_table(index_data: List[Dict[str, Any]]) -> str:
    if not index_data:
        return "暂无场外标普500联接/指数基金数据"

    header = "| 基金代码 | 基金全称 | 年管理费 | 年托管费 | 年度综合年费 | 申购费率 | 赎回费率 | 限购规则 | 能否购买 | 基金管理人 |\n"
    separator = "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    
    rows = []
    for fund in index_data:
        purchase_fee = fund.get("purchase_fee", "")
        original_fee = fund.get("original_purchase_fee", "")
        if original_fee and purchase_fee != original_fee:
            fee_display = f"{purchase_fee}（原{original_fee}）"
        else:
            fee_display = purchase_fee
        
        quota = fund.get("quota", "")
        can_buy = _can_purchase(quota)
        
        row = f"| {fund.get('fund_code', '')} | {fund.get('fund_name', '')} | {fund.get('management_fee', '')} | {fund.get('custody_fee', '')} | {fund.get('total_fee', '')} | {fee_display} | {fund.get('redemption_fee', '')} | {quota} | {can_buy} | {fund.get('manager', '')} |"
        rows.append(row)
    
    return header + separator + "\n".join(rows)


def generate_summary(etf_data: List[Dict[str, Any]], index_data: List[Dict[str, Any]]) -> str:
    summary = ""
    
    if etf_data:
        # 按溢价率排序，取折价最小的（最适合买入）
        def premium_sort_key(fund):
            try:
                rate_str = fund.get("premium_rate", "")
                if "当日数据未公示" in rate_str:
                    return 99999
                match = __import__('re').search(r'([+-]?[\d.]+)', rate_str)
                return float(match.group(1)) if match else 99999
            except:
                return 99999
        sorted_etf = sorted(etf_data, key=premium_sort_key)
        best_etf = sorted_etf[0]
        
        summary += f"💰 **场内最优性价比标的**: {best_etf.get('fund_code', '')} {best_etf.get('fund_name', '')}（溢价率 {best_etf.get('premium_rate', '')}）\n\n"
        
        discounted_etfs = [f for f in etf_data if f.get("premium_status") == "低估"]
        if discounted_etfs:
            items = [f"{f.get('fund_code')}({f.get('premium_rate')})" for f in discounted_etfs[:3]]
            summary += f"📉 **场内折价标的**: {', '.join(items)}\n\n"
        
        premium_etfs = [f for f in etf_data if f.get("premium_status") == "高估"]
        if premium_etfs:
            items = [f"{f.get('fund_code')}({f.get('premium_rate')})" for f in premium_etfs[:3]]
            summary += f"📈 **场内高估标的**: {', '.join(items)}\n\n"
    
    if index_data:
        best_index = index_data[0]
        summary += f"💵 **场外最低手续费标的**: {best_index.get('fund_code', '')} {best_index.get('fund_name', '')}（综合年费 {best_index.get('total_fee', '')}）\n\n"
        
        not_purchasable = [f for f in index_data if _can_purchase(f.get("quota", "")) != "✅ 正常购买"]
        if not_purchasable:
            items = [f"{f.get('fund_code')}({_can_purchase(f.get('quota', ''))})" for f in not_purchasable[:3]]
            summary += f"⚠️ **限购/暂停基金**: {', '.join(items)}\n\n"
        
        purchasable = [f for f in index_data if _can_purchase(f.get("quota", "")) == "✅ 正常购买"]
        if purchasable:
            items = [f"{f.get('fund_code')} {f.get('fund_name')[:10]}..." for f in purchasable[:3]]
            summary += f"✅ **可正常购买**: {', '.join(items)}\n\n"
    
    return summary


def generate_full_report(etf_data: List[Dict[str, Any]], index_data: List[Dict[str, Any]]) -> str:
    date_str = datetime.now().strftime("%Y年%m月%d日")
    
    report = f"# 📊 标普500基金每日快报 ({date_str})\n\n"
    report += "---\n\n"
    report += "## 📈 表格一：场内标普500 ETF 溢价 + 费率明细表（按溢价率升序）\n\n"
    report += generate_etf_table(etf_data) + "\n\n"
    report += "> 💡 **溢价率解读**: 溢价＞0 代表场内价格比基金净值贵，不适合买入；溢价＜0 折价，更适合场内加仓。\n\n"
    report += "---\n\n"
    report += "## 📉 表格二：场外标普500联接/指数基金（A类）额度 + 费率明细表（按综合费率升序）\n\n"
    report += generate_index_fund_table(index_data) + "\n\n"
    report += "> 💡 **持有建议**: A类适合长期持有，费率更优。\n\n"
    report += "---\n\n"
    report += "## 📝 今日总结\n\n"
    report += generate_summary(etf_data, index_data)
    
    return report