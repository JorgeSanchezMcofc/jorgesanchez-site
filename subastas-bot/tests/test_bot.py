import datetime as dt
import pathlib

import yaml

from bot import analisis, fuentes, parsers, salidas

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
HID, CAM = CFG["condados"]


def test_primer_martes():
    assert fuentes.proximo_primer_martes(dt.date(2026, 10, 19)) == dt.date(2026, 11, 3)
    assert fuentes.proximo_primer_martes(dt.date(2026, 11, 3)) == dt.date(2026, 11, 3)
    assert fuentes.proximo_primer_martes(dt.date(2026, 12, 2)) == dt.date(2027, 1, 5)


def test_perdue_cameron():
    r = parsers.parse_perdue((FIX / "cameron_perdue.txt").read_text())
    assert [p["cause"] for p in r] == ["2019-DCL02397", "2020-DCL04485", "2022-DCL05304",
                                        "2023-DCL04625", "2024-DCL00762"]
    assert (r[0]["valor"], r[0]["minimo"], r[0]["cuenta"]) == (23500.0, 9480.84, "7479601870010000")
    assert r[0]["legal"].startswith("1.092 acre")
    assert (r[3]["valor"], r[3]["minimo"]) == (66008.0, 25430.51)
    assert "DECEASED" in r[3]["demandado"]
    assert r[4]["legal"].startswith("Lot 5, Block 1")
    p = analisis.analizar(r[0], CAM, CFG)
    assert p["acres"] == 1.092


def test_linebarger_hidalgo():
    r = parsers.parse_linebarger((FIX / "hidalgo_linebarger.txt").read_text())
    assert len(r) == 8
    a = r[3]
    assert a["cuenta"] == "L0450-00-067-0002-00"
    assert a["direccion"] == "LA BLANCA RD (FM 493), DONNA, TX 78537"
    assert a["cause"] == "T-1363-18-C"
    assert (a["valor"], a["minimo"]) == (72756.0, 14392.93)
    assert a["estatus"] == "Cancelled"
    assert "DECEASED" in a["demandado"]
    assert "2021, 2022, 2023" in a["notas"]
    assert "HOMESITE 2.15 AC NET" in a["legal"]
    b = r[4]
    assert b["direccion"].startswith("W HOOKS AVE") and b["estatus"].startswith("Scheduled")
    assert r[6]["legal"].startswith("3.00 acres")
    assert r[7]["legal"].startswith("Lot Thirty-five")

    pa = analisis.analizar(a, HID, CFG)
    assert pa["acres"] == 2.15 and pa["baldio"] is True and pa["score"] == 0  # cancelada
    pb = analisis.analizar(b, HID, CFG)
    assert pb["acres"] == 1.21 and pb["baldio"] is True and pb["ciudad"] == "Donna"
    assert pb["impuestos_est"] > 0 and pb["score"] > 0
    assert analisis.analizar(r[6], HID, CFG)["acres"] == 0.43


def test_salidas(tmp_path):
    r = [analisis.analizar(p, HID, CFG)
         for p in parsers.parse_linebarger((FIX / "hidalgo_linebarger.txt").read_text())]
    for p in r:
        p["pdf"], p["fecha_subasta"] = "x", "2026-08-04"
    r.sort(key=lambda p: p["score"], reverse=True)
    salidas.guardar_csv(r, tmp_path / "p.csv")
    html = salidas.reporte_html(r, dt.date(2026, 8, 4), 10, ["aviso"])
    assert "W HOOKS AVE" in html and (tmp_path / "p.csv").exists()
