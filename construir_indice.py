"""
Construcción del índice vectorial del corpus.

Ejecutar desde la raíz del proyecto:
    python construir_indice.py

Procesa todos los documentos del corpus aplicando extracción, limpieza,
fragmentación y vectorización, y guarda el índice resultante en disco para su
reutilización en las sesiones posteriores.
"""

import sys
import time

from src.config import DOCUMENTOS_DIR, INDICE_DIR, TAMANO_FRAGMENTO, SOLAPAMIENTO
from src.ingesta.extractor_pdf import extraer_pdf
from src.ingesta.extractor_docx import extraer_docx
from src.procesamiento.limpieza import limpiar_documento
from src.procesamiento.fragmentacion import fragmentar_documento
from src.indexado.indice import IndiceVectorial

SEP = "=" * 78


def procesar_documento(ruta) -> list[dict]:
    """Ejecuta extracción, limpieza y fragmentación sobre un documento."""
    if ruta.suffix.lower() == ".pdf":
        bloques = extraer_pdf(ruta)
    else:
        bloques = extraer_docx(ruta)

    if not bloques:
        return []

    limpios = limpiar_documento(bloques)
    return fragmentar_documento(limpios)


def main() -> None:
    rutas = sorted(
        list(DOCUMENTOS_DIR.glob("*.pdf")) + list(DOCUMENTOS_DIR.glob("*.docx"))
    )

    if not rutas:
        print(f"No se encontraron documentos en: {DOCUMENTOS_DIR}")
        sys.exit(1)

    print(f"\nCONSTRUCCIÓN DEL ÍNDICE VECTORIAL")
    print(SEP)
    print(f"Documentos       : {len(rutas)}")
    print(f"Fragmentación    : {TAMANO_FRAGMENTO} caracteres, "
          f"solapamiento {SOLAPAMIENTO}")
    print(SEP)

    # --- Fase 1: procesamiento documental ---
    print("\nProcesando documentos...")
    inicio_procesamiento = time.perf_counter()

    todos = []
    omitidos = []

    for ruta in rutas:
        fragmentos = procesar_documento(ruta)

        if not fragmentos:
            omitidos.append(ruta.name)
            print(f"  {ruta.name}: omitido (sin contenido extraíble)")
            continue

        todos.extend(fragmentos)
        print(f"  {ruta.name}: {len(fragmentos)} fragmentos")

    tiempo_procesamiento = time.perf_counter() - inicio_procesamiento

    if not todos:
        print("\nNingún documento produjo fragmentos. No se construyó el índice.")
        sys.exit(1)

    print(f"\nTotal de fragmentos: {len(todos)}")
    print(f"Tiempo de procesamiento documental: {tiempo_procesamiento:.2f} s")

    # --- Fase 2: vectorización e indexación ---
    print(f"\nGenerando embeddings e indexando...")
    inicio_indexacion = time.perf_counter()

    indice = IndiceVectorial()
    indice.construir(todos)

    tiempo_indexacion = time.perf_counter() - inicio_indexacion

    # --- Fase 3: persistencia ---
    indice.guardar()

    resumen = indice.resumen()

    print("\n" + SEP)
    print("ÍNDICE CONSTRUIDO")
    print(SEP)
    print(f"Fragmentos indexados : {resumen['total_fragmentos']}")
    print(f"Dimensión vectorial  : {resumen['dimension']}")
    print(f"Documentos incluidos : {resumen['total_documentos']}")

    if omitidos:
        print(f"Documentos omitidos  : {len(omitidos)}")
        for nombre in omitidos:
            print(f"    - {nombre}")

    print(f"\nTiempo de indexación : {tiempo_indexacion:.2f} s")
    print(f"Tiempo total         : "
          f"{tiempo_procesamiento + tiempo_indexacion:.2f} s")
    print(f"Media por fragmento  : "
          f"{1000 * tiempo_indexacion / len(todos):.1f} ms")
    print(f"\nÍndice guardado en: {INDICE_DIR}")


if __name__ == "__main__":
    main()
