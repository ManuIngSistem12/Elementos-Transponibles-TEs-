from collections import Counter

#Caracteres válidos para k-mers
BASES = frozenset("ACGT")

#Rango de k a procesar
KS = range(1, 7)

#Define la función contar_kmers que cuenta los k-mers válidos en una secuencia dada.
def contar_kmers(seq, k):
    bruto = Counter([seq[i:i + k] for i in range(len(seq) - k + 1)])
    conteos = {km: c for km, c in bruto.items() if BASES.issuperset(km)}
    return conteos, sum(conteos.values())


#Define la función procesar_secuencia que genera documentos de k-mers para una secuencia dada(6 documentos en total).
def procesar_secuencia(item):
    sid, orden, seq = item
    seq = seq.upper()
    docs = []
    for k in KS:
        conteos, total = contar_kmers(seq, k)
        docs.append({"secuencia_id": sid, "te_orden": orden, "k": k,
                     "total_ventanas": total, "conteos": conteos})
    return docs


#Define la función procesar_lote que procesa un lote de secuencias y devuelve una lista de documentos de k-mers.
def procesar_lote(lote):
    return [d for item in lote for d in procesar_secuencia(item)]