"""Experimento 4.4 rápido: estrategia 1 (colección aparte) vs. estrategia 2 (embebida).

Mide, sobre una MUESTRA de secuencias, con los mismos documentos de k-mers en
ambas estrategias:
  - tiempo de inserción (repetido N veces),
  - espacio en disco (collStats),
  - tiempo de 3 consultas con y sin índices (explain("executionStats")).

Uso, desde la raíz del repositorio (base con especies y secuencias cargadas):
    python -m src.experimento_muestra                # 5.000 secuencias, 3 repeticiones
    python -m src.experimento_muestra 5000 3 panteon  # muestra, repeticiones, base

Guarda las tablas en resultados/experimento_muestra_*.csv
"""
import os
import platform
import sys
import time

import pandas as pd
from pymongo import ASCENDING, MongoClient

from src.kmers import procesar_secuencia

BASE = "panteon"
COL_A = "exp_kmers_aparte"      # estrategia 1: un documento por (secuencia, k)
COL_B = "exp_kmers_embebidos"   # estrategia 2: un documento por secuencia con los 6 perfiles


# ---------------------------------------------------------------------------
# 1 y 2. Carga por lotes (memoria acotada): los k-mers se calculan fuera del
# cronómetro y solo se mide insert_many de cada estrategia.
# ---------------------------------------------------------------------------
def a_embebidos(docs_a):
    por_sec = {}
    for d in docs_a:
        sid = d["secuencia_id"]
        if sid not in por_sec:
            por_sec[sid] = {"secuencia_id": sid, "te_orden": d["te_orden"], "kmers": []}
        por_sec[sid]["kmers"].append({"k": d["k"], "total_ventanas": d["total_ventanas"],
                                      "conteos": d["conteos"]})
    return list(por_sec.values())


def cargar_ambas(db, n, lote_secuencias=25):
    """Devuelve (t_estrategia_1, t_estrategia_2, t_calculo, n_docs_1, n_docs_2)."""
    db[COL_A].drop()
    db[COL_B].drop()
    ta = tb = tc = 0.0
    na = nb = 0
    cursor = db.secuencias.find({}, {"te_orden": 1, "secuencia": 1}).sort("_id", 1).limit(n)
    lote = []

    def procesar(lote):
        nonlocal ta, tb, tc, na, nb
        t0 = time.perf_counter()
        docs_a = [d for s in lote for d in procesar_secuencia(s)]
        docs_b = a_embebidos(docs_a)
        tc += time.perf_counter() - t0
        t0 = time.perf_counter(); db[COL_A].insert_many(docs_a, ordered=False); ta += time.perf_counter() - t0
        t0 = time.perf_counter(); db[COL_B].insert_many(docs_b, ordered=False); tb += time.perf_counter() - t0
        na += len(docs_a); nb += len(docs_b)
        del docs_a, docs_b                     # libera memoria antes del siguiente lote

    for s in cursor:
        lote.append((s["_id"], s["te_orden"], s["secuencia"]))
        if len(lote) == lote_secuencias:
            procesar(lote); lote = []
    if lote:
        procesar(lote)
    return ta, tb, tc, na, nb


def espacio(db, nombre):
    s = db.command("collStats", nombre)
    return {"documentos": s["count"],
            "datos_MB": round(s["size"] / 1e6, 2),
            "disco_MB": round(s["storageSize"] / 1e6, 2),
            "indices_MB": round(s["totalIndexSize"] / 1e6, 2),
            "doc_promedio_KB": round(s["avgObjSize"] / 1e3, 2)}


# ---------------------------------------------------------------------------
# 3. Consultas con y sin índices
# ---------------------------------------------------------------------------
def consultas(db):
    muestra = db[COL_A].find_one()
    sid, orden = muestra["secuencia_id"], muestra["te_orden"]
    cond = {"k": 6, "total_ventanas": {"$gt": 1000}}
    return [
        ("C1: perfil k=6 de una secuencia",
         (COL_A, {"secuencia_id": sid, "k": 6}, None),
         (COL_B, {"secuencia_id": sid}, {"kmers": {"$elemMatch": {"k": 6}}})),
        ("C2: perfiles k=2 de un orden",
         (COL_A, {"te_orden": orden, "k": 2}, None),
         (COL_B, {"te_orden": orden}, {"kmers": {"$elemMatch": {"k": 2}}})),
        ("C3: k=6 con más de 1000 ventanas",
         (COL_A, cond, None),
         (COL_B, {"kmers": {"$elemMatch": cond}}, {"kmers": {"$elemMatch": cond}})),
    ]


def medir_consulta(db, nombre, filtro, proyeccion, con_indice, rep=3):
    tiempos = []
    for _ in range(rep):
        cur = db[nombre].find(filtro, proyeccion)
        if not con_indice:
            cur = cur.hint([("$natural", 1)])
        e = cur.explain()["executionStats"]
        tiempos.append(e["executionTimeMillis"])
    return min(tiempos), e["totalDocsExamined"], e["nReturned"]


def crear_indices(db):
    db[COL_A].create_index([("secuencia_id", ASCENDING), ("k", ASCENDING)], unique=True)
    db[COL_A].create_index([("te_orden", ASCENDING), ("k", ASCENDING)])
    db[COL_A].create_index([("k", ASCENDING), ("total_ventanas", ASCENDING)])
    db[COL_B].create_index([("secuencia_id", ASCENDING)], unique=True)
    db[COL_B].create_index([("te_orden", ASCENDING)])
    db[COL_B].create_index([("kmers.k", ASCENDING), ("kmers.total_ventanas", ASCENDING)])


# ---------------------------------------------------------------------------
def main(n=5000, repeticiones=3, base=BASE, lote=25):
    cliente = MongoClient("mongodb://localhost:27017")
    db = cliente[base]

    condiciones = {"sistema": f"{platform.system()} {platform.release()}",
                   "procesador": platform.processor(), "nucleos": os.cpu_count(),
                   "python": platform.python_version(),
                   "mongodb": cliente.server_info()["version"],
                   "secuencias_muestra": n, "repeticiones": repeticiones,
                   "secuencias_por_lote": lote}
    try:
        import psutil
        condiciones["ram_GB"] = round(psutil.virtual_memory().total / 1e9, 1)
    except ImportError:
        condiciones["ram_GB"] = "anotar a mano"

    filas = []
    for r in range(1, repeticiones + 1):
        ta, tb, tc, na, nb = cargar_ambas(db, n, lote)
        filas.append({"repeticion": r, "estrategia_1_s": round(ta, 3),
                      "estrategia_2_s": round(tb, 3), "calculo_kmers_s": round(tc, 1)})
        print(f"repetición {r}: estrategia 1 = {ta:.2f} s ({na} docs) | "
              f"estrategia 2 = {tb:.2f} s ({nb} docs) | cálculo k-mers = {tc:.1f} s")
    carga = pd.DataFrame(filas).set_index("repeticion")

    filas_q = []
    for con_indice in (False, True):
        if con_indice:
            crear_indices(db)
        for nombre_q, (ca, fa, pa), (cb, fb, pb) in consultas(db):
            for estrategia, (col, f, p) in (("1 aparte", (ca, fa, pa)), ("2 embebida", (cb, fb, pb))):
                ms, examinados, devueltos = medir_consulta(db, col, f, p, con_indice)
                filas_q.append({"consulta": nombre_q, "estrategia": estrategia,
                                "indice": "con" if con_indice else "sin", "ms": ms,
                                "docs_examinados": examinados, "devueltos": devueltos})
    tiempos_q = pd.DataFrame(filas_q)

    esp = pd.DataFrame({"estrategia 1 (aparte)": espacio(db, COL_A),
                        "estrategia 2 (embebida)": espacio(db, COL_B)}).T

    os.makedirs("resultados", exist_ok=True)
    pd.Series(condiciones).to_csv("resultados/experimento_muestra_condiciones.csv")
    carga.to_csv("resultados/experimento_muestra_carga.csv")
    esp.to_csv("resultados/experimento_muestra_espacio.csv")
    tiempos_q.to_csv("resultados/experimento_muestra_consultas.csv", index=False)

    pd.set_option("display.width", 160)
    print("\n=== CONDICIONES ===\n", pd.Series(condiciones).to_string())
    print("\n=== CARGA (s) ===\n", carga.to_string())
    print("\n", carga.agg(["mean", "std"]).round(3).to_string())
    print("\n=== ESPACIO (con índices creados) ===\n", esp.to_string())
    print("\n=== CONSULTAS ===\n", tiempos_q.to_string(index=False))
    return condiciones, carga, esp, tiempos_q


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    rep = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    base = sys.argv[3] if len(sys.argv) > 3 else BASE
    lote = int(sys.argv[4]) if len(sys.argv) > 4 else 25
    main(n, rep, base, lote)