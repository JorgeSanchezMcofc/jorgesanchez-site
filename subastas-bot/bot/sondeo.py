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


LLAVES = ["95ab97a25034446d84379f1c42f2bc1e"]
ARCH = re.compile(r"https?://[^\"'\s<>]+?(?:\.zip|\.csv|\.xlsx?|\.txt|filedownload[^\"'\s<>]*)", re.I)


def contenido(debug_dir):
    """El texto de la página viene de un CMS público (Builder.io): buscar ahí los archivos."""
    out = {}
    for k in LLAVES:
        for ruta in ("/data-downloads",):
            try:
                r = requests.get("https://cdn.builder.io/api/v3/content/page",
                                 params={"apiKey": k, "url": ruta, "limit": 1}, headers=UA, timeout=60)
                t = r.text
                out[f"{k}{ruta}"] = {"status": r.status_code, "largo": len(t), "archivos": sorted(set(ARCH.findall(t)))[:200],
                                     "json": r.json() if r.ok else t}
            except requests.RequestException as e:
                out[f"{k}{ruta}"] = {"error": str(e)}
    p = pathlib.Path(debug_dir) / "sondeo_hidalgo_cms.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


def correr(debug_dir):
    contenido(debug_dir)
    return
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
