#!/usr/bin/env python3
"""Send PDFs via Gmail SMTP."""
import smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import os

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER = "solom1312818@gmail.com"
PASSWORD = "rorfbowpelhwupwt"
TO = "gromyko.s@ibcon.ru"

PDF_DIR = "/home/hermes-workspace/Alikhan-migration/output_pdf"

context = ssl.create_default_context()

with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
    server.starttls(context=context)
    server.login(SENDER, PASSWORD)
    
    for filename in ["PRESENTATION_PITCH.pdf", "CLIENT_GUIDE.pdf"]:
        filepath = os.path.join(PDF_DIR, filename)
        
        msg = MIMEMultipart()
        msg['From'] = SENDER
        msg['To'] = TO
        msg['Subject'] = f"Hermes: {filename.replace('.pdf', '')}"
        msg.attach(MIMEText(
            f"Презентационные материалы проекта Hermes.\n"
            f"Файл: {filename}\n"
            f"Сгенерировано: 18.07.2026\n\n"
            f"Архитектурная схема и три уровня прилагаются.",
            'plain'
        ))
        
        with open(filepath, 'rb') as f:
            part = MIMEBase('application', 'pdf')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
            msg.attach(part)
        
        server.sendmail(SENDER, TO, msg.as_string())
        print(f"✅ {filename} — отправлен")

print("\nГотово. Проверь почту gromyko.s@ibcon.ru")
