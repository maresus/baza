"""
Email Service za Kmetija Pod Goro AI Chatbot
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from datetime import datetime

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "info@podgoro.si")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Kmetija Pod Goro")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "info@podgoro.si")
CC_ADMIN_EMAIL = os.getenv("CC_ADMIN_EMAIL", "")
SMTP_SSL = os.getenv("SMTP_SSL", "").strip().lower() in {"1", "true", "yes"}
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
SUBJECT_PREFIX = os.getenv("SUBJECT_PREFIX", "").strip()
BASE_URL = os.getenv("BASE_URL", "http://localhost:8001")

BRAND_COLOR = "#3a6b35"
BORDER_COLOR = "#c8dfc5"
BG_COLOR = "#f4f9f3"
TEXT_COLOR = "#1b2b1a"
MUTED_COLOR = "#6a7a69"


def _email_wrapper(content: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="sl">
<head>
    <meta charset="UTF-8">
    <title>Kmetija Pod Goro</title>
</head>
<body style="margin:0; padding:0; background:#f4f9f3; font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;">
    <div style="max-width:620px; margin:0 auto; padding:24px 16px;">
        <div style="background:{BRAND_COLOR}; color:#fff; padding:18px 24px; border-radius:14px 14px 0 0; font-size:18px; font-weight:700;">
            Kmetija Pod Goro
        </div>
        <div style="background:#fff; border:1px solid {BORDER_COLOR}; border-top:none; padding:24px; color:{TEXT_COLOR}; font-size:15px; line-height:1.6;">
            {content}
        </div>
        <div style="background:{BG_COLOR}; border:1px solid {BORDER_COLOR}; border-top:none; border-radius:0 0 14px 14px; padding:16px 24px; color:{MUTED_COLOR}; font-size:12px;">
            Kmetija Pod Goro • Pod Goro 1, Slovenija<br>
            Tel: 041 123 456 • info@podgoro.si
        </div>
    </div>
</body>
</html>
"""


def _kv_table(rows: Dict[str, str]) -> str:
    html = f'<table cellpadding="0" cellspacing="0" style="width:100%; border:1px solid {BORDER_COLOR}; border-radius:10px; overflow:hidden; font-size:14px; margin:16px 0;">'
    items = list(rows.items())
    for i, (key, value) in enumerate(items):
        is_last = i == len(items) - 1
        border = "0" if is_last else f"1px solid {BORDER_COLOR}"
        html += f"""
        <tr>
            <td style="background:#f0f7ee; padding:10px 12px; width:40%; border-bottom:{border}; color:#444;"><strong>{key}</strong></td>
            <td style="padding:10px 12px; border-bottom:{border}; color:#111;">{value if value else '—'}</td>
        </tr>"""
    html += "</table>"
    return html


def _guest_confirmation_html(data: Dict[str, Any]) -> str:
    rid = data.get("id")
    rid_line = f"<p><strong>ID rezervacije:</strong> #{rid}</p>" if rid else ""
    res_type = data.get("reservation_type", "")

    type_label = {
        "room": "nastanitev (soba)",
        "table": "kosilo (miza)",
        "bike": "izposoja koles",
        "animals": "hranjenje živali",
    }.get(res_type, res_type)

    rows = {
        "Tip": type_label,
        "Datum": data.get("date", ""),
        "Osebe": str(data.get("people", "")),
        "Ime": data.get("name", ""),
        "Telefon": data.get("phone", ""),
        "Email": data.get("email", ""),
    }
    if data.get("nights"):
        rows["Nočitve"] = str(data.get("nights"))
    if data.get("time"):
        rows["Ura"] = data.get("time")
    if data.get("note"):
        rows["Opomba"] = data.get("note")

    content = f"""
    <p>Pozdravljeni <strong>{data.get('name', 'gost')}</strong>,</p>
    <p>Hvala za vaše povpraševanje. Posredujemo vam povzetek:</p>
    {rid_line}
    {_kv_table(rows)}
    <p><strong>POMEMBNO:</strong> To je povpraševanje, ne potrjena rezervacija. Potrditev boste prejeli po pregledu.</p>
    <p style="color:{MUTED_COLOR};">Za spremembe: 041 123 456 ali info@podgoro.si</p>
    """
    return _email_wrapper(content)


def _admin_new_reservation_html(data: Dict[str, Any], confirm_url: str = "", reject_url: str = "") -> str:
    res_type = data.get("reservation_type", "")
    type_label = {
        "room": "Soba", "table": "Miza", "bike": "Kolesa", "animals": "Hranjenje živali"
    }.get(res_type, res_type)

    rows = {
        "ID": f"#{data.get('id', '?')}",
        "Tip": type_label,
        "Ime": data.get("name", ""),
        "Telefon": data.get("phone", ""),
        "Email": data.get("email", ""),
        "Datum": data.get("date", ""),
        "Osebe": str(data.get("people", "")),
    }
    if data.get("nights"):
        rows["Nočitve"] = str(data.get("nights"))
    if data.get("time"):
        rows["Ura"] = data.get("time")
    if data.get("note"):
        rows["Opomba"] = data.get("note")

    action_buttons = ""
    if confirm_url and reject_url:
        action_buttons = f"""
        <div style="margin-top:20px;">
            <a href="{confirm_url}" style="display:inline-block; background:{BRAND_COLOR}; color:#fff; padding:12px 20px; border-radius:10px; text-decoration:none; font-weight:700; margin-right:10px;">Potrdi</a>
            <a href="{reject_url}" style="display:inline-block; background:#b42318; color:#fff; padding:12px 20px; border-radius:10px; text-decoration:none; font-weight:700;">Zavrni</a>
        </div>"""

    content = f"""
    <p><strong>Nova rezervacija čaka na obdelavo:</strong></p>
    {_kv_table(rows)}
    {action_buttons}
    <p style="margin-top:16px; color:{MUTED_COLOR}; font-size:13px;">
        Ustvarjena: {datetime.now().strftime('%d.%m.%Y %H:%M')}<br>
        <a href="{BASE_URL}/admin" style="color:{BRAND_COLOR};">Odpri admin panel</a>
    </p>"""
    return _email_wrapper(content)


def _guest_confirmed_html(data: Dict[str, Any]) -> str:
    content = f"""
    <p>Pozdravljeni <strong>{data.get('name', 'gost')}</strong>,</p>
    <p>Z veseljem vam sporočamo, da je vaša rezervacija <strong style="color:#22c55e;">POTRJENA</strong>.</p>
    {_kv_table({"Datum": data.get("date", ""), "Osebe": str(data.get("people", ""))})}
    <p>Veselimo se vašega obiska na Kmetiji Pod Goro!</p>
    <p style="color:{MUTED_COLOR};">Za spremembe: 041 123 456 ali info@podgoro.si</p>"""
    return _email_wrapper(content)


def _guest_rejected_html(data: Dict[str, Any]) -> str:
    content = f"""
    <p>Pozdravljeni <strong>{data.get('name', 'gost')}</strong>,</p>
    <p>Zahvaljujemo se za vaše povpraševanje.</p>
    <p>Žal so naše zmogljivosti v izbranem terminu že zapolnjene.</p>
    <p>Vabimo vas, da preverite druge termine. Z veseljem vas pričakamo drugič!</p>
    <p>Lepo vas pozdravljamo,<br><strong>Kmetija Pod Goro</strong></p>"""
    return _email_wrapper(content)


def _send_email(to: str, subject: str, html_body: str) -> bool:
    if SUBJECT_PREFIX:
        subject = f"{SUBJECT_PREFIX} {subject}" if not subject.startswith(SUBJECT_PREFIX) else subject

    if RESEND_API_KEY:
        try:
            import resend
            resend.api_key = RESEND_API_KEY
            resend.Emails.send({
                "from": f"{SMTP_FROM_NAME} <{RESEND_FROM_EMAIL}>",
                "reply_to": SMTP_FROM_EMAIL or ADMIN_EMAIL,
                "to": to,
                "subject": subject,
                "html": html_body,
            })
            print(f"[EMAIL] Resend poslano: {subject} -> {to}")
            return True
        except Exception as e:
            print(f"[EMAIL] Resend napaka: {e}")
            return False

    if not SMTP_USER or not SMTP_PASSWORD:
        print(f"[EMAIL] SMTP ni konfiguriran. Email NI poslan: {subject}")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg["To"] = to
        msg.attach(MIMEText("Sporocilo od Kmetije Pod Goro.", "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        if SMTP_PORT == 465 or SMTP_SSL:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)

        print(f"[EMAIL] Poslano: {subject} -> {to}")
        return True
    except Exception as e:
        print(f"[EMAIL] Napaka: {e}")
        return False


def send_guest_confirmation(data: Dict[str, Any]) -> bool:
    email = data.get("email")
    if not email:
        return False
    rid = data.get("id")
    tag = f"Rezervacija #{rid}" if rid else "Rezervacija"
    subject = f"{tag} - Povpraševanje sprejeto"
    return _send_email(email, subject, _guest_confirmation_html(data))


def send_admin_notification(data: Dict[str, Any], confirm_url: str = "", reject_url: str = "") -> bool:
    rid = data.get("id")
    tag = f"Rezervacija #{rid}" if rid else "Rezervacija"
    subject = f"{tag} - Nova rezervacija – {data.get('name', 'Neznano')}"

    if rid and not confirm_url:
        confirm_url = f"{BASE_URL}/api/admin/reservations/{rid}/confirm"
    if rid and not reject_url:
        reject_url = f"{BASE_URL}/api/admin/reservations/{rid}/reject"

    html = _admin_new_reservation_html(data, confirm_url, reject_url)
    result = _send_email(ADMIN_EMAIL, subject, html)
    if CC_ADMIN_EMAIL and CC_ADMIN_EMAIL != ADMIN_EMAIL:
        _send_email(CC_ADMIN_EMAIL, subject, html)
    return result


def send_reservation_confirmed(data: Dict[str, Any]) -> bool:
    email = data.get("email")
    if not email:
        return False
    rid = data.get("id")
    tag = f"Rezervacija #{rid}" if rid else "Rezervacija"
    return _send_email(email, f"{tag} - Rezervacija potrjena", _guest_confirmed_html(data))


def send_reservation_rejected(data: Dict[str, Any]) -> bool:
    email = data.get("email")
    if not email:
        return False
    rid = data.get("id")
    tag = f"Rezervacija #{rid}" if rid else "Rezervacija"
    return _send_email(email, f"{tag} - Rezervacija zavrnjena", _guest_rejected_html(data))


def send_custom_message(to_email: str, subject: str, body: str) -> bool:
    if not to_email:
        return False
    html = _email_wrapper(f"<div style='white-space:pre-wrap;line-height:1.7'>{body}</div>")
    return _send_email(to_email, subject, html)
