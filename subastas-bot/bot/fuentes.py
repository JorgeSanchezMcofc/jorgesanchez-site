"""Descarga las listas de subasta de Perdue y Linebarger."""
import datetime as dt
import io
import re

import requests
from pdfminer.high_level import extract_text

UA = {"User-Agent": "Mozilla/5.0 (subastas-bot; uso personal)"}
PERDUE_PAGES = {
    "Venta": "https://pbfcm.com/taxsale.html",
    "Reventa": "https://www.pbfcm.com/taxresale.html",
}
LGB_PDF = ("https://taxsalesib.lgbs.com/images/lit_ps_images/ib-emails/"
           "County_Sale_list_{county}_{fecha}.pdf")


def proximo_primer_martes(hoy=None):
    hoy = hoy or dt.date.today()
    for mes in (0, 1):
        y, m = hoy.year + (hoy.month + mes - 1) // 12, (hoy.month + mes - 1) % 12 + 1
        d = dt.date(y, m, 1)
        d += dt.timedelta(days=(1 - d.weekday()) % 7)
        if d >= hoy:
            return d
    raise RuntimeError("sin fecha")


DEBUG_DIR = None  # si se define, guarda el texto crudo de cada PDF para revisar el formato


def _pdf_text(url):
    r = requests.get(url, headers=UA, timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    if not r.content.startswith(b"%PDF"):
        return None
    txt = extract_text(io.BytesIO(r.content))
    if DEBUG_DIR:
        import json
        import pathlib
        import pdfplumber
        d = pathlib.Path(DEBUG_DIR)
        d.mkdir(parents=True, exist_ok=True)
        name = url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        (d / f"{name}.pdfminer.txt").write_text(txt, encoding="utf-8")
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            pages = [{"text": pg.extract_text() or "", "tables": pg.extract_tables()} for pg in pdf.pages]
        (d / f"{name}.plumber.json").write_text(json.dumps(pages, ensure_ascii=False, indent=1), encoding="utf-8")
    return txt


def perdue(slug):
    """Regresa [(tipo, url, texto)] para el condado en las páginas de Perdue."""
    out = []
    for tipo, page in PERDUE_PAGES.items():
        html = requests.get(page, headers=UA, timeout=60).text
        for href in re.findall(r'href="([^"]+\.pdf)"', html, re.I):
            name = href.rsplit("/", 1)[-1].lower()
            if name.startswith(slug) or re.match(rf"\d{{1,2}}-\d{{4}}{slug}", name):
                url = href if href.startswith("http") else page.rsplit("/", 1)[0] + "/" + href.lstrip("/")
                txt = _pdf_text(url)
                if txt:
                    out.append((tipo, url, txt))
    return out


def linebarger(county, fecha):
    url = LGB_PDF.format(county=county.replace(" ", "_"), fecha=fecha.strftime("%Y%m%d"))
    txt = _pdf_text(url)
    return [("Venta", url, txt)] if txt else []
