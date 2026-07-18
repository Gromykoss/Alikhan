#!/usr/bin/env python3
"""Convert PRESENTATION_PITCH.md and CLIENT_GUIDE.md to PDF with images."""

import markdown
from weasyprint import HTML
import base64
import os

BASE = "/home/hermes-workspace/Alikhan-migration"
OUT = f"{BASE}/output_pdf"
os.makedirs(OUT, exist_ok=True)

def img_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

arch_b64 = img_b64(f"{OUT}/arch_diagram.png")
tiers_b64 = img_b64(f"{OUT}/tiers_diagram.png")

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

body {
    font-family: 'Inter', 'Segoe UI', 'DejaVu Sans', sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #1a1a1a;
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
}

h1 {
    font-size: 24pt;
    font-weight: 700;
    color: #0d47a1;
    border-bottom: 3px solid #0d47a1;
    padding-bottom: 8px;
    margin-top: 30px;
}

h2 {
    font-size: 18pt;
    font-weight: 600;
    color: #1565c0;
    margin-top: 24px;
}

h3 {
    font-size: 14pt;
    font-weight: 600;
    color: #1976d2;
}

strong { color: #0d47a1; }

table {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    font-size: 9.5pt;
}

th {
    background: #0d47a1;
    color: white;
    padding: 8px 12px;
    text-align: left;
    font-weight: 600;
}

td {
    padding: 8px 12px;
    border-bottom: 1px solid #e0e0e0;
}

tr:nth-child(even) { background: #f5f8ff; }

code {
    background: #e3f2fd;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'Courier New', monospace;
    font-size: 9.5pt;
}

hr {
    border: none;
    border-top: 1px solid #e0e0e0;
    margin: 24px 0;
}

blockquote {
    border-left: 4px solid #0d47a1;
    padding: 8px 16px;
    background: #f5f8ff;
    margin: 16px 0;
}

.page-break { page-break-before: always; }

.diagram {
    text-align: center;
    margin: 24px 0;
}

.diagram img {
    max-width: 100%;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.diagram .caption {
    font-size: 10pt;
    color: #666;
    margin-top: 8px;
}
"""

# --- PITCH with images ---
with open(f"{BASE}/PRESENTATION_PITCH.md") as f:
    pitch_md = f.read()

# Insert architecture diagram after section 2
pitch_md = pitch_md.replace(
    "## 3. Пакеты Hermes:",
    f'<div class="diagram"><img src="data:image/png;base64,{arch_b64}" alt="Architecture"><div class="caption">Архитектура Hermes + Alikhan</div></div>\n\n## 3. Пакеты Hermes:'
)

# Insert tiers diagram after section 5 (three levels)
pitch_md = pitch_md.replace(
    "## 6. Конкуренты:",
    f'<div class="diagram"><img src="data:image/png;base64,{tiers_b64}" alt="Three tiers"><div class="caption">Три уровня Hermes</div></div>\n\n## 6. Конкуренты:'
)

html_body = markdown.markdown(pitch_md, extensions=['tables', 'fenced_code', 'codehilite'])
html = f"<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'><style>{CSS}</style></head><body>{html_body}</body></html>"
HTML(string=html).write_pdf(f"{OUT}/PRESENTATION_PITCH.pdf")
print(f"✅ PRESENTATION_PITCH.pdf ({os.path.getsize(f'{OUT}/PRESENTATION_PITCH.pdf')/1024:.0f} KB)")

# --- GUIDE with images ---
with open(f"{BASE}/CLIENT_GUIDE.md") as f:
    guide_md = f.read()

guide_md = guide_md.replace(
    "## 2. Как это работает",
    f'<div class="diagram"><img src="data:image/png;base64,{arch_b64}" alt="Architecture"><div class="caption">Архитектура Hermes + Alikhan</div></div>\n\n## 2. Как это работает'
)

guide_md = guide_md.replace(
    "### Три уровня",
    f'<div class="diagram"><img src="data:image/png;base64,{tiers_b64}" alt="Three tiers"><div class="caption">Три уровня Hermes</div></div>\n\n### Три уровня'
)

html_body = markdown.markdown(guide_md, extensions=['tables', 'fenced_code', 'codehilite'])
html = f"<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'><style>{CSS}</style></head><body>{html_body}</body></html>"
HTML(string=html).write_pdf(f"{OUT}/CLIENT_GUIDE.pdf")
print(f"✅ CLIENT_GUIDE.pdf ({os.path.getsize(f'{OUT}/CLIENT_GUIDE.pdf')/1024:.0f} KB)")

print("\nГотово — PDF с иллюстрациями в output_pdf/")
