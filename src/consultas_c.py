import re
from pathlib import Path

CARPETA = Path("library")          


def _encabezado(s, especie):
    # Formato original: >ID#CLASE/ORDEN/SUPERFAMILIA @Especie
    return f">{s['pdb_id']}#{s['te_clase']}/{s['te_orden']}/{s['te_superfamilia']} @{especie}"


def exportar_biblioteca(db, campo, valor, ruta=None, ancho=None, carpeta=CARPETA):
    if campo not in ("especie", "reino"):
        raise ValueError("campo debe ser 'especie' o 'reino'")

    esp = {e["_id"]: e["especie"] for e in db.especies.find({campo: valor}, {"especie": 1})}
    if not esp:
        raise ValueError(f"No hay especies con {campo} = {valor!r}")

    cursor = db.secuencias.find({"especie_id": {"$in": list(esp)}}).sort("pdb_id", 1)

    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)     
    nombre = f"biblioteca_{campo}_{re.sub(r'[^A-Za-z0-9]+', '_', valor)}.fasta"
    ruta = Path(ruta) if ruta else carpeta / nombre

    n = 0
    with open(ruta, "w", encoding="utf-8") as f:
        for s in cursor:
            f.write(_encabezado(s, esp[s["especie_id"]]) + "\n")
            seq = s["secuencia"]
            if ancho:
                seq = "\n".join(seq[i:i + ancho] for i in range(0, len(seq), ancho))
            f.write(seq + "\n")
            n += 1
    return str(ruta), len(esp), n

