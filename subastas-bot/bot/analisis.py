"""Acres, terreno baldío, riesgos, score y puja máxima sugerida."""
import re
from urllib.parse import quote_plus

ACRES = re.compile(r"(\d+(?:\.\d+)?)\s*(?:acres?|AC)\b", re.I)
NET = re.compile(r"(\d+(?:\.\d+)?)\s*(?:AC|acres?)\s*NET", re.I)
RESIDUE = re.compile(r"residue of (\d+(?:\.\d+)?)\s*acres?", re.I)


def acres(legal):
    """Acres según la descripción legal. Si hay 'NET' o 'residue', usa ese."""
    for rx in (NET, RESIDUE):
        m = rx.search(legal or "")
        if m:
            return float(m.group(1))
    m = ACRES.search(legal or "")
    if not m:
        return None
    a = float(m.group(1))
    if re.search(r"\b1/2 OF A\s*$", (legal or "")[: m.start()].upper().strip() + " ", re.I) or \
       re.search(r"1/2 OF A\s+" + re.escape(m.group(0)), legal or "", re.I):
        a /= 2
    return a


SUBDIV = re.compile(
    r"([A-Za-z][A-Za-z0-9'. &-]{2,50}?)\s+(Subdivision|Subd\b|Estates?|Townsite|Heights|Grant|Orchards|Village|Acres)\b", re.I)
CITY = re.compile(r"City of ([A-Za-z ]+?)[,.]", re.I)


def zona(legal):
    """Nombre corto de la subdivisión o zona, para mostrar en vez del texto legal."""
    for m in SUBDIV.finditer(legal or ""):
        name = re.sub(r"^(.*\b(of|in|the|and|out|being)\s+)", "", m.group(1), flags=re.I).strip()
        if len(name) < 3 or re.match(r"^(a|an|said|this)$", name, re.I):
            continue
        if m.group(2).lower() == "acres" and re.search(r"\d|containing|^(north|south|east|west)", name, re.I):
            continue  # es una medida ("3.66 acres"), no un nombre
        word = m.group(2).lower()
        name = name + ("" if word.startswith("subd") else " " + m.group(2))
        return name.title().replace("'S", "'s")
    for part in (legal or "").split(","):
        part = part.strip()
        if part and not re.match(r"^(lots?|block|all|\d|the|being|tract|a )", part, re.I):
            return part.title()[:40]
    return ""


def baldio(direccion, legal):
    """Estimado: sin número de casa en la dirección = probablemente terreno baldío."""
    if re.search(r"\bbldg\b|building|improvements", legal or "", re.I):
        return False
    if direccion:
        return not re.match(r"^\s*\d", direccion)
    return None  # sin dirección (Perdue): no se sabe hasta revisar el CAD


def anios_atrasados(notas):
    return len(re.findall(r"\b20\d{2}\b", notas or ""))


CIUDADES = ["McAllen", "Edinburg", "Mission", "Pharr", "Weslaco", "Donna", "Mercedes", "San Juan", "Alamo",
            "La Joya", "Penitas", "Palmview", "Alton", "Elsa", "Edcouch", "La Villa", "Progreso", "Sullivan City",
            "Hidalgo", "Brownsville", "Harlingen", "San Benito", "Los Fresnos", "Port Isabel", "Rio Hondo",
            "Santa Rosa", "La Feria", "Combes", "Primera", "Palm Valley", "Laguna Vista", "South Padre Island",
            "Rancho Viejo", "Olmito", "Lozano", "Bayview", "Los Indios"]


def ciudad(direccion):
    m = re.search(r",\s*([A-Z .]+),\s*TX", direccion or "")
    if m:
        return m.group(1).strip().title().replace("Mcallen", "McAllen")
    up = (direccion or "").upper()
    for c in CIUDADES:
        if re.search(rf"\b{c.upper()}\b", up):
            return c
    return ""


def analizar(p, condado, cfg):
    crit, puja = cfg["criterios"], cfg["puja"]
    p["condado"] = condado["nombre"]
    p["acres"] = acres(p["legal"])
    aprox = re.search(r"approximately ([\d.]+) acres", p.get("notas") or "", re.I)
    if aprox:  # la nota del despacho manda sobre la descripción legal
        p["acres"] = float(aprox.group(1))
    p["baldio"] = baldio(p["direccion"], p["legal"])
    p["ciudad"] = ciudad(p["direccion"])
    if not p["ciudad"]:
        m = CITY.search(p["legal"] or "")
        p["ciudad"] = m.group(1).strip().title() if m else ""
    p["zona"] = zona(p["legal"])
    if p["acres"] and p["acres"] >= 0.5:
        p["titulo"] = f'Terreno de {p["acres"]:g} acres'
    elif re.match(r"\s*(all of\s+)?lots?\b", p["legal"] or "", re.I):
        p["titulo"] = "Lote"
    else:
        p["titulo"] = "Terreno"
    years = anios_atrasados(p["notas"])
    valor, minimo = p.get("valor") or 0, p.get("minimo") or 0

    riesgos = []
    d = (p.get("demandado") or "").upper()
    if "DECEASED" in d or "HEIRS" in d:
        riesgos.append("Herencia: revisar título")
    if years:
        riesgos.append(f"+{years} año{'s' if years > 1 else ''} de impuestos por pagar")
    p["riesgos"] = "; ".join(riesgos)

    # Impuestos que el comprador hereda (los años 'subject to')
    p["impuestos_est"] = round(valor * condado["tasa_impuesto"] * years, 2)

    # Puja máxima
    tope = valor * puja["pct_del_valor"] - puja["costo_quiet_title"] - puja["costo_survey"] - p["impuestos_est"]
    p["puja_max"] = round(max(tope, 0), -2)
    p["conviene"] = bool(valor) and p["puja_max"] >= minimo

    # Score 0-100
    s = 0.0
    if p["acres"]:
        s += 35 * min(p["acres"] / crit["acres_objetivo"], 1)
        if p["acres"] < crit["acres_minimo"]:
            s -= 5
    if p["baldio"]:
        s += 20
    if valor and minimo:
        s += 25 * max(0, 1 - minimo / valor)
    if p["tipo"] == "Reventa":
        s += 5
    s -= 3 * max(0, years - 1)
    if "Herencia" in p["riesgos"]:
        s -= 5
    if not p["conviene"]:
        s -= 15
    if "cancel" in (p.get("estatus") or "").lower():
        s = 0
    p["score"] = int(max(0, min(100, round(s))))

    q = p["direccion"] or f'{p["zona"]} {p["ciudad"] or condado["nombre"] + " County"} TX'
    p["mapa"] = "https://www.google.com/maps/search/?api=1&query=" + quote_plus(q)
    p["cad"] = condado["cad"]
    return p
