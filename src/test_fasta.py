"""Pruebas rápidas de src/fasta.py. Ejecutar desde la raíz del repo:
    python -m src.test_fasta
"""
import os
import tempfile
from collections import Counter

from src.fasta import (calcular_atributos, leer_fasta, parsear_encabezado,
                       procesar_fasta, validar_secuencia)
from src.normalizacion import normalizar_especie

FASTA_PRUEBA = """>PDB00000001#CLASSII/HELITRON/HELITRON @Halicephalobus mephisto
acgtacgt
ggcc
>PumCon-1.11#CLASSI/SINE/tRNA @Puma concolor
ACGTNN
>X1#CLASSI/LTR/GYPSY @Beta vulgaris subsp. vulgaris
NNNN
>MAL#sin_clasificacion @Algo
ACGT
>BAD#CLASSI/LTR/COPIA @Algo raro
ACGTR
"""


def main():
    # normalización
    assert normalizar_especie("Beta vulgaris subsp. vulgaris") == "Beta vulgaris subsp vulgaris"
    assert normalizar_especie("  Coccomyxa  sp. obi ") == "Coccomyxa sp obi"

    # encabezado
    h = parsear_encabezado(">PumCon-1.11#CLASSI/SINE/tRNA @Puma concolor")
    assert h == {"pdb_id": "PumCon-1.11", "te_clase": "CLASSI", "te_orden": "SINE",
                 "te_superfamilia": "TRNA", "especie": "Puma concolor"}
    assert parsear_encabezado(">MAL#sin_clasificacion @Algo") is None

    # validación
    assert validar_secuencia("ACGTN") == (True, None)
    assert validar_secuencia("ACGTR") == (False, "caracteres_invalidos")
    assert validar_secuencia("") == (False, "secuencia_vacia")

    # atributos
    assert calcular_atributos("GGCC") == {"longitud": 4, "porcentaje_gc": 100.0, "porcentaje_n": 0.0}
    assert calcular_atributos("ACGTNN")["porcentaje_gc"] == 50.0
    assert calcular_atributos("NNNN")["porcentaje_gc"] is None

    # pipeline completo
    with tempfile.NamedTemporaryFile("w", suffix=".fasta", delete=False) as f:
        f.write(FASTA_PRUEBA)
        ruta = f.name
    try:
        assert len(list(leer_fasta(ruta))) == 5
        cont = Counter()
        dfs = list(procesar_fasta(ruta, tam_lote=2, contadores=cont))
        assert [len(d) for d in dfs] == [2, 1]
        assert cont == Counter(leidos=5, validos=3, encabezado_invalido=1, caracteres_invalidos=1)
        assert dfs[0].loc[0, "secuencia"] == "ACGTACGTGGCC"
    finally:
        os.remove(ruta)

    print("Todas las pruebas pasaron.")


if __name__ == "__main__":
    main()