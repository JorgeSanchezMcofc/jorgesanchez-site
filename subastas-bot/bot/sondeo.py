"""Temporal: ver qué trae la carpeta de Google Drive del CAD de Hidalgo (shapefiles)."""
import json
import pathlib
import zipfile

CARPETA = "https://drive.google.com/drive/folders/1cZc8Oqy6sghflXLbTUuaefoPLLy-FQm2"


def correr(debug_dir):
    import gdown
    out = {}
    d = pathlib.Path(debug_dir).parent / ".hidalgo_gis"
    try:
        files = gdown.download_folder(CARPETA, output=str(d), quiet=True, skip_download=True)
        out["archivos"] = [{"path": f.path, "id": f.id} for f in files]
        # bajar solo el más chico que sea .zip o .dbf para ver las columnas
        cand = [f for f in files if f.path.lower().endswith((".zip", ".dbf"))]
        if cand:
            f = cand[0]
            dest = d / pathlib.Path(f.path).name
            dest.parent.mkdir(parents=True, exist_ok=True)
            gdown.download(id=f.id, output=str(dest), quiet=True)
            out["bajado"] = {"nombre": dest.name, "bytes": dest.stat().st_size}
            if dest.suffix.lower() == ".zip":
                with zipfile.ZipFile(dest) as z:
                    out["contenido"] = [(i.filename, i.file_size) for i in z.infolist()]
                    dbf = next((n for n in z.namelist() if n.lower().endswith(".dbf")), None)
                    if dbf:
                        z.extract(dbf, d)
                        dest = d / dbf
            if dest.suffix.lower() == ".dbf":
                from dbfread import DBF
                t = DBF(str(dest), load=False, encoding="latin-1")
                out["columnas"] = t.field_names
                out["ejemplos"] = [dict(r) for _, r in zip(range(3), t)]
    except Exception as e:  # noqa: BLE001
        out["error"] = repr(e)
    p = pathlib.Path(debug_dir) / "sondeo_hidalgo_gis.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
