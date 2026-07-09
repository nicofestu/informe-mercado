"""Envía el informe por email. Se ejecuta después de build_data.py y
build_email.py (y, opcionalmente, generate_report.py si configuraste la
API key paga de Anthropic).

Prioridad de contenido:
  1. Si existe data/report_latest.md (lo genera generate_report.py, opcional
     y pago), se manda esa versión narrada, con noticias.
  2. Si no, se manda data/email_body.html / .txt (gratis, generado por
     build_email.py: tablas con los datos, sin narración).

En los dos casos se adjunta data/prompt_ready.txt — el prompt con el JSON
ya pegado adentro — para que, si un lunes puntual querés la versión narrada,
alcance con abrir el adjunto, copiar y pegar en un chat de Claude con
búsqueda web activada. Sin pasos de configuración, sin costo.

Requiere las variables de entorno:
    GMAIL_ADDRESS        tu dirección de Gmail (el remitente)
    GMAIL_APP_PASSWORD   contraseña de aplicación de 16 caracteres
    RECIPIENT_EMAIL      a dónde mandarlo (puede ser la misma dirección)

    python send_email.py
"""
from __future__ import annotations

import os
import smtplib
from datetime import date
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _narrated_markdown_to_html(md_text: str) -> str:
    try:
        import markdown as md_lib
        body = md_lib.markdown(md_text, extensions=["tables", "nl2br"])
    except ImportError:
        import html
        body = f"<pre style='white-space:pre-wrap'>{html.escape(md_text)}</pre>"
    return f"""
    <html><body style="font-family:Georgia,serif;max-width:720px;margin:0 auto;
      color:#1a1a1a;line-height:1.5">
    {body}
    </body></html>
    """


def _load_content() -> tuple[str, str, str]:
    """Devuelve (subject_suffix, text_body, html_body)."""
    narrated_path = os.path.join("data", "report_latest.md")
    if os.path.exists(narrated_path) and os.path.getsize(narrated_path) > 0:
        text = open(narrated_path, encoding="utf-8").read()
        return " (narrado)", text, _narrated_markdown_to_html(text)

    html_path = os.path.join("data", "email_body.html")
    text_path = os.path.join("data", "email_body.txt")
    if not os.path.exists(html_path):
        raise FileNotFoundError(
            "No existe data/email_body.html; ¿corriste build_email.py antes?"
        )
    html = f"<html><body>{open(html_path, encoding='utf-8').read()}</body></html>"
    text = open(text_path, encoding="utf-8").read() if os.path.exists(text_path) else ""
    return "", text, html


def send() -> None:
    gmail_addr = os.environ["GMAIL_ADDRESS"]
    gmail_pass = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ.get("RECIPIENT_EMAIL", gmail_addr)

    subject_suffix, text_body, html_body = _load_content()

    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"Informe semanal de mercado{subject_suffix} — {date.today().isoformat()}"
    msg["From"] = gmail_addr
    msg["To"] = recipient

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(text_body or "Ver versión HTML.", "plain", "utf-8"))
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    prompt_path = os.path.join("data", "prompt_ready.txt")
    if os.path.exists(prompt_path):
        attachment = MIMEApplication(
            open(prompt_path, "rb").read(), Name="prompt_listo_para_pegar.txt"
        )
        attachment["Content-Disposition"] = (
            'attachment; filename="prompt_listo_para_pegar.txt"'
        )
        msg.attach(attachment)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(gmail_addr, gmail_pass)
        server.send_message(msg)

    print(f"[send_email] Enviado a {recipient}{subject_suffix}.")


if __name__ == "__main__":
    send()
