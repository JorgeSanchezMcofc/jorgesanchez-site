"""Datos del CAD (exenciones, uso agrícola, construcción, dueño) para las cuentas de la lista.

Los CAD publican su base certificada completa una vez al año. El robot la baja solo
cuando aparecen cuentas que todavía no tiene, toma únicamente esas cuentas y las
guarda en debug-listas/cad_cache.json. Así no baja el archivo grande cada semana.
"""
import io
import json
import pathlib
import re
import zipfile
from urllib.parse import quote_plus

import requests

from . import analisis

UA = {"User-Agent": "Mozilla/5.0 (subastas-bot; uso personal)"}
EXPORTS = {
    # Cameron: "Certified Data Export (simplified)", un Excel con una fila por cuenta.
    # Cada año cambia el nombre: actualizar desde https://www.cameroncad.org/Pages/Data
    "Cameron": {
        "url": "https://www.cameroncad.org/cad/exports/certified/2026/cameron-2026-GCC-certified-export-20260729.zip",
        "detalle": "https://cameron.prodigycad.com/property-detail/{pid}/{year}",
    },
}
CAMPOS_CAD = ["pID", "pYear", "geoID", "name", "exemptions", "stateCd", "agUse", "improvementValue", "landValue",
              "marketValue", "landTotalAcres", "yrBuilt", "zoning", "roadAccess", "utilities", "deedRecordedDt",
              "situsNum", "situsPrefix", "situsStreet", "situsSuffix", "situsCity", "situsZip"]
# Lo que se agrega a cada propiedad en data.json
CAMPOS = ("cad_ok", "dueno", "homestead", "agricola", "exenciones", "construccion", "anio_construccion",
          "zonificacion", "situs", "cad_detalle")


def norm(cuenta):
    return re.sub(r"[^0-9A-Z]", "", str(cuenta or "").upper())


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _filas_xlsx(data):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    it = wb.worksheets[0].iter_rows(values_only=True)
    cols = [str(c or "").strip() for c in next(it)]
    idx = {c: i for i, c in enumerate(cols)}
    for vals in it:
        yield {c: ("" if vals[i] is None else str(vals[i])) for c, i in idx.items() if c in CAMPOS_CAD}


def _descargar(condado, faltan):
    """Baja el export del condado y regresa {cuenta_normalizada: fila} solo de las que faltan."""
    url = EXPORTS[condado]["url"]
    r = requests.get(url, headers=UA, timeout=900)
    r.raise_for_status()
    encontradas = {}
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".xlsx"))
        for row in _filas_xlsx(z.read(name)):
            k = norm(row.get("geoID"))
            if k in faltan:
                encontradas[k] = row
                if len(encontradas) == len(faltan):
                    break
    return encontradas


def _resumen(filas, condado):
    """Junta una o varias cuentas (las que se venden juntas) en los datos que importan."""
    exen = sorted({e.strip() for f in filas for e in (f.get("exemptions") or "").split(",") if e.strip()})
    f0 = filas[0]
    situs = " ".join(x for x in (f0.get("situsNum"), f0.get("situsPrefix"), f0.get("situsStreet"),
                                  f0.get("situsSuffix")) if x).strip()
    ciudad = (f0.get("situsCity") or "").title()
    tpl = EXPORTS[condado]["detalle"]
    return {
        "cad_ok": True,
        "dueno": f0.get("name") or "",
        "homestead": any(e.upper().startswith("HS") for e in exen),
        "agricola": any(_num(f.get("agUse")) > 0 or (f.get("stateCd") or "").upper().startswith("D1") for f in filas),
        "exenciones": ", ".join(exen),
        "construccion": sum(_num(f.get("improvementValue")) for f in filas),
        "anio_construccion": next((f.get("yrBuilt") for f in filas if _num(f.get("yrBuilt")) > 1800), None),
        "zonificacion": f0.get("zoning") or "",
        "situs": f"{situs}, {ciudad}, TX {f0.get('situsZip') or ''}".strip() if situs and ciudad else "",
        "cad_detalle": tpl.format(pid=f0.get("pID"), year=f0.get("pYear")) if f0.get("pID") else "",
    }


def enriquecer(props, cache_path, cfg):
    """Agrega datos del CAD a cada propiedad. Regresa avisos (errores de descarga)."""
    cache_path = pathlib.Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    avisos = []
    for condado, info in EXPORTS.items():
        mias = [p for p in props if p["condado"] == condado]
        cuentas = {norm(c) for p in mias for c in p["cuenta"].split("&") if norm(c)}
        hoja = cache.setdefault(condado, {"url": info["url"], "cuentas": {}, "no_encontradas": []})
        if hoja.get("url") != info["url"]:  # salió el export de otro año: empezar de nuevo
            hoja.update(url=info["url"], cuentas={}, no_encontradas=[])
        faltan = cuentas - set(hoja["cuentas"]) - set(hoja["no_encontradas"])
        if faltan:
            try:
                nuevas = _descargar(condado, faltan)
                hoja["cuentas"].update(nuevas)
                hoja["no_encontradas"] = sorted(set(hoja["no_encontradas"]) | (faltan - set(nuevas)))
            except Exception as e:  # noqa: BLE001 (si el CAD falla, el resto del robot sigue)
                avisos.append(f"{condado}: no pude bajar los datos del CAD ({e}).")
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    for p in props:
        hoja = cache.get(p["condado"], {}).get("cuentas", {})
        filas = [hoja[norm(c)] for c in p["cuenta"].split("&") if norm(c) in hoja]
        if not filas:
            p.update({k: None for k in CAMPOS})
            continue
        p.update(_resumen(filas, p["condado"]))
        if not p.get("direccion") and p["situs"]:
            p["direccion"] = p["situs"]
            p["mapa"] = "https://www.google.com/maps/search/?api=1&query=" + quote_plus(p["situs"])
        if not p.get("ciudad") and p["situs"]:
            p["ciudad"] = p["situs"].split(",")[1].strip()
        p["baldio"] = p["construccion"] == 0  # el CAD sabe mejor que el estimado
        if p["cad_detalle"]:
            p["cad"] = p["cad_detalle"]
        riesgos = [r for r in (p.get("riesgos") or "").split("; ") if r]
        if re.search(r"\bEST(ATE)? OF\b|\bHEIRS\b|\bESTATE\b", p["dueno"].upper()) and \
                not any(r.startswith("Herencia") for r in riesgos):
            riesgos.insert(0, "Herencia: revisar título")
        if p["homestead"]:
            riesgos.append("Homestead: 2 años de redención")
        elif p["agricola"]:
            riesgos.append("Uso agrícola: 2 años de redención")
        p["riesgos"] = "; ".join(riesgos)
        analisis.puntuar(p, cfg)
    return avisos
