"""Convierte el texto de los PDFs de Perdue y Linebarger en una lista de propiedades.

Cada propiedad es un dict con: fuente, tipo, cause, cuenta(s), direccion, legal,
valor, minimo, estatus, notas, demandado.
"""
import re

MONEY = re.compile(r"\$\s?([\d,]+\.\d{2})")


def _money(s):
    return float(s.replace(",", ""))


# ---------------------------------------------------------------- Perdue
PERDUE_CAUSE = re.compile(r"^(\d{4}-[A-Z]{2,4}\d{4,6})\s*$", re.M)
PERDUE_ACCT = re.compile(r"\b(\d{16})\b")
LEGAL_START = re.compile(
    r"(\b\d+(\.\d+)?\s+acres?\b|\bLots?\s|\bLOTS?\s|\bALL OF\b|\bAll of\b|\bBEING\b|"
    r"\bA tract\b|\bA TRACT\b|\bThe (East|West|North|South)\b|\bTHE (EAST|WEST|NORTH|SOUTH)\b|\bTract\s+\d)"
)


def parse_perdue(text):
    """Lista de Perdue (ej. Cameron). Cada registro empieza con el Cause No."""
    header = re.search(r"SALES FOR ([A-Z]+ \d{1,2}, \d{4})", text)
    starts = list(PERDUE_CAUSE.finditer(text))
    out = []
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        block = text[m.end():end]
        block = block.split("Cause No:")[0]          # corta encabezados repetidos
        block = block.split("This notice and the materials")[0]
        flat = " ".join(block.split())
        amounts = [_money(a) for a in MONEY.findall(flat)]
        accts = PERDUE_ACCT.findall(flat)
        if not amounts:
            continue
        # Normal: [valor, minimo]. Varios tracts: [valor1, valor2, ..., minimo]
        if len(amounts) == len(accts) + 1 or len(amounts) == 2:
            valor, minimo = sum(amounts[:-1]), amounts[-1]
        else:
            half = len(amounts) // 2
            valor, minimo = sum(amounts[:half]), sum(amounts[half:])
        first_money = flat.find("$")
        before = flat[:first_money]
        vs = re.search(r"\b(VS\.?|vs\.?)\s", before)
        legal_zone = before[vs.end():] if vs else before
        ls = LEGAL_START.search(legal_zone)
        legal = legal_zone[ls.start():].strip() if ls else legal_zone.strip()
        demandado = legal_zone[: ls.start()].strip() if ls else ""
        legal = re.sub(r"\b(Tract \d+( & Tract \d+)?:\s*)+$", "", legal).strip()
        out.append({
            "fuente": "Perdue",
            "tipo": "Venta",
            "cause": m.group(1),
            "cuenta": " & ".join(accts),
            "direccion": "",
            "legal": legal,
            "valor": valor,
            "minimo": minimo,
            "estatus": "Programada",
            "notas": "",
            "demandado": demandado,
            "fecha_lista": header.group(1) if header else "",
        })
    return out


# ------------------------------------------------------------ Linebarger
LGB_ACCT = re.compile(r"^\s*([A-Z]\d{4}-\d{2}-[A-Z0-9]{3}-\d{4}-\d{2})\s*$", re.M)
LGB_CAUSE = re.compile(r"^\s*(T-\d{2,4}-\d{2}-[A-Z])/\d+\s*$", re.M)
LGB_TYPE = re.compile(r"^\s*((?:RE)?SALE|STRUCK[- ]?OFF)[A-Z ]*/\d+\s*$", re.M)
LGB_ADDR = re.compile(r"^\s*(.+?, TX(?:\s+\d{5}(?:-\d{4})?)?)\s*$", re.M)
LGB_DATE = re.compile(r"^\s*\d{2}-[A-Z]{3}-\d{2}\s*$", re.M)
LGB_STATUS = re.compile(r"^\s*(Cancelled|Scheduled[^\n]*|Active|Sold|Postponed[^\n]*|Pending[^\n]*)\s*$", re.M)
LGB_NOTE = re.compile(r"SALE IS SUBJECT TO ([\d,\sAND]+?)\s+AND\s+SUBSEQUENT", re.S)
PAGE_SPLIT = re.compile(r"Page \d+ of \d+")


def _split_legal(blob, n):
    lines = [l.strip() for l in blob.strip().splitlines() if l.strip()]
    descs, cur = [], []
    for ln in lines:
        cur.append(ln)
        if ln.endswith("."):
            descs.append(" ".join(cur))
            cur = []
    if cur:
        descs.append(" ".join(cur))
    if len(descs) == n:
        return descs
    return [" ".join(lines)] * n  # no se pudo separar: deja todo junto


def parse_linebarger(text):
    """Reporte 'County Property Sale List' de Linebarger (4 propiedades por página)."""
    out = []
    for page in PAGE_SPLIT.split(text)[1:]:
        accts = LGB_ACCT.findall(page)
        n = len(accts)
        if not n:
            continue
        types = [m.group(0).strip() for m in LGB_TYPE.finditer(page)][:n]
        addrs = [m.group(1) for m in LGB_ADDR.finditer(page)
                 if not m.group(1).upper().startswith(("HIDALGO COUNTY", "CAMERON COUNTY"))][:n]
        causes = LGB_CAUSE.findall(page)[:n]
        amounts = [_money(a) for a in MONEY.findall(page)]
        statuses = [s.strip() for s in LGB_STATUS.findall(page)][:n]

        # Descripción legal: entre la última dirección y el primer cause
        last_acct = list(LGB_ACCT.finditer(page))[-1]
        tail = page[last_acct.end():]
        first_cause = LGB_CAUSE.search(tail)
        addr_matches = list(LGB_ADDR.finditer(tail[: first_cause.start() if first_cause else None]))
        legal_blob = tail[addr_matches[n - 1].end() if len(addr_matches) >= n else 0:
                          first_cause.start() if first_cause else None]
        legals = _split_legal(legal_blob, n)

        # Demandados (para detectar herencias / fallecidos)
        dates = list(LGB_DATE.finditer(page))
        style_blob = page[dates[-1].end():page.find("$")] if dates else ""
        plaintiff = re.compile(r"^\s*((HIDALGO|CAMERON) COUNTY|CITY OF|.*INDEPENDENT SCHOOL)", re.M)
        defendants = []
        for part in re.split(r"\bVS\b", style_blob)[1:]:
            cut = plaintiff.search(part)
            defendants.append(part[: cut.start()] if cut else part)
        notes_blob = page[page.rfind("$"):]
        notes = [" ".join(m.group(1).split()) for m in LGB_NOTE.finditer(notes_blob)]

        for i in range(n):
            out.append({
                "fuente": "Linebarger",
                "tipo": "Reventa" if i < len(types) and types[i].startswith(("RESALE", "STRUCK")) else "Venta",
                "cause": causes[i] if i < len(causes) else "",
                "cuenta": accts[i],
                "direccion": addrs[i] if i < len(addrs) else "",
                "legal": legals[i],
                "valor": amounts[i] if len(amounts) >= 2 * n else None,
                "minimo": amounts[n + i] if len(amounts) >= 2 * n else None,
                "estatus": statuses[i] if i < len(statuses) else "",
                # Las notas no siempre vienen en todas; se asignan en orden si cuadran.
                "notas": ("Sujeto a impuestos " + notes[i]) if len(notes) == n else "",
                "demandado": " ".join(defendants[i].split()) if i < len(defendants) else "",
                "fecha_lista": "",
            })
    return out
