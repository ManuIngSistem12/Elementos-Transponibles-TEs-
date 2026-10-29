"""Índices y validación $jsonSchema de las tres colecciones (persona A).

Uso (desde un notebook o con `python -m src.esquema_indices panteon_prueba`):
    from src.esquema_indices import aplicar_todo, verificar
    aplicar_todo(db)          # crea índices y aplica las validaciones
    verificar(db)             # cuenta documentos que NO cumplen el esquema

Decisión del equipo: validar TODAS las colecciones para fijar los tipos de
los campos. Se usa validationAction="error": un insert que no cumple el
esquema se rechaza. Los documentos que ya existían no se tocan
(validationLevel="moderate"), por eso `verificar` los revisa aparte.
"""
import sys

from pymongo import ASCENDING, MongoClient

ENTERO = ["int", "long"]
TEXTO_O_NULO = ["string", "null"]

# ---------------------------------------------------------------------------
# Esquemas
# ---------------------------------------------------------------------------
ESQUEMA_ESPECIES = {
    "bsonType": "object",
    "required": ["especie", "reino", "fuente"],
    "properties": {
        "especie": {"bsonType": "string", "minLength": 1,
                    "description": "nombre normalizado; llave del cruce con el FASTA"},
        "reino": {"enum": ["Animalia", "Plantae", "Fungi"]},
        "filo": {"bsonType": TEXTO_O_NULO},
        "tax_clase": {"bsonType": TEXTO_O_NULO},
        "tax_orden": {"bsonType": TEXTO_O_NULO},
        "familia": {"bsonType": TEXTO_O_NULO},
        "fuente": {"bsonType": "string"},
        "fuente_2": {"bsonType": TEXTO_O_NULO},
        "notas": {"bsonType": TEXTO_O_NULO},
    },
}

ESQUEMA_SECUENCIAS = {
    "bsonType": "object",
    "required": ["pdb_id", "te_clase", "te_orden", "te_superfamilia",
                 "secuencia", "especie_id", "longitud", "porcentaje_gc",
                 "porcentaje_n"],
    "properties": {
        "pdb_id": {"bsonType": "string", "minLength": 1},
        "te_clase": {"enum": ["CLASSI", "CLASSII"]},
        "te_orden": {"bsonType": "string", "minLength": 1},
        "te_superfamilia": {"bsonType": "string", "minLength": 1},
        "secuencia": {"bsonType": "string", "pattern": "^[ACGTN]+$",
                      "description": "mayúsculas, alfabeto ACGTN"},
        "especie_id": {"bsonType": "objectId"},
        "longitud": {"bsonType": ENTERO, "minimum": 1},
        "porcentaje_gc": {"bsonType": ["double", "int", "null"],
                          "minimum": 0, "maximum": 100},
        "porcentaje_n": {"bsonType": ["double", "int"],
                         "minimum": 0, "maximum": 100},
    },
}

ESQUEMA_KMERS = {
    "bsonType": "object",
    "required": ["secuencia_id", "te_orden", "k", "total_ventanas", "conteos"],
    "properties": {
        "secuencia_id": {"bsonType": "objectId"},
        "te_orden": {"bsonType": "string"},
        "k": {"bsonType": ENTERO, "minimum": 1, "maximum": 6},
        "total_ventanas": {"bsonType": ENTERO, "minimum": 0},
        "conteos": {"bsonType": "object",
                    "description": "clave = k-mer, valor = conteo (solo presentes)"},
    },
}

ESQUEMAS = {"especies": ESQUEMA_ESPECIES,
            "secuencias": ESQUEMA_SECUENCIAS,
            "kmers": ESQUEMA_KMERS}

# ---------------------------------------------------------------------------
# Índices: (colección, campos, opciones, consulta que lo justifica)
# ---------------------------------------------------------------------------
INDICES = [
    ("especies", [("especie", ASCENDING)], {"unique": True},
     "Cruce FASTA-CSV, Q9 y Q10 (buscar por nombre de especie); impide duplicados"),
    ("especies", [("reino", ASCENDING)], {},
     "Q11 (biblioteca de un reino): filtrar las especies del reino"),
    ("secuencias", [("pdb_id", ASCENDING)], {"unique": True},
     "Q8 (buscar una secuencia por su nombre); el identificador no se repite"),
    ("secuencias", [("especie_id", ASCENDING)], {},
     "$lookup secuencias-especies y bibliotecas Q10/Q11 (secuencias de una especie)"),
    ("kmers", [("secuencia_id", ASCENDING), ("k", ASCENDING)], {"unique": True},
     "Q15 (perfil de una secuencia para un k); evita duplicados si la carga se repite"),
    ("kmers", [("te_orden", ASCENDING), ("k", ASCENDING)], {},
     "Figura 4 (heatmap de k=2 por orden)"),
]


def crear_indices(db):
    for coleccion, campos, opciones, _ in INDICES:
        db[coleccion].create_index(campos, **opciones)


def aplicar_validaciones(db):
    existentes = set(db.list_collection_names())
    for nombre, esquema in ESQUEMAS.items():
        opciones = {"validator": {"$jsonSchema": esquema},
                    "validationLevel": "moderate", "validationAction": "error"}
        if nombre in existentes:
            db.command("collMod", nombre, **opciones)
        else:
            db.create_collection(nombre, **opciones)


def aplicar_todo(db):
    aplicar_validaciones(db)
    crear_indices(db)
    return listar_indices(db)


def verificar(db):
    """Documentos que NO cumplen su esquema (debería ser 0 en las tres)."""
    return {nombre: db[nombre].count_documents({"$nor": [{"$jsonSchema": esq}]})
            for nombre, esq in ESQUEMAS.items()}


def listar_indices(db):
    filas = []
    for coleccion in ESQUEMAS:
        for nombre, info in db[coleccion].index_information().items():
            filas.append({"coleccion": coleccion, "indice": nombre,
                          "campos": info["key"], "unico": info.get("unique", False)})
    return filas


if __name__ == "__main__":
    base = sys.argv[1] if len(sys.argv) > 1 else "panteon_prueba"
    db = MongoClient("mongodb://localhost:27017")[base]
    for fila in aplicar_todo(db):
        print(fila)
    print("Documentos que no cumplen el esquema:", verificar(db))