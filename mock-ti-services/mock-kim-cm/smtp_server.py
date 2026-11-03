import asyncio
import hashlib# mock-ti-services/mock-kim-cm/smtp_server.py
import asyncio
import logging
from aiosmtpd.controller import Controller
from email import message_from_bytes

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [KIM-MOCK-CM] - %(levelname)s - %(message)s')
logger = logging.getLogger("KIM_Mock")

class KIMClientModuleHandler:
    async def handle_DATA(self, server, session, envelope):
        peer = session.peer
        mail_from = envelope.mail_from
        rcpt_tos = envelope.rcpt_tos
        data = envelope.content

        # E-Mail-Byte-Daten parsen
        msg = message_from_bytes(data)
        subject = msg.get('Subject', 'Kein Betreff')
        
        logger.info(f"--- Eingehende unverschlüsselte Nachricht von Agent empfangen ---")
        logger.info(f"Verbindung von: {peer[0]}:{peer[1]}")
        logger.info(f"Absender (KIM): {mail_from}")
        logger.info(f"Empfänger (KIM): {rcpt_tos}")
        logger.info(f"Betreff: {subject}")

        # Simuliere TI-Krypto-Prozesse (SMC-B / eHBA Prüfung & Verschlüsselung)
        logger.info("Greife auf simulierte SMC-B (Institutionskarte) zu...")
        await asyncio.sleep(0.5) # Simuliere Latenz des Kartenterminals
        
        logger.info("Signiere Nachricht kryptografisch (Signatur-Typ: C-AdES)...")
        logger.info("Löse Empfänger-Zertifikat über TI-Verzeichnisdienst (VSDM) auf...")
        
        # Verschlüsselungs-Simulation
        logger.info("Verschlüssele Nachricht Ende-zu-Ende (CMS / EnvelopedData)...")
        
        # Payload im Log anzeigen (gekürzt für Lesbarkeit)
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode('utf-8')
        else:
            body = msg.get_payload(decode=True).decode('utf-8')
            
        logger.info(f"Simulierter Chiffretext generiert für Inhalt:\n[ORIGINAL TEXT]: {body[:150]}...")
        logger.info(f"--- Verschlüsselte KIM-Nachricht erfolgreich in die TI übertragen! ---")

        return '250 Message accepted for delivery'

async def main():
    handler = KIMClientModuleHandler()
    # Der Server lauscht auf Port 25 (Standard-SMTP) innerhalb des Containers
    controller = Controller(handler, hostname='0.0.0.0', port=25)
    controller.start()
    logger.info("KIM-Clientmodul-Mock gestartet und lauscht auf Port 25...")
    
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        controller.stop()

if __name__ == '__main__':
    asyncio.run(main())


from aiosmtpd.controller import Controller


class LoggingHandler:
    async def handle_DATA(self, server, session, envelope):
        digest = hashlib.sha256(envelope.content).hexdigest()
        print("=== KIM message intercepted ===")
        print(f"From: {envelope.mail_from}  To: {envelope.rcpt_tos}")
        print(f"[mock] S/MIME signature (SHA-256 of content): {digest}")
        print(envelope.content.decode("utf-8", errors="replace"))
        print("===============================", flush=True)
        return "250 OK"


async def main():
    controller = Controller(LoggingHandler(), hostname="0.0.0.0", port=2525)
    controller.start()
    print("Mock KIM-CM listening on :2525", flush=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
