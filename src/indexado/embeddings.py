"""
Generación de representaciones vectoriales (embeddings).

Convierte cada fragmento de texto en un vector numérico que representa su
significado. Dos textos con contenido semánticamente próximo producen vectores
próximos en el espacio vectorial, lo que permite la recuperación por
significado y no por coincidencia literal de términos.

El modelo se ejecuta localmente. Esta decisión evita el costo por consulta
asociado a los servicios externos —relevante dado que la experimentación con
distintas configuraciones de fragmentación exige reindexar el corpus
repetidamente— y garantiza que los documentos del usuario no abandonen su
equipo durante la indexación.
"""

import numpy as np
from sentence_transformers import SentenceTransformer

from src.config import MODELO_EMBEDDINGS, LOTE_EMBEDDINGS

# El modelo se carga una única vez y se reutiliza. La carga implica leer
# varios cientos de megabytes desde disco, por lo que repetirla en cada
# llamada penalizaría gravemente el rendimiento.
_modelo: SentenceTransformer | None = None


def obtener_modelo() -> SentenceTransformer:
    """
    Devuelve la instancia del modelo de embeddings.

    La primera invocación descarga el modelo si no se encuentra en la caché
    local del equipo, operación que puede tardar varios minutos.
    """
    global _modelo

    if _modelo is None:
        print(f"Cargando modelo de embeddings: {MODELO_EMBEDDINGS}")
        print("(la primera ejecución descarga el modelo; puede tardar)")
        _modelo = SentenceTransformer(MODELO_EMBEDDINGS)
        print(f"Modelo cargado. Dimensión: {_modelo.get_sentence_embedding_dimension()}")

    return _modelo


def dimension() -> int:
    """Devuelve la dimensionalidad de los vectores que produce el modelo."""
    return obtener_modelo().get_sentence_embedding_dimension()


def generar_embeddings(
    textos: list[str],
    mostrar_progreso: bool = True,
) -> np.ndarray:
    """
    Genera las representaciones vectoriales de una lista de textos.

    Los vectores se normalizan a longitud unitaria. Esta normalización permite
    calcular la similitud coseno mediante el producto escalar, operación
    considerablemente más eficiente, y es requisito para emplear el índice de
    producto interno de FAISS como medida de similitud coseno.

    Args:
        textos: lista de textos a vectorizar.
        mostrar_progreso: muestra una barra de progreso durante el proceso.

    Returns:
        Matriz de dimensiones (n_textos, dimensión), en formato float32 por
        requisito de FAISS.
    """
    if not textos:
        return np.empty((0, dimension()), dtype=np.float32)

    modelo = obtener_modelo()

    vectores = modelo.encode(
        textos,
        batch_size=LOTE_EMBEDDINGS,
        show_progress_bar=mostrar_progreso,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    return vectores.astype(np.float32)


def generar_embedding_consulta(texto: str) -> np.ndarray:
    """
    Genera la representación vectorial de una consulta.

    Se emplea el mismo modelo que para los fragmentos, condición
    indispensable: dos modelos distintos producen espacios vectoriales
    incompatibles, de modo que la comparación entre sus vectores carecería
    de significado.

    Returns:
        Matriz de dimensiones (1, dimensión), formato que espera FAISS para
        la búsqueda.
    """
    return generar_embeddings([texto], mostrar_progreso=False)
