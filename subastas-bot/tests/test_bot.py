"""Pruebas con las listas reales del 3 de noviembre de 2026."""
import datetime as dt
import json
import pathlib

import yaml

from bot import analisis, dashboard, fuentes, geo, parsers, salidas

geo.ACTIVO = False  # sin internet en los tests

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
HID, CAM = CFG["condados"]


def pages(name):
    return json.loads((FIX / name).read_text())


def test_primer_martes():
    assert fuentes.proximo_primer_martes(dt.date(2026, 10, 19)) == dt.date(2026, 11, 3)
    assert fuentes.proximo_primer_martes(dt.date(2026, 11, 3)) == dt.date(2026, 11, 3)
    assert fuentes.proximo_primer_martes(dt.date(2026, 12, 2)) == dt.date(2027, 1, 5)


def test_linebarger_hidalgo():
    r = parsers.parse_linebarger(pages("hidalgo_lgbs.json"))
    assert len(r) == 31
    assert all(p["fecha_lista"] == "2026-11-03" and p["legal"] and p["valor"] for p in r)
    p = r[0]
    assert (p["cuenta"], p["cause"], p["valor"], p["minimo"]) == ("T2100-00-252-0008-20", "T-1271-14-F", 41045.0, 15770.63)
    assert p["direccion"] == "ROGERS RD, EDINBURG, TX 78539"
    assert p["estatus"] == "Scheduled for Online Auction"
    assert p["notas"] == "Sujeto a impuestos 2021, 2022, 2023, 2024, 2025"
    alton = next(x for x in r if x["cuenta"] == "S2950-00-000-0401-16")
    a = analisis.analizar(alton, HID, CFG)
    assert a["acres"] == 1.11 and a["baldio"] is True and a["ciudad"] == "Alton"  # 20.22 menos excepciones


def test_linebarger_cameron():
    r = parsers.parse_linebarger(pages("cameron_lgbs.json"))
    assert len(r) == 22
    assert all(p["legal"] for p in r)
    sb = next(x for x in r if x["cuenta"] == "9096800210031000")
    assert "TX 78586" in sb["direccion"] and "TX 78586" not in sb["notas"]
    assert analisis.analizar(r[1], CAM, CFG)["notas"].startswith("Sujeto a impuestos 2025, 2026")


def test_perdue_cameron():
    r = parsers.parse_perdue(pages("cameron_perdue.json"))
    assert len(r) == 12 and r[0]["fecha_lista"] == "2026-11-03"
    assert (r[0]["cause"], r[0]["valor"], r[0]["minimo"], r[0]["cuenta"]) == \
        ("2019-DCL-02397", 23500.0, 9480.84, "7479601870010000")
    assert analisis.analizar(r[0], CAM, CFG)["acres"] == 1.092
    p = analisis.analizar(r[-1], CAM, CFG)
    assert p["acres"] == 0.5


def test_perdue_reventa():
    r = parsers.parse_perdue(pages("cameron_perdue_reventa.json"))
    assert {p["tipo"] for p in r} == {"Reventa"} and r[0]["fecha_lista"] == "2026-03-03"
    assert any(analisis.acres(p["legal"]) and analisis.acres(p["legal"]) > 10 for p in r)


def test_salidas_y_dashboard(tmp_path):
    r = [analisis.analizar(p, HID, CFG) for p in parsers.parse_linebarger(pages("hidalgo_lgbs.json"))]
    for p in r:
        p["pdf"], p["fecha_subasta"] = "x", "2026-11-03"
    r.sort(key=lambda p: p["score"], reverse=True)
    assert r[0]["score"] >= r[-1]["score"]
    salidas.guardar_csv(r, tmp_path / "p.csv")
    assert "DONNA" in salidas.reporte_html(r, dt.date(2026, 11, 3), 10, [])
    dashboard.escribir(r, tmp_path / "data.json", tmp_path / "no.yaml", dt.date(2026, 11, 3), [])
    d = json.loads((tmp_path / "data.json").read_text())
    assert len(d["propiedades"]) == 31 and d["ganadas"] == []


def test_geo_limpia_y_reutiliza():
    assert "REAR" not in geo._limpia("819 S 5TH ST (REAR), HIDALGO, TX 78557")
    assert "78557-1234" not in geo._limpia("819 S 5TH ST, HIDALGO, TX 78557-1234")
    prev = {"lat": 26.1, "lng": -98.2, "flood_zona": "AE", "flood_riesgo": True, "geo_v": geo.VERSION}
    p = geo.enriquecer({"direccion": "x"}, prev)
    assert p["flood_zona"] == "AE" and p["lat"] == 26.1
