import smtplib
from email.message import EmailMessage

from config import settings


def send_kim_message(
    subject: str,
    body: str,
    recipient: str | None = None,
    attachments: list[tuple[str, bytes]] | None = None,
) -> None:
    """Hands a message to the local KIM client module (CM) via SMTP.

    Signing/encryption is performed by the CM; the mock only logs it.
    """
    msg = EmailMessage()
    msg["From"] = settings.kim_sender
    msg["To"] = recipient or settings.kim_recipient
    msg["Subject"] = subject
    msg.set_content(body)
    for filename, data in attachments or []:
        msg.add_attachment(data, maintype="application", subtype="json", filename=filename)
    with smtplib.SMTP(settings.kim_smtp_host, settings.kim_smtp_port, timeout=10) as smtp:
        smtp.send_message(msg)
