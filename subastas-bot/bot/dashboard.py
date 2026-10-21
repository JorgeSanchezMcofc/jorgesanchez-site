"""Genera data.json para jorgesanchez.me/subastas: historial de listas + propiedades ganadas."""
import datetime as dt
import json
import pathlib

import yaml

CAMPOS = ["condado", "fecha_subasta", "tipo", "cause", "cuenta", "direccion", "ciudad", "legal",
          "acres", "baldio", "minimo", "valor", "puja_max", "conviene", "impuestos_est", "score",
          "riesgos", "estatus", "mapa", "cad", "pdf", "visto"]


def _key(p):
    return f'{p["condado"]}|{p["cuenta"]}|{p["cause"]}'


def ganadas(path, hoy=None):
    """Lee ganadas.yaml y calcula cuándo vence la redención de cada una."""
    hoy = hoy or dt.date.today()
    if not pathlib.Path(path).exists():
        return []
    data = yaml.safe_load(pathlib.Path(path).read_text()) or {}
    out = []
    for g in data.get("ganadas") or []:
        inicio = g.get("fecha_deed") or g.get("fecha_compra")
        inicio = inicio if isinstance(inicio, dt.date) else dt.date.fromisoformat(str(inicio))
        dias = int(g.get("dias_redencion", 180))
        vence = inicio + dt.timedelta(days=dias)
        precio = float(g.get("precio", 0))
        # Si el dueño redime: 25% el primer año, 50% el segundo (Tax Code 34.21)
        pen = 0.25 if (hoy - inicio).days <= 365 else 0.50
        out.append({
            **{k: (v.isoformat() if isinstance(v, dt.date) else v) for k, v in g.items()},
            "inicio_redencion": inicio.isoformat(),
            "vence": vence.isoformat(),
            "dias_restantes": (vence - hoy).days,
            "si_redimen_recibes": round(precio * (1 + pen), 2),
        })
    out.sort(key=lambda g: g["vence"])
    return out


def escribir(props, json_path, ganadas_path, fecha, avisos):
    json_path = pathlib.Path(json_path)
    viejo = {}
    if json_path.exists():
        try:
            viejo = {_key(p): p for p in json.loads(json_path.read_text()).get("propiedades", [])}
        except (ValueError, KeyError):
            viejo = {}
    hoy = dt.date.today().isoformat()
    for p in props:
        prev = viejo.get(_key(p))
        p["visto"] = (prev or {}).get("visto") or hoy
        viejo[_key(p)] = {k: p.get(k) for k in CAMPOS}
    todas = sorted(viejo.values(), key=lambda p: (p["fecha_subasta"] or "", p["score"] or 0), reverse=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps({
        "actualizado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "proxima_subasta": fecha.isoformat(),
        "avisos": avisos,
        "propiedades": todas,
        "ganadas": ganadas(ganadas_path),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
