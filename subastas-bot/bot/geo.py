"""Ubicación (lat/lng) y zona de inundación de FEMA para cada propiedad.

Se consulta una sola vez por propiedad: data.json guarda el resultado y la siguiente
corrida lo reutiliza. Si un servicio falla, la propiedad queda sin ese dato y se
vuelve a intentar la próxima vez.
"""
import re
import time

import requests

ACTIVO = True  # los tests lo apagan para no salir a internet
VERSION = 1
UA = {"User-Agent": "subastas-bot/1.0 (uso personal; jorgesanchez.me)"}

CENSUS = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
FEMA = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"

CAMPOS = ("lat", "lng", "flood_zona", "flood_riesgo", "geo_v")


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
    if j and j[0].get("class") in ("building", "place", "highway", "amenity", "landuse", "shop", "office"):
        return float(j[0]["lat"]), float(j[0]["lon"])
    return None


def ubicar(direccion):
    """(lat, lng) de una dirección con número o calle; None si no se encuentra."""
    q = _limpia(direccion)
    if not q or not re.search(r",\s*TX", q, re.I):
        return None
    for fn in (_census, _nominatim):
        try:
            pt = fn(q)
            if pt and 25.5 < pt[0] < 27.0 and -98.9 < pt[1] < -97.0:  # dentro del Valle
                return pt
        except (requests.RequestException, KeyError, ValueError, IndexError):
            continue
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
        pt = ubicar(p.get("direccion"))
        if pt:
            p["lat"], p["lng"] = round(pt[0], 6), round(pt[1], 6)
    if p.get("lat") is not None and p.get("flood_zona") is None:
        try:
            f = inundacion(p["lat"], p["lng"])
            if f:
                p["flood_zona"], p["flood_riesgo"] = f
        except (requests.RequestException, KeyError, ValueError):
            pass
    p["geo_v"] = VERSION
    return p
