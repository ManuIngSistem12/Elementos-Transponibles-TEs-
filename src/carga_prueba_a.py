"""Carga de PRUEBA para correr Q1-Q4 y las figuras sin esperar el cargador de C.

Crea la base `panteon_prueba` (no toca la base oficial `panteon`) con las
colecciones `especies` y `secuencias` usando los nombres de campo acordados.
No calcula k-mers: eso es trabajo del cargador de C.

Uso, desde la raíz del repositorio:
    python -m src.carga_prueba_a                 # base completa (~2-4 min)
    python -m src.carga_prueba_a --max 20000     # solo las primeras 20 mil secuencias
"""
import argparse
import time
from collections import Counter

import pandas as pd
from pymongo import MongoClient

from src.fasta import procesar_fasta
from src.normalizacion import normalizar_especie

RUTA_FASTA = "data/PanTEon_Database_v1.6.1.fasta"
RUTA_CSV = "data/PanTEon_Database_metadata_v1.6.1.csv"


def _texto(v):
    return None if pd.isna(v) or str(v).strip() == "" else str(v).strip()


def cargar_especies(db):
    csv = pd.read_csv(RUTA_CSV, encoding="utf-8-sig")
    docs = [{
        "especie": normalizar_especie(r["Species"]),
        "reino": _texto(r["Kingdom"]), "filo": _texto(r["Phylum"]),
        "tax_clase": _texto(r["Class"]), "tax_orden": _texto(r["Order"]),
        "familia": _texto(r["Family"]), "fuente": _texto(r["Source"]),
        "fuente_2": _texto(r["Source 2"]), "notas": _texto(r["Notes"]),
    } for _, r in csv.iterrows()]
    db.especies.insert_many(docs)
    db.especies.create_index("especie", unique=True)
    return {d["especie"]: d["_id"] for d in docs}


def main(maximo=None, tam_lote=5000):
    db = MongoClient("mongodb://localhost:27017")["panteon_prueba"]
    db.especies.drop()
    db.secuencias.drop()

    t0 = time.perf_counter()
    ids = cargar_especies(db)
    cont, sin_especie, cargadas = Counter(), 0, 0

    for df in procesar_fasta(RUTA_FASTA, tam_lote, cont):
        if maximo:
            df = df.head(maximo - cargadas)
        df["especie_id"] = df["especie"].map(ids)
        sin_especie += int(df["especie_id"].isna().sum())
        df = df.dropna(subset=["especie_id"]).drop(columns="especie")
        if len(df):
            db.secuencias.insert_many(df.to_dict("records"), ordered=False)
        cargadas += len(df)
        if maximo and cargadas >= maximo:
            break

    db.secuencias.create_index("pdb_id", unique=True)
    db.secuencias.create_index("especie_id")
    print(f"especies: {db.especies.count_documents({})}")
    print(f"secuencias: {db.secuencias.count_documents({})}  (sin especie: {sin_especie})")
    print(f"tiempo: {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--max", type=int, default=None, help="máximo de secuencias a cargar")
    main(p.parse_args().max)