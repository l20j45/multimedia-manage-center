"""Servicio de correo por SMTP.

Si SMTP_HOST no está configurado, los correos solo se registran por consola,
así que el proyecto funciona sin configuración previa.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


def smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER)


def send_email(to: str, subject: str, html: str) -> bool:
    """Envía un correo HTML. Devuelve True si pudo enviarlo."""
    if not smtp_configured():
        logger.info("[email] SMTP no configurado. Solo se registra:\n%s | Para: %s", subject, to)
        return False

    try:
        msg = EmailMessage()
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content("Tu cliente no soporta HTML.")
        msg.add_alternative(html, subtype="html")

        if settings.SMTP_PORT == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                settings.SMTP_HOST, settings.SMTP_PORT, context=context, timeout=15
            ) as smtp:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.send_message(msg)

        logger.info("[email] Enviado a %s: %s", to, subject)
        return True
    except Exception:
        logger.exception("[email] Error enviando a %s", to)
        return False


def send_welcome_email(to: str, name: str | None) -> None:
    """Correo de bienvenida al crear una cuenta."""
    display = name or to.split("@")[0]
    subject = "¡Bienvenido!"
    html = f"""
    <html><body style="font-family: Arial, sans-serif; color: #1f2937;">
      <h2>¡Hola {display}!</h2>
      <p>Tu cuenta fue creada con éxito. Ya puedes iniciar sesión en la aplicación.</p>
      <p>— El equipo de {settings.PROJECT_NAME}</p>
    </body></html>
    """
    send_email(to, subject, html)


def send_password_reset_email(to: str, name: str | None, code: str) -> None:
    """Correo con el código de un solo uso para restablecer la contraseña."""
    if not smtp_configured():
        logger.info(
            "[email] Código de reset para %s: %s (SMTP no configurado, solo consola)", to, code
        )
    display = name or to.split("@")[0]
    subject = "Recupera tu contraseña"
    html = f"""
    <html><body style="font-family: Arial, sans-serif; color: #1f2937;">
      <h2>¡Hola {display}!</h2>
      <p>Recibimos una solicitud para restablecer tu contraseña. Tu código es:</p>
      <p style="font-size: 30px; letter-spacing: 8px; font-weight: bold;">{code}</p>
      <p>Expira en 30 minutos y puede usarse una sola vez. Si no fuiste tú, ignora este correo.</p>
      <p>— El equipo de {settings.PROJECT_NAME}</p>
    </body></html>
    """
    send_email(to, subject, html)
