"""
Diagnóstico del corpus documental.

Ejecutar desde la raíz del proyecto:
    python probar_extraccion.py

Recorre los documentos de data/documentos y reporta qué se puede extraer de
cada uno. Los resultados cumplen dos funciones: detectar documentos
problemáticos antes de indexarlos, y describir el corpus en la sección 3.3.1
del documento escrito.
"""

import sys

from src.config import DOCUMENTOS_DIR
from src.ingesta.extractor_pdf import diagnosticar_pdf, extraer_pdf
from src.ingesta.extractor_docx import diagnosticar_docx, extraer_docx

SEPARADOR = "=" * 78


def revisar_pdfs(rutas: list) -> None:
    print(f"\nARCHIVOS PDF ({len(rutas)})")
    print(SEPARADOR)

    for ruta in rutas:
        info = diagnosticar_pdf(ruta)

        print(f"\n{info['documento']}")
        print(f"  Páginas totales      : {info['total_paginas']}")
        print(f"  Páginas con texto    : {info['paginas_con_texto']}")
        print(f"  Páginas sin texto    : {info['paginas_sin_texto']}")
        print(f"  Caracteres totales   : {info['caracteres_totales']:,}")
        print(f"  Promedio por página  : {info['promedio_caracteres_por_pagina']:,}")

        if info["paginas_sin_texto"] > 0:
            print("  AVISO: hay páginas sin texto extraíble (posible escaneo).")


def revisar_docx(rutas: list) -> None:
    print(f"\n\nARCHIVOS WORD ({len(rutas)})")
    print(SEPARADOR)

    for ruta in rutas:
        try:
            info = diagnosticar_docx(ruta)
        except Exception as error:
            print(f"\n{ruta.name}")
            print(f"  ERROR: {error}")
            continue

        print(f"\n{info['documento']}")
        print(f"  Secciones detectadas : {info['secciones']}")
        print(f"  Caracteres totales   : {info['caracteres_totales']:,}")
        print(f"  Promedio por sección : {info['promedio_caracteres_por_seccion']:,}")

        if info["secciones"] <= 1:
            print("  AVISO: no se detectaron títulos con estilo de Word.")
            print("         Todo el documento quedó como una sola sección.")
        else:
            print("  Títulos encontrados:")
            for titulo in info["titulos"][:8]:
                print(f"    - {titulo[:60]}")
            if len(info["titulos"]) > 8:
                print(f"    ... y {len(info['titulos']) - 8} más")


def mostrar_muestra(ruta, tipo: str) -> None:
    """Imprime un fragmento del texto extraído para inspección visual."""
    print("\n" + SEPARADOR)
    print(f"MUESTRA DE TEXTO EXTRAÍDO — {ruta.name}")
    print(SEPARADOR)

    bloques = extraer_pdf(ruta) if tipo == "pdf" else extraer_docx(ruta)

    if not bloques:
        print("Este documento no produjo texto extraíble.")
        return

    primero = bloques[0]
    referencia = (
        f"Página: {primero['pagina']}" if tipo == "pdf"
        else f"Sección: {primero['seccion']}"
    )
    print(f"\n[Documento: {primero['documento']} | {referencia}]\n")
    print(primero["texto"][:600])
    print("\n[...]")
    print(f"\nBloques con contenido: {len(bloques)}")


def main() -> None:
    pdfs = sorted(DOCUMENTOS_DIR.glob("*.pdf"))
    words = sorted(DOCUMENTOS_DIR.glob("*.docx"))

    if not pdfs and not words:
        print(f"No se encontraron documentos en: {DOCUMENTOS_DIR}")
        sys.exit(1)

    print(f"\nCorpus documental: {len(pdfs)} PDF, {len(words)} Word")

    if pdfs:
        revisar_pdfs(pdfs)
    if words:
        revisar_docx(words)

    # Muestra de cada formato para verificar la calidad de la extracción.
    if pdfs:
        mostrar_muestra(pdfs[0], "pdf")
    if words:
        mostrar_muestra(words[0], "docx")


if __name__ == "__main__":
    main()
