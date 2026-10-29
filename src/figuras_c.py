import pandas as pd

DINUC = [a + b for a in "ACGT" for b in "ACGT"]


def frecuencias_2mers_por_orden(db):
    pipeline = [
        {"$match": {"k": 2, "total_ventanas": {"$gt": 0}}},
        {"$group": {
            "_id": "$te_orden",
            "n": {"$sum": 1},
            **{d: {"$avg": {"$divide": [{"$ifNull": [f"$conteos.{d}", 0]},
                                        "$total_ventanas"]}} for d in DINUC},
        }},
    ]
    df = pd.DataFrame(db.kmers.aggregate(pipeline, allowDiskUse=True))
    df = df.rename(columns={"_id": "te_orden"}).set_index("te_orden")
    return df[["n"] + DINUC].sort_index()