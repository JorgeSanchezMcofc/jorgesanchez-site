"""Corre todo: descarga, analiza, actualiza el Sheet y manda el correo.

Uso:  python -m bot.main            (normal)
      python -m bot.main --fecha 2026-11-03 --sin-correo
"""
import argparse
import datetime as dt
import os
import pathlib

import yaml

from . import analisis, dashboard, fuentes, parsers, salidas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fecha", help="fecha de la subasta AAAA-MM-DD (default: próximo primer martes)")
    ap.add_argument("--sin-correo", action="store_true")
    ap.add_argument("--json", help="dónde escribir data.json para el dashboard")
    args = ap.parse_args()

    root = pathlib.Path(__file__).resolve().parent.parent
    cfg = yaml.safe_load((root / "config.yaml").read_text())
    fecha = dt.date.fromisoformat(args.fecha) if args.fecha else fuentes.proximo_primer_martes()
    out_dir = root / "salida"
    out_dir.mkdir(exist_ok=True)

    props, avisos = [], []
    for c in cfg["condados"]:
        listas = []
        try:
            listas += fuentes.linebarger(c["linebarger"], fecha)
        except Exception as e:
            avisos.append(f"{c['nombre']}: error con Linebarger ({e})")
        try:
            listas += fuentes.perdue(c["perdue"])
        except Exception as e:
            avisos.append(f"{c['nombre']}: error con Perdue ({e})")
        if not listas:
            avisos.append(f"{c['nombre']}: todavía no publican lista para el {fecha:%d/%m}.")
        for tipo, url, txt in listas:
            regs = parsers.parse_linebarger(txt) if "lgbs.com" in url else parsers.parse_perdue(txt)
            if not regs:
                avisos.append(f"{c['nombre']}: no pude leer {url} (revisar formato).")
            for p in regs:
                if tipo == "Reventa":
                    p["tipo"] = "Reventa"
                p["pdf"], p["fecha_subasta"] = url, fecha.isoformat()
                props.append(analisis.analizar(p, c, cfg))

    props.sort(key=lambda p: p["score"], reverse=True)
    salidas.guardar_csv(props, out_dir / "propiedades.csv")
    cuerpo = salidas.reporte_html(props, fecha, cfg["correo"]["top"], avisos)
    (out_dir / "reporte.html").write_text(cuerpo, encoding="utf-8")
    print(f"{len(props)} propiedades. Avisos: {avisos or 'ninguno'}")
    if args.json:
        dashboard.escribir(props, args.json, root / "ganadas.yaml", fecha, avisos)
        print(f"Dashboard actualizado: {args.json}")

    if os.getenv("SHEET_ID") and os.getenv("GOOGLE_SA_JSON"):
        nuevos = salidas.actualizar_sheet(props, os.environ["SHEET_ID"], os.environ["GOOGLE_SA_JSON"])
        print(f"Sheet actualizado ({nuevos} nuevas).")
    if not args.sin_correo and os.getenv("SMTP_USER") and os.getenv("SMTP_PASS"):
        salidas.enviar_correo(f"Subastas {fecha:%d/%m}: top {cfg['correo']['top']} en Hidalgo y Cameron",
                              cuerpo, cfg["correo"]["para"], os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        print("Correo enviado.")


if __name__ == "__main__":
    main()
