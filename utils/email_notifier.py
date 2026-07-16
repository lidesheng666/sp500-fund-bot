import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import Optional


def send_email(subject: str, content: str, to_addr: str, smtp_user: str, smtp_pass: str) -> bool:
    """通过 QQ 邮箱 SMTP 发送邮件。

    Args:
        subject: 邮件主题
        content: 邮件内容（支持 HTML/Markdown）
        to_addr: 收件人邮箱
        smtp_user: 发件邮箱（QQ邮箱地址）
        smtp_pass: SMTP 授权码（非QQ密码）
    """
    msg = MIMEMultipart("alternative")
    msg["From"] = smtp_user
    msg["To"] = to_addr
    msg["Subject"] = Header(subject, "utf-8")

    # 纯文本版本
    text_part = MIMEText(content, "plain", "utf-8")
    msg.attach(text_part)

    # HTML 版本（将 markdown 表格转为简单 HTML）
    html_content = _markdown_to_html(content)
    html_part = MIMEText(html_content, "html", "utf-8")
    msg.attach(html_part)

    try:
        server = smtplib.SMTP_SSL("smtp.qq.com", 465)
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [to_addr], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"邮件发送失败: {e}")
        return False


def _markdown_to_html(md: str) -> str:
    """简易 Markdown 转 HTML。"""
    import re

    html = md

    # 表格处理
    lines = html.split("\n")
    in_table = False
    table_rows = []
    result = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            # 跳过分隔行
            if all(re.match(r'^[-:]+$', c) for c in cells):
                continue
            table_rows.append(cells)
            in_table = True
        else:
            if in_table and table_rows:
                result.append("<table border='1' cellpadding='5' cellspacing='0' style='border-collapse:collapse;font-size:12px;'>")
                for i, row in enumerate(table_rows):
                    tag = "th" if i == 0 else "td"
                    result.append("<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in row) + "</tr>")
                result.append("</table>")
                table_rows = []
                in_table = False
            result.append(line)

    if table_rows:
        result.append("<table border='1' cellpadding='5' cellspacing='0' style='border-collapse:collapse;font-size:12px;'>")
        for i, row in enumerate(table_rows):
            tag = "th" if i == 0 else "td"
            result.append("<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in row) + "</tr>")
        result.append("</table>")

    html = "\n".join(result)

    # 标题
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    # 粗体
    html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html)
    # 分隔线
    html = re.sub(r'^---$', r'<hr>', html, flags=re.MULTILINE)
    # 引用
    html = re.sub(r'^> (.+)$', r'<blockquote style="color:#666;border-left:3px solid #ccc;padding-left:10px;">\1</blockquote>', html, flags=re.MULTILINE)

    return f"<html><body style='font-family:Microsoft YaHei,sans-serif;'>{html}</body></html>"