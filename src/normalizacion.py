"""Normalización de nombres de especie, compartida por el FASTA y el CSV.

Ambos lados DEBEN usar esta misma función; si no, el cruce por especie falla.
"""
import re

# Abreviaturas taxonómicas que aparecen con punto en el FASTA ("subsp.", "sp.")
# y sin punto en el CSV ("subsp", "sp"). Se les quita el punto en ambos lados.
_ABREVIATURAS = re.compile(r"\b(subsp|sp|var|f)\.(?=\s|$)")
_ESPACIOS = re.compile(r"\s+")


def normalizar_especie(nombre):
    """Devuelve el nombre de especie normalizado para cruzar FASTA y CSV.

    Reglas, en orden:
      1. strip(): quita espacios al inicio y al final.
      2. Colapsa espacios múltiples en uno solo.
      3. Quita el punto de las abreviaturas sp., subsp., var. y f.

    No cambia mayúsculas/minúsculas: en la exploración no hubo nombres que
    difirieran solo en mayúsculas, y así el nombre guardado sigue siendo legible.

    >>> normalizar_especie("  Beta vulgaris subsp. vulgaris ")
    'Beta vulgaris subsp vulgaris'
    """
    if nombre is None:
        return None
    nombre = str(nombre).strip()
    nombre = _ESPACIOS.sub(" ", nombre)
    nombre = _ABREVIATURAS.sub(r"\1", nombre)
    return nombre