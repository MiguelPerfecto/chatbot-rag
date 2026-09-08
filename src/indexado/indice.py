"""
Construcción y gestión del índice vectorial.

FAISS almacena y consulta las representaciones vectoriales de los fragmentos,
pero no conserva los textos ni sus metadatos: opera únicamente sobre vectores,
identificados por su posición en el índice. Por ello este módulo mantiene, en
paralelo al índice, una lista de fragmentos cuyo orden se corresponde
exactamente con el de los vectores.

Esta correspondencia es la que permite la trazabilidad del sistema: cuando la
búsqueda devuelve la posición 47, el fragmento con su documento y página de
origen se recupera de dicha lista. La pérdida de esta correspondencia
invalidaría por completo el mecanismo de citación de fuentes.
"""

import json
import pickle
from pathlib import Path

import faiss
import numpy as np

from src.config import INDICE_DIR
from src.indexado.embeddings import generar_embeddings, dimension

ARCHIVO_INDICE = INDICE_DIR / "faiss.index"
ARCHIVO_FRAGMENTOS = INDICE_DIR / "fragmentos.pkl"
ARCHIVO_METADATOS = INDICE_DIR / "metadatos.json"


class IndiceVectorial:
    """
    Índice de búsqueda semántica sobre un conjunto de fragmentos.

    Emplea IndexFlatIP, que realiza búsqueda exhaustiva mediante producto
    interno. Al estar los vectores normalizados, el producto interno equivale
    a la similitud coseno.

    La elección de un índice exhaustivo frente a las alternativas aproximadas
    responde al tamaño del corpus: con volúmenes del orden de los miles de
    fragmentos, la búsqueda exhaustiva resulta suficientemente rápida y
    garantiza resultados exactos, lo que elimina una fuente de variabilidad
    en la evaluación experimental del sistema.
    """

    def __init__(self):
        self.indice: faiss.Index | None = None
        self.fragmentos: list[dict] = []

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------

    def construir(self, fragmentos: list[dict]) -> None:
        """
        Construye el índice a partir de una lista de fragmentos.

        Args:
            fragmentos: fragmentos con su texto y metadatos de origen.
        """
        if not fragmentos:
            raise ValueError("No se recibieron fragmentos para indexar.")

        self.fragmentos = fragmentos

        textos = [f["texto"] for f in fragmentos]
        vectores = generar_embeddings(textos)

        self.indice = faiss.IndexFlatIP(vectores.shape[1])
        self.indice.add(vectores)

    def agregar(self, fragmentos: list[dict]) -> None:
        """
        Incorpora nuevos fragmentos a un índice existente.

        Permite añadir documentos sin reconstruir el índice completo.
        """
        if not fragmentos:
            return

        if self.indice is None:
            self.construir(fragmentos)
            return

        textos = [f["texto"] for f in fragmentos]
        vectores = generar_embeddings(textos)

        self.indice.add(vectores)
        self.fragmentos.extend(fragmentos)

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------

    def buscar(self, vector_consulta: np.ndarray, k: int = 5) -> list[dict]:
        """
        Recupera los k fragmentos más próximos a la consulta.

        Args:
            vector_consulta: vector de la consulta, de dimensiones (1, dim).
            k: número de fragmentos a recuperar.

        Returns:
            Lista de fragmentos ordenados por similitud descendente. Cada uno
            incorpora los campos 'similitud' y 'posicion'.
        """
        if self.indice is None or not self.fragmentos:
            return []

        k = min(k, len(self.fragmentos))

        similitudes, posiciones = self.indice.search(vector_consulta, k)

        resultados = []

        for similitud, posicion in zip(similitudes[0], posiciones[0]):
            # FAISS devuelve -1 cuando no hay suficientes resultados.
            if posicion < 0:
                continue

            resultado = dict(self.fragmentos[posicion])
            resultado["similitud"] = float(similitud)
            resultado["posicion"] = int(posicion)
            resultados.append(resultado)

        return resultados

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------

    def guardar(self, directorio: Path = INDICE_DIR) -> None:
        """
        Guarda el índice y los fragmentos en disco.

        Ambos elementos deben guardarse conjuntamente: un índice sin sus
        fragmentos asociados devuelve posiciones que no pueden resolverse,
        y unos fragmentos sin índice no son consultables.
        """
        if self.indice is None:
            raise ValueError("No hay índice construido que guardar.")

        directorio.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self.indice, str(directorio / "faiss.index"))

        with open(directorio / "fragmentos.pkl", "wb") as archivo:
            pickle.dump(self.fragmentos, archivo)

        documentos = sorted({f["documento"] for f in self.fragmentos})

        metadatos = {
            "total_fragmentos": len(self.fragmentos),
            "dimension": self.indice.d,
            "documentos": documentos,
            "total_documentos": len(documentos),
        }

        with open(directorio / "metadatos.json", "w", encoding="utf-8") as archivo:
            json.dump(metadatos, archivo, ensure_ascii=False, indent=2)

    def cargar(self, directorio: Path = INDICE_DIR) -> bool:
        """
        Carga un índice previamente guardado.

        Returns:
            True si la carga se completó, False si no existe índice guardado.
        """
        ruta_indice = directorio / "faiss.index"
        ruta_fragmentos = directorio / "fragmentos.pkl"

        if not ruta_indice.exists() or not ruta_fragmentos.exists():
            return False

        self.indice = faiss.read_index(str(ruta_indice))

        with open(ruta_fragmentos, "rb") as archivo:
            self.fragmentos = pickle.load(archivo)

        # Verificación de coherencia: si el número de vectores no coincide
        # con el de fragmentos, la correspondencia se ha perdido y el índice
        # no puede utilizarse de forma fiable.
        if self.indice.ntotal != len(self.fragmentos):
            raise ValueError(
                f"Índice inconsistente: {self.indice.ntotal} vectores frente a "
                f"{len(self.fragmentos)} fragmentos. Reconstruya el índice."
            )

        return True

    # ------------------------------------------------------------------
    # Información
    # ------------------------------------------------------------------

    def resumen(self) -> dict:
        """Devuelve información descriptiva del estado del índice."""
        if self.indice is None:
            return {"construido": False}

        documentos = sorted({f["documento"] for f in self.fragmentos})

        return {
            "construido": True,
            "total_fragmentos": len(self.fragmentos),
            "dimension": self.indice.d,
            "total_documentos": len(documentos),
            "documentos": documentos,
        }
