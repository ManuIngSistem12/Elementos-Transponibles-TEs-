"""Figuras 1 y 2 del artículo. Los datos se leen SIEMPRE desde MongoDB.

Figura 1. Composición de TEs por reino: % de cada orden de TE en Animalia,
          Plantae y Fungi (tres paneles con el mismo eje, uno por reino).
Figura 2. Longitud de los TEs: boxplot de la longitud por orden de TE.

Uso:
    from src.figuras_a import figura1, figura2
    figura1(db, "figuras/fig1_composicion_reino")
    figura2(db, "figuras/fig2_longitud_orden")
Cada figura se guarda en PNG (300 dpi) y PDF (vectorial, para LaTeX).
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.consultas_a import pipeline_q3

# Estilo sobrio para artículo: un solo color de datos, tinta gris para el texto.
COLOR_DATOS = "#2a78d6"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
GRILLA = "#e6e5e1"
REINOS = ["Animalia", "Plantae", "Fungi"]

plt.rcParams.update({
    "font.size": 9, "axes.edgecolor": TINTA_2, "axes.labelcolor": TINTA,
    "xtick.color": TINTA_2, "ytick.color": TINTA_2, "text.color": TINTA,
    "axes.spines.top": False, "axes.spines.right": False,
})


def _guardar(fig, ruta):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(ruta.with_suffix(".pdf"), bbox_inches="tight")


# ---------------------------------------------------------------------------
# Figura 1
# ---------------------------------------------------------------------------
def datos_figura1(db):
    """Tabla orden × reino con conteos (usa el mismo pipeline de Q3)."""
    df = pd.DataFrame(list(db.secuencias.aggregate(pipeline_q3("reino"),
                                                   allowDiskUse=True)))
    tabla = df.pivot_table(index="te_orden", columns="reino", values="n_te",
                           aggfunc="sum", fill_value=0)
    return tabla[[r for r in REINOS if r in tabla.columns]]


def figura1(db=None, ruta="figuras/fig1_composicion_reino", tabla=None):
    """Porcentaje de TEs de cada orden dentro de cada reino.

    Se usa porcentaje (no conteo) porque los reinos tienen tamaños muy distintos
    (Plantae ~118 mil TEs, Fungi ~20 mil): con conteos Fungi no se vería.
    """
    if tabla is None:
        tabla = datos_figura1(db)
    pct = tabla / tabla.sum() * 100
    orden = pct.mean(axis=1).sort_values().index        # mismo orden en los 3 paneles
    pct = pct.loc[orden]

    fig, ejes = plt.subplots(1, len(pct.columns), figsize=(7.2, 3.6), sharey=True)
    for ax, reino in zip(ejes, pct.columns):
        valores = pct[reino]
        ax.barh(valores.index, valores.values, color=COLOR_DATOS, height=0.7)
        ax.set_title(f"{reino}\n(n = {int(tabla[reino].sum()):,})".replace(",", "."),
                     fontsize=9, color=TINTA)
        ax.set_xlim(0, 100)
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.xaxis.grid(True, color=GRILLA, linewidth=0.6)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0)
        for y, v in enumerate(valores.values):              # etiqueta solo si > 5 %
            if v >= 5:
                ax.text(v + 1.5, y, f"{v:.0f} %", va="center", fontsize=7.5,
                        color=TINTA_2)
    ejes[len(ejes) // 2].set_xlabel("Porcentaje de TEs del reino (%)")
    ejes[0].set_ylabel("Orden de TE")
    fig.tight_layout()
    _guardar(fig, ruta)
    return fig, tabla


# ---------------------------------------------------------------------------
# Figura 2
# ---------------------------------------------------------------------------
def datos_figura2(db):
    """Longitud y orden de cada secuencia (solo esos dos campos, sin la secuencia)."""
    cursor = db.secuencias.find({}, {"_id": 0, "te_orden": 1, "longitud": 1})
    return pd.DataFrame(list(cursor))


def figura2(db=None, ruta="figuras/fig2_longitud_orden", datos=None):
    """Boxplot de longitud (pb) por orden de TE, ordenado por mediana.

    Los valores atípicos se dibujan pequeños y semitransparentes porque con
    240 mil puntos taparían las cajas.
    """
    if datos is None:
        datos = datos_figura2(db)
    medianas = datos.groupby("te_orden")["longitud"].median().sort_values()
    ordenes = list(medianas.index)
    grupos = [datos.loc[datos.te_orden == o, "longitud"].values for o in ordenes]
    conteos = [len(g) for g in grupos]

    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.boxplot(
        grupos, vert=False, widths=0.6, patch_artist=True,
        boxprops=dict(facecolor=COLOR_DATOS, edgecolor=COLOR_DATOS, alpha=0.35),
        medianprops=dict(color=COLOR_DATOS, linewidth=2),
        whiskerprops=dict(color=TINTA_2, linewidth=0.8),
        capprops=dict(color=TINTA_2, linewidth=0.8),
        flierprops=dict(marker="o", markersize=1.5, markerfacecolor=TINTA_2,
                        markeredgecolor="none", alpha=0.25),
    )
    ax.set_yticks(range(1, len(ordenes) + 1))
    ax.set_yticklabels([f"{o}  (n = {n:,})".replace(",", ".")
                        for o, n in zip(ordenes, conteos)])
    ax.set_xlabel("Longitud (pb)")
    ax.set_ylabel("Orden de TE")
    ax.xaxis.grid(True, color=GRILLA, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    fig.tight_layout()
    _guardar(fig, ruta)

    resumen = (datos.groupby("te_orden")["longitud"]
               .describe()[["count", "min", "25%", "50%", "75%", "max", "mean"]]
               .loc[ordenes].round(0).astype(int))
    return fig, resumen