import os
import smtplib
from email.message import EmailMessage


def enviar_email(destinatario, assunto, corpo):
    """Envia um email de texto simples pelo servidor SMTP definido no .env."""
    mensagem = EmailMessage()
    mensagem["From"] = os.environ["SMTP_USER"]
    mensagem["To"] = destinatario
    mensagem["Subject"] = assunto
    mensagem.set_content(corpo)

    porta = int(os.environ.get("SMTP_PORT", 587))
    with smtplib.SMTP(os.environ["SMTP_HOST"], porta, timeout=10) as servidor:
        servidor.starttls()
        servidor.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        servidor.send_message(mensagem)
