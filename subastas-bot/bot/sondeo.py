"""Temporal: revisa la página de descargas del CAD de Hidalgo para encontrar su archivo."""
import json
import pathlib
import re
from urllib.parse import urljoin

import requests

UA = {"User-Agent": "Mozilla/5.0 (subastas-bot; uso personal)"}
PAGINAS = ["https://www.hidalgoad.org/data-downloads", "https://www.hidalgoad.org/reports",
           "https://www.hidalgoad.org/"]
PAT = re.compile(r"""["'`]([^"'`\s]{0,200}(?:export|download|\.zip|\.csv|\.xlsx|/api/|appraisal)[^"'`\s]{0,200})["'`]""", re.I)


def correr(debug_dir):
    out = {}
    for url in PAGINAS:
        info = {}
        try:
            r = requests.get(url, headers=UA, timeout=60)
            info["status"] = r.status_code
            info["html"] = r.text[:3000]
            scripts = [urljoin(url, s) for s in re.findall(r'<script[^>]+src="([^"]+)"', r.text)]
            info["scripts"] = scripts
            hallazgos = set(PAT.findall(r.text))
            for s in scripts[:15]:
                try:
                    js = requests.get(s, headers=UA, timeout=60).text
                    hallazgos |= set(PAT.findall(js))
                    for m in re.finditer(r"https?://[a-z0-9.-]+\.[a-z]{2,}[^\"'`\s]{0,120}", js):
                        if re.search(r"api|export|download|blob|storage|amazonaws|azure", m.group(0), re.I):
                            hallazgos.add(m.group(0))
                except requests.RequestException as e:
                    info.setdefault("errores", []).append(f"{s}: {e}")
            info["hallazgos"] = sorted(hallazgos)[:400]
        except requests.RequestException as e:
            info["error"] = str(e)
        out[url] = info
    p = pathlib.Path(debug_dir) / "sondeo_hidalgo.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
