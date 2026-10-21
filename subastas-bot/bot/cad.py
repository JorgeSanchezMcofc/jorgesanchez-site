"""Datos del CAD (exenciones, uso agrícola, construcción) para las cuentas de la lista.

Los CAD publican su base certificada completa una vez al año. Se descarga, se
buscan solo las cuentas que salen en subasta y se guarda lo que importa en
cad_cache.json, para no bajar el archivo grande en cada corrida.
"""
import csv
import io
import json
import pathlib
import re
import zipfile

import requests

UA = {"User-Agent": "Mozilla/5.0 (subastas-bot; uso personal)"}
EXPORTS = {
    # Cameron: "Certified Data Export (simplified)", una fila por cuenta.
    "Cameron": "https://www.cameroncad.org/cad/exports/certified/2026/cameron-2026-GCC-certified-export-20260729.zip",
}


def solo_digitos(s):
    return re.sub(r"[^0-9A-Z]", "", str(s or "").upper())


def _filas(zpath):
    """Recorre las filas de cualquier CSV/TXT/XLSX dentro del zip como dicts."""
    with zipfile.ZipFile(zpath) as z:
        for name in z.namelist():
            low = name.lower()
            if low.endswith((".csv", ".txt")):
                with z.open(name) as fh:
                    head = fh.read(20000).decode("latin-1")
                dialect = csv.Sniffer().sniff(head.split("\n", 1)[0] + "\n", delimiters=",|\t;")
                with z.open(name) as fh:
                    rd = csv.DictReader(io.TextIOWrapper(fh, encoding="latin-1", newline=""), dialect=dialect)
                    for row in rd:
                        yield name, row
            elif low.endswith(".xlsx"):
                import openpyxl
                with z.open(name) as fh:
                    data = io.BytesIO(fh.read())
                wb = openpyxl.load_workbook(data, read_only=True, data_only=True)
                ws = wb.worksheets[0]
                it = ws.iter_rows(values_only=True)
                cols = [str(c or "").strip() for c in next(it)]
                for vals in it:
                    yield name, dict(zip(cols, ["" if v is None else str(v) for v in vals]))


def explorar(condado, cuentas, debug_dir):
    """Primera pasada: guarda los nombres de columnas y las filas de nuestras cuentas
    para ver el formato del archivo."""
    url = EXPORTS.get(condado)
    if not url:
        return
    debug = pathlib.Path(debug_dir)
    debug.mkdir(parents=True, exist_ok=True)
    zpath = debug.parent / f".cad_{condado}.zip"
    with requests.get(url, headers=UA, timeout=600, stream=True) as r:
        r.raise_for_status()
        with open(zpath, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    buscar = {solo_digitos(c) for c in cuentas}
    out = {"url": url, "archivos": [], "columnas": None, "ejemplo": None, "coinciden": []}
    with zipfile.ZipFile(zpath) as z:
        out["archivos"] = [(i.filename, i.file_size) for i in z.infolist()]
    for n, (name, row) in enumerate(_filas(zpath)):
        if out["columnas"] is None:
            out["columnas"] = list(row.keys())
            out["ejemplo"] = row
        if any(solo_digitos(v) in buscar for v in list(row.values())[:12] if v):
            out["coinciden"].append(row)
        if len(out["coinciden"]) >= 8 or n > 2_000_000:
            break
    (debug / f"cad_{condado}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    zpath.unlink(missing_ok=True)
