# Elementos transponibles en MongoDB

Proyecto del segundo corte de **Bases de Datos II** (Universidad Autónoma de Manizales).

Diseño, implementación y evaluación de una base de datos documental en **MongoDB** que integra las secuencias de elementos transponibles (TEs) de *PanTEon Database v1.6.1*, la taxonomía de las especies de las que provienen y sus perfiles de *k*-mers (*k* = 1 a 6). Todo el procesamiento se hace en **Python**.

---

## Contenido del repositorio

```
├── notebooks/
│   ├── TEs_pipeline.ipynb       ← NOTEBOOK ÚNICO DEL PROYECTO (todo, de principio a fin)
│   └── library/                 Bibliotecas .fasta generadas (Q10 y Q11)
├── src/                         Funciones que usa el notebook
│   ├── fasta.py                 Lectura por streaming, validación y atributos del FASTA
│   ├── normalizacion.py         Normalización de nombres de especie (cruce FASTA–CSV)
│   ├── test_fasta.py            Pruebas del pipeline del FASTA
│   ├── kmers.py                 Conteo de k-mers (k = 1 a 6)
│   ├── esquema_indices.py       Índices y validación $jsonSchema de las 3 colecciones
│   ├── consultas_a.py           Consultas Q1–Q4 y pregunta propia 1
│   ├── consultas_c.py           Exportación de bibliotecas .fasta (Q10, Q11)
│   ├── figuras_a.py             Figuras 1 y 2
│   ├── figuras_c.py             Datos de la figura 4 (heatmap de 2-mers)
│   └── experimento_muestra.py   Experimento 4.4 (estrategias de almacenamiento de k-mers)
├── figuras/                     Figuras del artículo (PNG y PDF)
├── resultados/                  Tablas del experimento (CSV)
├── articulo/
|   ├──articulo
|   ├──secciones/          Fuentes LaTeX del artículo
├── requirements.txt
└── README.md
```

Los datos **no** se suben al repositorio (carpeta `data/`, ignorada en `.gitignore`).

---

## 1. Requisitos

| Herramienta | Versión probada | Para qué |
|---|---|---|
| Python | 3.10 o superior | Pipeline, consultas y figuras |
| MongoDB Community Server | 7.x u 8.x | Base de datos local |
| Git | cualquiera reciente | Clonar el repositorio |
| VS Code o JupyterLab | — | Ejecutar los notebooks |

Opcional: **MongoDB Compass**, para ver las colecciones de forma gráfica.

---

## 2. Instalación

```bash
git clone https://github.com/ManuIngSistem12/Elementos-Transponibles-TEs-.git
cd Elementos-Transponibles-TEs-

python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Al abrir los notebooks, selecciona el kernel del entorno `.venv`.

---

## 3. Descarga de los datos

Los datos son públicos (licencia CC BY 4.0): **https://zenodo.org/records/19372616**

Descarga solo estos dos archivos y guárdalos en una carpeta `data/` en la raíz del repositorio:

```
data/
├── PanTEon_Database_v1.6.1.fasta            (~947 MB)
└── PanTEon_Database_metadata_v1.6.1.csv     (~363 KB)
```

Los archivos `.zip` de modelos entrenados del mismo repositorio no se necesitan.

---

## 4. MongoDB local

Instala MongoDB Community Server desde https://www.mongodb.com/try/download/community con la opción **"Install MongoD as a Service"**. Comprueba que esté encendido:

```powershell
# Windows (PowerShell)
Get-Service MongoDB          # debe decir Running
# si está detenido, en PowerShell como administrador:
Start-Service MongoDB
```

Todo el proyecto se conecta a `mongodb://localhost:27017` y usa la base **`panteon_prueba`**.

---

## 5. Ejecución desde cero

Todo el proyecto está en **un solo notebook**: `notebooks/TEs_pipeline.ipynb`.

1. Opcional: comprueba el pipeline del FASTA desde la raíz del repositorio con `python -m src.test_fasta` (debe decir `Todas las pruebas pasaron.`).
2. Abre `notebooks/TEs_pipeline.ipynb`, selecciona el kernel de `.venv` y ejecuta **Run All**.

La primera celda de código define la configuración común. Si cambias la base o la carpeta de datos, solo se cambia ahí:

```python
BASE = "panteon"
DATOS = "../data"
```

El notebook ejecuta, en este orden:

| Sección | Qué hace | Comprobación esperada |
|---|---|---|
| Pipeline del FASTA | Lee, valida y calcula longitud, %GC y %N | 239.946 leídos, 0 descartados |
| CSV y cruce | Limpia el CSV, cruza por especie y carga `especies` | 2.790 especies cruzadas |
| Carga de las secuencias | Carga `secuencias` enlazadas con `especie_id` | 239.946 secuencias, 0 sin especie |
| Índices y validación | Crea los 6 índices y aplica `$jsonSchema` | 0 documentos fuera del esquema |
| *k*-mers | Calcula y carga los perfiles *k* = 1 a 6 (en paralelo) | 1.439.676 documentos (6 × 239.946) |
| Consultas Q1–Q15 y preguntas propias | Pregunta, código, resultado e interpretación | — |
| Figuras 1 a 4 | Se generan con datos leídos desde MongoDB | Archivos en `figuras/` |
| Experimento 4.4 | Compara colección aparte y *k*-mers embebidos | Tablas en `resultados/` |

**Tiempos:** el cálculo de los *k*-mers de toda la base es la parte lenta (del orden de una hora; depende de la máquina). Si el notebook se interrumpe, al volver a ejecutarlo continúa con las secuencias que faltan. El experimento necesita unos 3 GB libres en disco.

**Volver a ejecutar sobre una base existente:** la sección del CSV vacía y recarga `especies`, lo que cambia sus `_id`. La celda de carga de secuencias lo detecta y recarga `secuencias` y `kmers` para que las referencias sigan siendo válidas.

---

## 6. Modelo de datos

Tres colecciones relacionadas por referencias (`_id`):

| Colección | Documentos | Contenido |
|---|---|---|
| `especies` | 2.790 | `especie`, `reino`, `filo`, `tax_clase`, `tax_orden`, `familia`, `fuente`, `fuente_2`, `notas` |
| `secuencias` | 239.946 | `pdb_id`, `te_clase`, `te_orden`, `te_superfamilia`, `secuencia`, `especie_id` → `especies._id`, `longitud`, `porcentaje_gc`, `porcentaje_n` |
| `kmers` | 1.439.676 (6 por secuencia) | `secuencia_id` → `secuencias._id`, `te_orden`, `k`, `total_ventanas`, `conteos` |

**Índices:** `especies.especie` (único), `especies.fuente`, `secuencias.pdb_id` (único), `secuencias.especie_id`, `kmers.(secuencia_id, k)` (único) y `kmers.(te_orden, k)`. La justificación de cada uno está en el artículo (Métodos).

---

## 7. Reglas de procesamiento

| Regla | Decisión |
|---|---|
| Secuencia | Se guarda en **mayúsculas**; alfabeto válido **ACGTN** |
| Clasificación del TE | En mayúsculas (unifica `SINE/TRNA` y `SINE/tRNA`) |
| `porcentaje_gc` | (G + C) / (A + C + G + T) × 100 — **sin contar las N** |
| `porcentaje_n` | N / longitud total × 100 |
| *k*-mers con N | La ventana que contiene una N no se cuenta; `total_ventanas` cuenta solo ventanas válidas |
| Nombres de especie | Se normalizan para el cruce (espacios y punto de `sp.`/`subsp.`); se guarda el nombre del FASTA |
| Registros descartados | Ninguno: los 239.946 registros del FASTA son válidos |

---

## 8. Artículo

El artículo sigue la guía de autores de **BMC Bioinformatics** y está escrito en LaTeX. Las fuentes de las secciones están en `articulo/secciones/`. La revista elegida y las normas aplicadas están en `JOURNAL.md`.

---

## 9. Datos y citación

Si usas este trabajo, cita las fuentes de los datos:

1. Orozco-Arias S, Ferrer-Pomer I, Rodrigues de Goes F, Gaviria-Orrego S, Gómiz-Fernández J, Llatser-Torres J, Paschoal AR, Guyot R, Gabaldón T. (2026). *PanTEon: a cross-kingdom framework to guide the design of transposable element classifiers*. bioRxiv. https://doi.org/10.64898/2026.04.01.715927
2. PanTEon Database v1.6.1. Zenodo. https://zenodo.org/records/19372616

---

## Equipo

Proyecto de Bases de Datos II – Universidad Autónoma de Manizales. Docente: Simón Gaviria Orrego.