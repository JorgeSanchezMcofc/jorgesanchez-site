"""Descarga las listas de subasta de Perdue y Linebarger."""
import datetime as dt
import io
import re

import requests

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


DEBUG_DIR = None  # si se define, guarda las tablas de cada PDF para revisar el formato


def _pdf_pages(url):
    """Descarga un PDF y regresa [{"text":..., "tables":[...]}, ...] o None si no existe."""
    import json
    import pathlib
    import pdfplumber
    r = requests.get(url, headers=UA, timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    if not r.content.startswith(b"%PDF"):
        return None
    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        pages = [{"text": pg.extract_text() or "", "tables": pg.extract_tables()} for pg in pdf.pages]
    if DEBUG_DIR:
        d = pathlib.Path(DEBUG_DIR)
        d.mkdir(parents=True, exist_ok=True)
        name = url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        (d / f"{name}.plumber.json").write_text(json.dumps(pages, ensure_ascii=False, indent=1), encoding="utf-8")
    return pages


def perdue(slug):
    """Regresa [(tipo, url, texto)] para el condado en las páginas de Perdue."""
    out = []
    for tipo, page in PERDUE_PAGES.items():
        html = requests.get(page, headers=UA, timeout=60).text
        for href in re.findall(r'href="([^"]+\.pdf)"', html, re.I):
            name = href.rsplit("/", 1)[-1].lower()
            if name.startswith(slug) or re.match(rf"\d{{1,2}}-\d{{4}}{slug}", name):
                url = href if href.startswith("http") else page.rsplit("/", 1)[0] + "/" + href.lstrip("/")
                pages = _pdf_pages(url)
                if pages:
                    out.append((tipo, url, pages))
    return out


def linebarger(county, fecha):
    url = LGB_PDF.format(county=county.replace(" ", "_"), fecha=fecha.strftime("%Y%m%d"))
    pages = _pdf_pages(url)
    return [("Venta", url, pages)] if pages else []
