"""Ubicación (lat/lng) y zona de inundación de FEMA para cada propiedad.

Se consulta una sola vez por propiedad: data.json guarda el resultado y la siguiente
corrida lo reutiliza. Si un servicio falla, la propiedad queda sin ese dato y se
vuelve a intentar la próxima vez.
"""
import re
import time

import requests

ACTIVO = True  # los tests lo apagan para no salir a internet
VERSION = 2
UA = {"User-Agent": "subastas-bot/1.0 (uso personal; jorgesanchez.me)"}

CENSUS = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
PHOTON = "https://photon.komoot.io/api/"
FEMA = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"

DEMASIADO_GENERAL = ("city", "town", "village", "county", "state", "country", "administrative", "postcode")

CAMPOS = ("lat", "lng", "geo_aprox", "flood_zona", "flood_riesgo", "geo_v")


def _limpia(direccion):
    d = re.sub(r"\((?:REAR|FRONT)\)", "", direccion or "", flags=re.I)
    d = re.sub(r"(\d{5})-\d{4}\b", r"\1", d)  # el ZIP+4 confunde a los geocodificadores
    return re.sub(r"\s+", " ", d).strip(" ,")


def _census(q):
    r = requests.get(CENSUS, params={"address": q, "benchmark": "Public_AR_Current", "format": "json"},
                     headers=UA, timeout=30)
    r.raise_for_status()
    m = r.json()["result"]["addressMatches"]
    if m:
        return m[0]["coordinates"]["y"], m[0]["coordinates"]["x"]
    return None


def _nominatim(q):
    time.sleep(1.1)  # su política: máximo una consulta por segundo
    r = requests.get(NOMINATIM, params={"q": q, "format": "json", "limit": 1, "countrycodes": "us"},
                     headers=UA, timeout=30)
    r.raise_for_status()
    j = r.json()
    if not j or j[0].get("class") == "boundary" or j[0].get("type") in DEMASIADO_GENERAL:
        return None  # el centro de una ciudad o condado no sirve como ubicación
    return float(j[0]["lat"]), float(j[0]["lon"])


def _photon(q):
    time.sleep(0.5)
    r = requests.get(PHOTON, params={"q": q, "limit": 1, "lat": 26.2, "lon": -97.9}, headers=UA, timeout=30)
    r.raise_for_status()
    f = r.json().get("features") or []
    if f and f[0]["properties"].get("type") not in DEMASIADO_GENERAL:
        lng, lat = f[0]["geometry"]["coordinates"][:2]
        return lat, lng
    return None


def _en_valle(pt):
    return pt and 25.5 < pt[0] < 27.0 and -98.9 < pt[1] < -97.0


def _probar(q, fuentes):
    for fn in fuentes:
        try:
            pt = fn(q)
            if _en_valle(pt):
                return pt
        except (requests.RequestException, KeyError, ValueError, IndexError, TypeError):
            continue
    return None


def ubicar(p, condado=""):
    """(lat, lng, aproximada). Primero la dirección exacta; si no, la calle y la ciudad;
    si no, la colonia o subdivisión. None si nada funciona."""
    d = _limpia(p.get("direccion"))
    ciudad = p.get("ciudad") or ""
    if not ciudad:  # "Town of Lozano" / "City of Lozano" en la descripción legal
        m = re.search(r"(?:town|city) of ([a-z ]+?)(?:[,.]| -|$)", f'{p.get("zona", "")} {p.get("legal", "")}', re.I)
        ciudad = m.group(1).strip().title() if m else ""
    lugar = ciudad or (f"{condado} County" if condado else "")
    if d and re.match(r"^\d", d) and re.search(r",\s*TX", d, re.I):
        pt = _probar(d, (_census, _nominatim, _photon))
        if pt:
            return pt[0], pt[1], False
    calle = re.sub(r",.*$", "", d).strip() if d else ""
    calle = re.sub(r"^\d+[A-Z]?\s+", "", calle)
    if calle and lugar:
        pt = _probar(f"{calle}, {lugar}, TX", (_nominatim, _photon))
        if pt:
            return pt[0], pt[1], True
    zona = p.get("zona") or ""
    if zona and lugar:
        pt = _probar(f"{zona}, {lugar}, TX", (_nominatim, _photon))
        if pt:
            return pt[0], pt[1], True
    return None


def inundacion(lat, lng):
    """(zona, en_zona_de_riesgo) según el mapa de FEMA; None si no responde."""
    r = requests.get(FEMA, params={
        "geometry": f"{lng},{lat}", "geometryType": "esriGeometryPoint", "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects", "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF",
        "returnGeometry": "false", "f": "json"}, headers=UA, timeout=45)
    r.raise_for_status()
    feats = r.json().get("features") or []
    if not feats:
        return None
    a = feats[0]["attributes"]
    zona = (a.get("FLD_ZONE") or "").strip()
    if a.get("ZONE_SUBTY") and "0.2" in a["ZONE_SUBTY"]:
        zona = "X (0.2%)"
    return zona, a.get("SFHA_TF") == "T"


def enriquecer(p, prev=None):
    """Agrega lat/lng y zona de inundación, reutilizando lo de la corrida anterior."""
    prev = prev or {}
    if prev.get("geo_v") == VERSION and prev.get("lat") is not None and prev.get("flood_zona") is not None:
        for k in CAMPOS:
            p[k] = prev.get(k)
        return p
    for k in CAMPOS:
        p.setdefault(k, prev.get(k))
    if not ACTIVO:
        return p
    if p.get("lat") is None:
        pt = ubicar(p, p.get("condado", ""))
        if pt:
            p["lat"], p["lng"], p["geo_aprox"] = round(pt[0], 6), round(pt[1], 6), pt[2]
    if p.get("lat") is not None and not p.get("geo_aprox") and p.get("flood_zona") is None:
        try:
            f = inundacion(p["lat"], p["lng"])
            if f:
                p["flood_zona"], p["flood_riesgo"] = f
        except (requests.RequestException, KeyError, ValueError):
            pass
    p["geo_v"] = VERSION
    return p
