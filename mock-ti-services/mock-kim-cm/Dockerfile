FROM docker.io/library/python:3.12-slim
WORKDIR /srv# mock-ti-services/mock-kim-cm/Dockerfile
FROM docker.io/library/python:3.11-slim

WORKDIR /app

# Installiere benötigte SMTP-Bibliothek
RUN pip install --no-cache-dir aiosmtpd

# Skript in den Container kopieren
COPY smtp_server.py .

# SMTP Port freigeben
EXPOSE 25

# Server starten
CMD ["python", "smtp_server.py"]

RUN pip install --no-cache-dir aiosmtpd
COPY smtp_server.py .
EXPOSE 2525
CMD ["python", "-u", "smtp_server.py"]
