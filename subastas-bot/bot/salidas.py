"""Google Sheets, correo, y archivos locales (CSV + reporte HTML)."""
import csv
import datetime as dt
import html
import json
import os
import smtplib
from email.mime.text import MIMEText

# Columnas que llena el bot. Las demás (Luz, Agua, Ganador, Notas...) son tuyas y no se tocan.
COLS = {
    "Condado": "condado",
    "Fecha subasta": "fecha_subasta",
    "Tipo (venta/reventa)": "tipo",
    "Cause No.": "cause",
    "Cuenta CAD / Property ID": "cuenta",
    "Dirección / Ubicación": "direccion",
    "Ciudad": "ciudad",
    "Descripción legal": "legal",
    "Acres": "acres",
    "Oferta mínima": "minimo",
    "Valor tasación CAD": "valor",
    "Liens / notas de título": "riesgos",
    "Score (0-100)": "score",
    "Puja máxima sugerida": "puja_max",
    "Estatus": "estatus",
    "Link mapa / satélite": "mapa",
    # Columnas nuevas que el bot agrega al final si no existen:
    "Baldío (estimado)": "baldio_txt",
    "Impuestos atrasados est.": "impuestos_est",
    "¿Conviene?": "conviene_txt",
    "Link CAD": "cad",
    "Fuente / PDF": "pdf",
    "Visto primera vez": "visto",
}


def _fmt(p):
    p["baldio_txt"] = {True: "Sí", False: "No", None: "¿?"}[p["baldio"]]
    p["conviene_txt"] = "Sí" if p["conviene"] else "No"
    return p


def guardar_csv(props, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLS.keys())
        for p in props:
            w.writerow([_fmt(p).get(k, "") for k in COLS.values()])


def actualizar_sheet(props, sheet_id, creds_json):
    import gspread
    gc = gspread.service_account_from_dict(json.loads(creds_json))
    ws = gc.open_by_key(sheet_id).sheet1
    data = ws.get_all_values()
    header = data[0] if data else []
    for col in COLS:
        if col not in header:
            header.append(col)
    idx = {h: i for i, h in enumerate(header)}
    rows = [r + [""] * (len(header) - len(r)) for r in data[1:]]
    key = lambda r: (r[idx["Condado"]], r[idx["Cuenta CAD / Property ID"]], r[idx["Cause No."]])
    by_key = {key(r): r for r in rows}
    hoy = dt.date.today().isoformat()
    nuevos = 0
    for p in props:
        _fmt(p)
        k = (p["condado"], p["cuenta"], p["cause"])
        row = by_key.get(k)
        if row is None:
            row = [""] * len(header)
            rows.append(row)
            by_key[k] = row
            p["visto"] = hoy
            nuevos += 1
        else:
            p["visto"] = row[idx["Visto primera vez"]] or hoy
        for col, attr in COLS.items():
            v = p.get(attr, "")
            row[idx[col]] = "" if v is None else str(v)
    ws.update([header] + rows, "A1", value_input_option="USER_ENTERED")
    return nuevos


def reporte_html(props, fecha, top, avisos):
    mejores = [p for p in props if p["score"] > 0][:top]
    filas = "".join(
        f"<tr><td><b>{p['score']}</b></td><td>{html.escape(p['condado'])}</td>"
        f"<td><a href='{p['mapa']}'>{html.escape(p['direccion'] or p['legal'][:70])}</a></td>"
        f"<td>{p['acres'] or '¿?'}</td><td>{p['baldio_txt']}</td>"
        f"<td>${(p['minimo'] or 0):,.0f}</td><td>${(p['valor'] or 0):,.0f}</td>"
        f"<td><b>${p['puja_max']:,.0f}</b>{'' if p['conviene'] else ' ⚠️'}</td>"
        f"<td style='font-size:12px'>{html.escape(p['riesgos'])}</td></tr>"
        for p in mejores)
    avisos_html = "".join(f"<li>{html.escape(a)}</li>" for a in avisos)
    return f"""<div style="font-family:Arial,sans-serif;max-width:900px">
<h2>Subastas del {fecha:%d/%m/%Y}: Hidalgo y Cameron</h2>
<p>{len(props)} propiedades en lista. Estas son las {len(mejores)} con mejor score.
⚠️ = el mínimo ya es más alto que tu puja máxima.</p>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-size:14px">
<tr style="background:#eee"><th>Score</th><th>Condado</th><th>Ubicación</th><th>Acres</th>
<th>Baldío</th><th>Mínimo</th><th>Valor</th><th>Puja máx.</th><th>Riesgos</th></tr>{filas}</table>
<ul>{avisos_html}</ul>
<p style="font-size:12px;color:#666">Homestead, ag exemption y título se revisan en el CAD y con title company
antes de pujar. Las ventas son "as is".</p></div>"""


def enviar_correo(asunto, cuerpo_html, para, usuario, password, host="smtp.gmail.com", port=587):
    msg = MIMEText(cuerpo_html, "html", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = asunto, usuario, para
    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(usuario, password)
        s.send_message(msg)
