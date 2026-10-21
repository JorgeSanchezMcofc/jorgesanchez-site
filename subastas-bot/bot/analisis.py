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


def baldio(direccion, legal):
    """Estimado: sin número de casa en la dirección = probablemente terreno baldío."""
    if direccion:
        return not re.match(r"^\s*\d", direccion)
    return None  # sin dirección (Perdue): no se sabe hasta revisar el CAD


def anios_atrasados(notas):
    return len(re.findall(r"\b20\d{2}\b", notas or ""))


def ciudad(direccion):
    m = re.search(r",\s*([A-Z .]+),\s*TX", direccion or "")
    return m.group(1).title() if m else ""


def analizar(p, condado, cfg):
    crit, puja = cfg["criterios"], cfg["puja"]
    p["condado"] = condado["nombre"]
    p["acres"] = acres(p["legal"])
    p["baldio"] = baldio(p["direccion"], p["legal"])
    p["ciudad"] = ciudad(p["direccion"])
    years = anios_atrasados(p["notas"])
    valor, minimo = p.get("valor") or 0, p.get("minimo") or 0

    riesgos = []
    d = (p.get("demandado") or "").upper()
    if "DECEASED" in d or "HEIRS" in d:
        riesgos.append("Dueño fallecido / herederos (revisar título)")
    if "ET AL" in d:
        riesgos.append("Varios demandados")
    if years:
        riesgos.append(f"Debes pagar aparte impuestos de {years} año(s)")
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
    if "fallecido" in p["riesgos"]:
        s -= 5
    if not p["conviene"]:
        s -= 15
    if "cancel" in (p.get("estatus") or "").lower():
        s = 0
    p["score"] = int(max(0, min(100, round(s))))

    q = p["direccion"] or f'{p["legal"][:80]} {condado["nombre"]} County TX'
    p["mapa"] = "https://www.google.com/maps/search/?api=1&query=" + quote_plus(q)
    p["cad"] = condado["cad"]
    return p
