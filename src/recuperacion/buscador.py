"""
Recuperación de fragmentos relevantes.

Ante una consulta en lenguaje natural, localiza los fragmentos del corpus
semánticamente más próximos. Constituye el componente central del sistema: si
la recuperación devuelve fragmentos inadecuados, ningún modelo de lenguaje
puede producir una respuesta correcta a partir de ellos.

La recuperación incorpora un criterio de relevancia mínima. Cuando ningún
fragmento alcanza el umbral establecido, el sistema no entrega resultados, lo
que permite comunicar al usuario la ausencia de información en lugar de
generar una respuesta carente de fundamento documental.
"""

import time

from src.config import TOP_K, UMBRAL_RELEVANCIA
from src.indexado.embeddings import generar_embedding_consulta
from src.indexado.indice import IndiceVectorial


class Buscador:
    """Interfaz de consulta sobre el índice vectorial del corpus."""

    def __init__(self, indice: IndiceVectorial | None = None):
        """
        Args:
            indice: índice ya construido. Si se omite, se carga desde disco.
        """
        if indice is not None:
            self.indice = indice
        else:
            self.indice = IndiceVectorial()
            if not self.indice.cargar():
                raise FileNotFoundError(
                    "No existe un índice guardado. "
                    "Ejecute primero: python construir_indice.py"
                )

    def buscar(
        self,
        consulta: str,
        k: int = TOP_K,
        umbral: float = UMBRAL_RELEVANCIA,
        aplicar_umbral: bool = True,
    ) -> dict:
        """
        Recupera los fragmentos más relevantes para una consulta.

        Args:
            consulta: pregunta formulada en lenguaje natural.
            k: número de fragmentos a recuperar.
            umbral: similitud mínima para considerar un fragmento relevante.
            aplicar_umbral: si es False, devuelve los k fragmentos sin filtrar.
                Resulta útil durante la experimentación, cuando interesa
                observar las similitudes obtenidas con independencia de que
                superen el umbral.

        Returns:
            Diccionario con los resultados y los datos de la búsqueda:
                {
                    "consulta": str,
                    "resultados": list[dict],
                    "total_recuperados": int,
                    "total_relevantes": int,
                    "similitud_maxima": float,
                    "hay_evidencia": bool,
                    "tiempo_embedding": float,
                    "tiempo_busqueda": float,
                }
        """
        inicio = time.perf_counter()
        vector = generar_embedding_consulta(consulta)
        tiempo_embedding = time.perf_counter() - inicio

        inicio = time.perf_counter()
        recuperados = self.indice.buscar(vector, k=k)
        tiempo_busqueda = time.perf_counter() - inicio

        similitud_maxima = recuperados[0]["similitud"] if recuperados else 0.0

        if aplicar_umbral:
            relevantes = [r for r in recuperados if r["similitud"] >= umbral]
        else:
            relevantes = recuperados

        return {
            "consulta": consulta,
            "resultados": relevantes,
            "total_recuperados": len(recuperados),
            "total_relevantes": len(relevantes),
            "similitud_maxima": similitud_maxima,
            "hay_evidencia": len(relevantes) > 0,
            "tiempo_embedding": tiempo_embedding,
            "tiempo_busqueda": tiempo_busqueda,
        }

    def buscar_sin_filtro(self, consulta: str, k: int = TOP_K) -> dict:
        """
        Recupera sin aplicar el criterio de relevancia.

        Empleado en la determinación experimental del umbral: permite observar
        la distribución de similitudes de las consultas con respuesta en el
        corpus frente a las que carecen de ella.
        """
        return self.buscar(consulta, k=k, aplicar_umbral=False)

    def resumen_corpus(self) -> dict:
        """Devuelve información sobre el corpus indexado."""
        return self.indice.resumen()


def formatear_resultado(resultado: dict, ancho_texto: int = 300) -> str:
    """
    Compone una representación legible de un fragmento recuperado.

    Args:
        resultado: fragmento con sus metadatos y su similitud.
        ancho_texto: número de caracteres del texto a mostrar.
    """
    cabecera = (
        f"[{resultado['similitud']:.4f}] "
        f"{resultado['documento']} — {resultado['referencia']}"
    )

    texto = resultado["texto"][:ancho_texto]
    if len(resultado["texto"]) > ancho_texto:
        texto += "..."

    return f"{cabecera}\n{texto}"
