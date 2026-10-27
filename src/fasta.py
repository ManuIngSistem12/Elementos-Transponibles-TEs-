"""Pipeline de lectura, validación y atributos del FASTA de PanTEon (persona A).

Uso típico:
    from src.fasta import procesar_fasta
    for df in procesar_fasta("data/PanTEon_Database_v1.6.1.fasta", tam_lote=5000):
        ...                       # cada df es un lote listo para B (cruce) y C (k-mers)

Contrato de salida (columnas de cada DataFrame):
    id_original, te_class, te_order, te_superfamily, especie,
    secuencia, longitud, porcentaje_gc, porcentaje_n

Reglas de limpieza (documentadas en exploracion/hallazgos_fasta.md):
    - Secuencia en MAYÚSCULAS (86,8 % venía en minúsculas).
    - Clasificación en MAYÚSCULAS (unifica SINE/TRNA y SINE/tRNA).
    - Especie normalizada con src.normalizacion.normalizar_especie.
    - Alfabeto válido: A, C, G, T, N. Otro carácter => registro descartado.
    - porcentaje_n  = N / longitud total * 100
    - porcentaje_gc = (G + C) / (A + C + G + T) * 100   (bases válidas, sin N)
      Si la secuencia es solo N, porcentaje_gc = None.
"""
from collections import Counter

import pandas as pd

from src.normalizacion import normalizar_especie

ALFABETO_VALIDO = set("ACGTN")

COLUMNAS = [
    "id_original", "te_class", "te_order", "te_superfamily", "especie",
    "secuencia", "longitud", "porcentaje_gc", "porcentaje_n",
]


# ---------------------------------------------------------------------------
# 1. Lectura por streaming
# ---------------------------------------------------------------------------
def leer_fasta(ruta):
    """Recorre el FASTA y entrega (encabezado, secuencia) de a un registro.

    Es un generador: solo guarda en memoria la secuencia que está armando,
    así que sirve para el archivo de ~1 GB.
    """
    encabezado = None
    partes = []                       # líneas de la secuencia actual

    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.rstrip("\r\n")
            if not linea:             # ignora líneas en blanco
                continue
            if linea.startswith(">"):
                if encabezado is not None:          # cierra el registro anterior
                    yield encabezado, "".join(partes)
                encabezado = linea
                partes = []
            else:
                partes.append(linea)

    if encabezado is not None:        # el último registro no tiene ">" detrás
        yield encabezado, "".join(partes)


# ---------------------------------------------------------------------------
# 2. Encabezado
# ---------------------------------------------------------------------------
def parsear_encabezado(encabezado):
    """Separa '>ID#CLASE/ORDEN/SUPERFAMILIA @Especie' en un diccionario.

    Devuelve None si el encabezado no cumple el patrón (el llamador lo
    cuenta como descarte).
    """
    texto = encabezado.lstrip(">").strip()

    if "#" not in texto or "@" not in texto:
        return None

    id_original, resto = texto.split("#", 1)
    clasificacion, especie = resto.split("@", 1)

    niveles = [n.strip().upper() for n in clasificacion.strip().split("/")]
    if len(niveles) != 3 or not all(niveles):
        return None

    id_original = id_original.strip()
    especie = normalizar_especie(especie)
    if not id_original or not especie:
        return None

    return {
        "id_original": id_original,
        "te_class": niveles[0],
        "te_order": niveles[1],
        "te_superfamily": niveles[2],
        "especie": especie,
    }


# ---------------------------------------------------------------------------
# 3. Validación
# ---------------------------------------------------------------------------
def validar_secuencia(seq):
    """Valida una secuencia YA en mayúsculas.

    Devuelve (True, None) si es válida o (False, motivo) si no.
    """
    if not seq:
        return False, "secuencia_vacia"
    invalidos = set(seq) - ALFABETO_VALIDO
    if invalidos:
        return False, "caracteres_invalidos"
    return True, None


# ---------------------------------------------------------------------------
# 4. Atributos
# ---------------------------------------------------------------------------
def calcular_atributos(seq):
    """Calcula longitud, porcentaje_gc y porcentaje_n de una secuencia válida.

    porcentaje_gc usa como denominador las bases A, C, G, T (sin N);
    porcentaje_n usa la longitud total.
    """
    longitud = len(seq)
    g, c, a, t, n = (seq.count(b) for b in "GCATN")
    bases_validas = a + c + g + t

    porcentaje_gc = round((g + c) / bases_validas * 100, 4) if bases_validas else None
    porcentaje_n = round(n / longitud * 100, 4)

    return {
        "longitud": longitud,
        "porcentaje_gc": porcentaje_gc,
        "porcentaje_n": porcentaje_n,
    }


# ---------------------------------------------------------------------------
# 5. Pipeline por lotes
# ---------------------------------------------------------------------------
def procesar_fasta(ruta, tam_lote=5000, contadores=None):
    """Lee, valida y calcula atributos; entrega DataFrames de `tam_lote` filas.

    `contadores` (un Counter) se va llenando con:
        leidos, validos, encabezado_invalido, secuencia_vacia,
        caracteres_invalidos
    Pasalo desde afuera para consultarlo al terminar:
        cont = Counter()
        for df in procesar_fasta(ruta, contadores=cont): ...
        print(cont)
    """
    if contadores is None:
        contadores = Counter()

    lote = []
    for encabezado, seq in leer_fasta(ruta):
        contadores["leidos"] += 1

        campos = parsear_encabezado(encabezado)
        if campos is None:
            contadores["encabezado_invalido"] += 1
            continue

        seq = seq.upper()
        valida, motivo = validar_secuencia(seq)
        if not valida:
            contadores[motivo] += 1
            continue

        fila = {**campos, "secuencia": seq, **calcular_atributos(seq)}
        lote.append(fila)
        contadores["validos"] += 1

        if len(lote) >= tam_lote:
            yield pd.DataFrame(lote, columns=COLUMNAS)
            lote = []

    if lote:                          # último lote incompleto
        yield pd.DataFrame(lote, columns=COLUMNAS)