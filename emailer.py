"""Email delivery for daily topic picker.

Reads SMTP config from environment variables (so secrets never live in code):
    SMTP_HOST     e.g. smtp.qq.com
    SMTP_PORT     e.g. 465 (SSL) or 587 (TLS),默认 465
    SMTP_USER     发件邮箱完整地址
    SMTP_PASS     SMTP 授权码(不是登录密码)
    TO_EMAIL      收件邮箱(可多个,逗号分隔)
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formatdate, make_msgid
from pathlib import Path


def send_report(
    md_path: Path,
    subject: str | None = None,
    to_email: str | None = None,
) -> bool:
    host     = os.environ.get("SMTP_HOST")
    port     = int(os.environ.get("SMTP_PORT", "465"))
    user     = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    to_addr  = to_email or os.environ.get("TO_EMAIL")

    missing = [k for k, v in {
        "SMTP_HOST": host, "SMTP_USER": user, "SMTP_PASS": password,
        "TO_EMAIL":  to_addr,
    }.items() if not v]
    if missing:
        print(f"[email] missing env vars: {', '.join(missing)} — skipping send")
        return False

    md_path = Path(md_path)
    if not md_path.exists():
        print(f"[email] file not found: {md_path}")
        return False

    date_str = md_path.stem
    subject  = subject or f"🔥 今日 1 分钟短视频选题包 · {date_str}"
    body     = md_path.read_text(encoding="utf-8")

    msg = MIMEMultipart("mixed")
    msg["From"]    = user
    msg["To"]      = to_addr
    msg["Date"]    = formatdate(localtime=True)
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=user.split("@", 1)[1])

    msg.attach(MIMEText(body, _subtype="plain", _charset="utf-8"))

    with md_path.open("rb") as f:
        attach = MIMEApplication(f.read(), _subtype="markdown")
        attach.add_header("Content-Disposition", "attachment",
                          filename=md_path.name)
        msg.attach(attach)

    try:
        ctx = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=20) as s:
                s.login(user, password)
                s.sendmail(user, [a.strip() for a in to_addr.split(",")], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.starttls(context=ctx)
                s.login(user, password)
                s.sendmail(user, [a.strip() for a in to_addr.split(",")], msg.as_string())
        print(f"[email] sent  -> {to_addr}  ({md_path.name}, {len(body)} chars)")
        return True
    except Exception as e:
        print(f"[email] FAILED  {type(e).__name__}: {e}")
        return False
