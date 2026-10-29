"""Consultas Q1 a Q4 y pregunta propia 1 (persona A).

Modelo acordado por el equipo:

    secuencias: _id, pdb_id, te_clase, te_orden, te_superfamilia, secuencia,
                especie_id (-> especies._id), longitud, porcentaje_gc, porcentaje_n
    especies:   _id, especie, reino, filo, tax_clase, tax_orden, familia,
                fuente, fuente_2, notas
    kmers:      _id, secuencia_id, te_orden, k, total_ventanas, conteos

Cada consulta tiene dos funciones:
    pipeline_qX(...)  -> la lista de etapas de agregación (es lo que va en el artículo)
    qX(db, ...)       -> ejecuta el pipeline y devuelve un DataFrame de pandas

Idea general de rendimiento: en Q2, Q3, Q4 y la propia se agrupa PRIMERO en
`secuencias` (240 mil documentos -> unos miles de grupos) y DESPUÉS se hace el
$lookup a `especies`. Así el $lookup se ejecuta miles de veces y no 240 mil.
"""
import pandas as pd


def _df(cursor):
    return pd.DataFrame(list(cursor))


# ---------------------------------------------------------------------------
# Q1. ¿Cuántos TEs hay por clase, por orden y por superfamilia en toda la base?
# ---------------------------------------------------------------------------
def pipeline_q1():
    """Un solo recorrido de la colección con $facet: tres conteos a la vez."""
    def conteo(*campos):
        id_ = {c: f"${c}" for c in campos}
        return [
            {"$group": {"_id": id_, "n_te": {"$sum": 1}}},
            {"$sort": {"n_te": -1}},
        ]

    return [
        {"$facet": {
            "por_clase": conteo("te_clase"),
            "por_orden": conteo("te_clase", "te_orden"),
            "por_superfamilia": conteo("te_clase", "te_orden", "te_superfamilia"),
        }}
    ]


def q1(db):
    """Devuelve un dict con tres DataFrames: por_clase, por_orden, por_superfamilia."""
    res = next(db.secuencias.aggregate(pipeline_q1()))
    salida = {}
    for nivel, filas in res.items():
        df = pd.json_normalize(filas)
        df.columns = [c.replace("_id.", "") for c in df.columns]
        df["porcentaje"] = (df["n_te"] / df["n_te"].sum() * 100).round(2)
        salida[nivel] = df
    return salida


# ---------------------------------------------------------------------------
# Q2. ¿Cuántos TEs tiene cada especie, desglosados por clase, orden y superfamilia?
# ---------------------------------------------------------------------------
def pipeline_q2(especie=None):
    """Si se pasa `especie`, filtra el resultado a esa especie."""
    pipeline = [
        {"$group": {
            "_id": {
                "especie_id": "$especie_id",
                "te_clase": "$te_clase",
                "te_orden": "$te_orden",
                "te_superfamilia": "$te_superfamilia",
            },
            "n_te": {"$sum": 1},
        }},
        {"$lookup": {
            "from": "especies",
            "localField": "_id.especie_id",
            "foreignField": "_id",
            "as": "esp",
        }},
        {"$unwind": "$esp"},
    ]
    if especie:
        pipeline.append({"$match": {"esp.especie": especie}})
    pipeline += [
        {"$project": {
            "_id": 0,
            "especie": "$esp.especie",
            "te_clase": "$_id.te_clase",
            "te_orden": "$_id.te_orden",
            "te_superfamilia": "$_id.te_superfamilia",
            "n_te": 1,
        }},
        {"$sort": {"especie": 1, "n_te": -1}},
    ]
    return pipeline


def q2(db, especie=None):
    return _df(db.secuencias.aggregate(pipeline_q2(especie), allowDiskUse=True))


# ---------------------------------------------------------------------------
# Q3. ¿Cómo cambia la cantidad de TEs por clase y orden entre reinos? ¿Y entre phyla?
# ---------------------------------------------------------------------------
def pipeline_q3(nivel="reino"):
    """`nivel` es "reino" o "filo" (campo de la colección especies)."""
    if nivel not in ("reino", "filo"):
        raise ValueError("nivel debe ser 'reino' o 'filo'")
    agrupacion = {"te_clase": "$_id.te_clase", "te_orden": "$_id.te_orden",
                  nivel: f"$esp.{nivel}"}
    if nivel == "filo":                      # el filo se muestra junto a su reino
        agrupacion["reino"] = "$esp.reino"
    return [
        # 1) contar por especie y orden (reduce 240 mil documentos a unos miles)
        {"$group": {
            "_id": {"especie_id": "$especie_id",
                    "te_clase": "$te_clase", "te_orden": "$te_orden"},
            "n": {"$sum": 1},
        }},
        # 2) traer la taxonomía de la especie
        {"$lookup": {"from": "especies", "localField": "_id.especie_id",
                     "foreignField": "_id", "as": "esp"}},
        {"$unwind": "$esp"},
        # 3) volver a agrupar por reino (o filo) + clase + orden
        {"$group": {"_id": agrupacion, "n_te": {"$sum": "$n"}}},
        {"$project": {"_id": 0, **{c: f"$_id.{c}" for c in agrupacion}, "n_te": 1}},
        {"$sort": {nivel: 1, "n_te": -1}},
    ]


def q3(db, nivel="reino", tabla=True):
    """Con tabla=True devuelve una tabla cruzada (filas: orden, columnas: reino/filo)."""
    df = _df(db.secuencias.aggregate(pipeline_q3(nivel), allowDiskUse=True))
    if not tabla or df.empty:
        return df
    return (df.pivot_table(index=["te_clase", "te_orden"], columns=nivel,
                           values="n_te", aggfunc="sum", fill_value=0)
              .astype(int))


# ---------------------------------------------------------------------------
# Q4. ¿Cuáles son las 10 especies con más TEs y las 10 con menos?
# ---------------------------------------------------------------------------
def pipeline_q4(n=10):
    """Los empates se rompen por nombre de especie (orden alfabético)."""
    nombre = [
        {"$lookup": {"from": "especies", "localField": "_id",
                     "foreignField": "_id", "as": "esp"}},
        {"$unwind": "$esp"},
        {"$project": {"_id": 0, "especie": "$esp.especie",
                      "reino": "$esp.reino", "n_te": 1}},
    ]
    return [
        {"$group": {"_id": "$especie_id", "n_te": {"$sum": 1}}},
        {"$facet": {
            "top": [{"$sort": {"n_te": -1, "_id": 1}}, {"$limit": n}] + nombre
                   + [{"$sort": {"n_te": -1, "especie": 1}}],
            "bottom": [{"$sort": {"n_te": 1, "_id": 1}}, {"$limit": n}] + nombre
                      + [{"$sort": {"n_te": 1, "especie": 1}}],
            "empatados_en_minimo": [
                {"$group": {"_id": None, "minimo": {"$min": "$n_te"},
                            "valores": {"$push": "$n_te"}}},
                {"$project": {"_id": 0, "minimo": 1,
                              "n_especies": {"$size": {"$filter": {
                                  "input": "$valores", "as": "v",
                                  "cond": {"$eq": ["$$v", "$minimo"]}}}}}},
            ],
        }},
    ]


def q4(db, n=10):
    """Devuelve (top, bottom, info_empates)."""
    res = next(db.secuencias.aggregate(pipeline_q4(n), allowDiskUse=True))
    empates = res["empatados_en_minimo"][0] if res["empatados_en_minimo"] else {}
    return pd.DataFrame(res["top"]), pd.DataFrame(res["bottom"]), empates


# ---------------------------------------------------------------------------
# Pregunta propia 1.
# ¿Cuántas "especies" son en realidad taxones superiores (nombre de una sola
# palabra, p. ej. Mammalia, Homininae), cuántos TEs aportan y de qué órdenes?
# Nace de la exploración: 45 de las 2.790 entradas no son especies.
# ---------------------------------------------------------------------------
def pipeline_propia1():
    return [
        {"$group": {"_id": {"especie_id": "$especie_id", "te_orden": "$te_orden"},
                    "n": {"$sum": 1}}},
        {"$lookup": {"from": "especies", "localField": "_id.especie_id",
                     "foreignField": "_id", "as": "esp"}},
        {"$unwind": "$esp"},
        # nombre sin espacios = una sola palabra = taxón superior
        {"$addFields": {"es_taxon_superior": {
            "$regexMatch": {"input": "$esp.especie", "regex": r"^\S+$"}}}},
        {"$facet": {
            "resumen": [
                {"$group": {"_id": "$es_taxon_superior",
                            "n_te": {"$sum": "$n"},
                            "especies": {"$addToSet": "$_id.especie_id"}}},
                {"$project": {"_id": 0, "es_taxon_superior": "$_id", "n_te": 1,
                              "n_entradas": {"$size": "$especies"}}},
                {"$sort": {"es_taxon_superior": -1}},
            ],
            "por_orden": [
                {"$match": {"es_taxon_superior": True}},
                {"$group": {"_id": "$_id.te_orden", "n_te": {"$sum": "$n"}}},
                {"$project": {"_id": 0, "te_orden": "$_id", "n_te": 1}},
                {"$sort": {"n_te": -1}},
            ],
            "taxones": [
                {"$match": {"es_taxon_superior": True}},
                {"$group": {"_id": "$esp.especie", "reino": {"$first": "$esp.reino"},
                            "n_te": {"$sum": "$n"}}},
                {"$project": {"_id": 0, "taxon": "$_id", "reino": 1, "n_te": 1}},
                {"$sort": {"n_te": -1}},
            ],
        }},
    ]


def propia1(db):
    """Devuelve (resumen, por_orden, taxones)."""
    res = next(db.secuencias.aggregate(pipeline_propia1(), allowDiskUse=True))
    resumen = pd.DataFrame(res["resumen"])
    if not resumen.empty:
        resumen["porcentaje_te"] = (resumen["n_te"] / resumen["n_te"].sum() * 100).round(2)
    return resumen, pd.DataFrame(res["por_orden"]), pd.DataFrame(res["taxones"])