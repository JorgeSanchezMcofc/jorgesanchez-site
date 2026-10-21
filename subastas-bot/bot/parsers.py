"""Convierte las tablas de los PDFs (pdfplumber) en una lista de propiedades.

Entrada: pages = [{"text": str, "tables": [[[celda, ...], ...], ...]}, ...]
Cada propiedad es un dict con: fuente, tipo, cause, cuenta, direccion, legal,
valor, minimo, estatus, notas, demandado, fecha_lista.
"""
import datetime as dt
import re

MONEY = re.compile(r"\$\s?([\d,]+(?:\.\d{2})?)")
MESES = {m: i for i, m in enumerate(["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST",
                                      "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"], 1)}


def _money_sum(s):
    return sum(float(a.replace(",", "")) for a in MONEY.findall(s or "")) or None


def _flat(s):
    return " ".join((s or "").split())


def _rows(pages):
    for pg in pages:
        for tb in pg.get("tables") or []:
            for row in tb:
                yield [c or "" for c in row]


def _defendant(style):
    parts = re.split(r"\b(?:VS|vs)\.?\s", style, maxsplit=1)
    return _flat(parts[1]) if len(parts) > 1 else ""


# ---------------------------------------------------------------- Perdue
def fecha_perdue(pages):
    m = re.search(r"SALES FOR ([A-Z]+) (\d{1,2}), (\d{4})", pages[0]["text"] if pages else "")
    if not m or m.group(1) not in MESES:
        return None
    return dt.date(int(m.group(3)), MESES[m.group(1)], int(m.group(2)))


def parse_perdue(pages):
    """Ventas (6 columnas: cause/corte/fecha, caso, legal, valor, mínimo, cuenta)
    y reventas (6 columnas: item, cause+caso, legal, valor, mínimo, cuenta)."""
    fecha = fecha_perdue(pages)
    reventa = "RESALES FOR" in (pages[0]["text"] if pages else "")
    out = []
    for row in _rows(pages):
        if len(row) < 6 or re.match(r"\s*(Cause No|Item No)", row[0]):
            continue
        if reventa:
            item, causa_caso, legal, valor, minimo, cuenta = row[:6]
            m = re.match(r"\s*((?:[\dA-Z]+-[\dA-Z-]+\s*&?\s*)+)(.*)", _flat(causa_caso))
            cause, style = (m.group(1).strip(" &"), m.group(2)) if m else ("", _flat(causa_caso))
        else:
            causa, style, legal, valor, minimo, cuenta = row[:6]
            m = re.match(r"\s*([\d]{4}-[A-Z]{2,4}-\s*\d+)", causa)
            cause = re.sub(r"\s+", "", m.group(1)) if m else _flat(causa)[:20]
        accts = re.findall(r"\b[A-Z]?\d{8,}\b", cuenta)
        nota = re.search(r"NOTE:(.*)", _flat(cuenta))
        v, mn = _money_sum(valor), _money_sum(minimo)
        if not accts or v is None:
            continue
        out.append({
            "fuente": "Perdue",
            "tipo": "Reventa" if reventa else "Venta",
            "cause": cause,
            "cuenta": " & ".join(accts),
            "direccion": "",
            "legal": re.sub(r"^Tract \d+:\s*", "", _flat(legal)),
            "valor": v,
            "minimo": mn,
            "estatus": "Programada",
            "notas": _flat(nota.group(1)) if nota else "",
            "demandado": _defendant(_flat(style)),
            "fecha_lista": fecha.isoformat() if fecha else "",
        })
    return out


# ------------------------------------------------------------ Linebarger
HEAD = re.compile(r"^(\d+)\s+((?:RE)?SALE|STRUCK\S*)\S*\s+(\S+?)/\S+\s+\d{2}-[A-Z]{3}-\d{2}\s+(.*)$")
STATUS = re.compile(r"\s+(Scheduled.*|Cancel\w*|Postponed.*|Active|Sold|Withdrawn.*|Pulled.*|Struck.*|Removed.*)$")
ACCT = re.compile(r"^(\S+)\s+(.*?)\s*(\d{2}-[A-Z]{3}-\d{2})\s+\$([\d,.]+)\s+\$([\d,.]+)\s*(.*)$")


def fecha_linebarger(pages):
    m = re.search(r"Sale Date (\d{2})/(\d{2})/(\d{4})", pages[0]["text"] if pages else "")
    return dt.date(int(m.group(3)), int(m.group(1)), int(m.group(2))) if m else None


def parse_linebarger(pages):
    """Reporte 'County Property Sale List': una celda por propiedad con varias líneas."""
    fecha = fecha_linebarger(pages)
    out = []
    for row in _rows(pages):
        lines = [l.strip() for l in row[0].split("\n") if l.strip()]
        if not lines:
            continue
        h = HEAD.match(lines[0])
        if not h:
            continue
        rest = h.group(4)
        st = STATUS.search(rest)
        status = st.group(1) if st else ""
        style = [rest[: st.start()] if st else rest]
        i = 1
        while i < len(lines) and not ACCT.match(lines[i]):
            style.append(lines[i])
            i += 1
        if i == len(lines):
            continue
        a = ACCT.match(lines[i])
        address = a.group(2)
        notes = [a.group(6)] if a.group(6) else []
        i += 1
        end = re.compile(r"(YEARS\.?|APPRAISED VALUE SALE\.?|tax sale\.?)\s*$", re.I)
        if notes:
            while i < len(lines) and not end.search(" ".join(notes)) and len(notes) < 6:
                ln = lines[i]
                z = re.match(r"^(TX \d{5}(?:-\d{4})?)\s*(.*)$", ln)  # el código postal se cuela en las notas
                if z:
                    address, ln = f"{address} {z.group(1)}", z.group(2)
                notes.append(ln)
                i += 1
        nota = _flat(" ".join(notes))
        for z in re.findall(r"\bTX \d{5}(?:-\d{4})?\b", nota):
            address, nota = f"{address} {z}", _flat(nota.replace(z, ""))
        yrs = sorted(set(re.findall(r"\b20\d{2}\b", nota)))
        if re.search(r"subject to", nota, re.I) and yrs:
            nota = "Sujeto a impuestos " + ", ".join(yrs) + ("; liens de ciudad aparte" if "City Liens" in nota else "")
        years = None
        out.append({
            "fuente": "Linebarger",
            "tipo": "Reventa" if h.group(2).upper().startswith(("RESALE", "STRUCK")) else "Venta",
            "cause": h.group(3),
            "cuenta": a.group(1),
            "direccion": _flat(address),
            "legal": _flat(" ".join(lines[i:])),
            "valor": float(a.group(4).replace(",", "")),
            "minimo": float(a.group(5).replace(",", "")),
            "estatus": status.replace("Aucti", "Auction") if status.endswith("Aucti") else status,
            "notas": nota,
            "demandado": _defendant(_flat(" ".join(style))),
            "fecha_lista": fecha.isoformat() if fecha else "",
        })
    return out
