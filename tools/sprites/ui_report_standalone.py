#!/usr/bin/env python3
"""Gera uma cópia autocontida do report de UI (todas as imagens em base64 num HTML só).

    python3 tools/sprites/ui_report_standalone.py [saída]   (padrão: ~/Desktop/hesper_ui_redesign.html)
"""
import base64
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "design" / "ui_redesign" / "index.html"
out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Desktop" / "hesper_ui_redesign.html"

html = REPORT.read_text()
html = re.sub(r'<a href="[^"]+\.png">(.*?)</a>', r"\1", html)      # links pra imagem cheia: sem o arquivo, sai
cache = {}


def inline(m):
    src = m.group(1)
    if src.startswith(("data:", "http")):
        return m.group(0)
    if src not in cache:
        data = (REPORT.parent / src).resolve().read_bytes()
        cache[src] = "data:image/png;base64," + base64.b64encode(data).decode()
    return f'src="{cache[src]}"'


html = re.sub(r'src="([^"]+)"', inline, html)
out.write_text(html)
print(out, f"{out.stat().st_size / 1e6:.1f} MB", len(cache), "imagens")
