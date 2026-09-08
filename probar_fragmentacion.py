"""
Prueba del pipeline de limpieza y fragmentación.

Ejecutar desde la raíz del proyecto:
    python probar_fragmentacion.py

Procesa el corpus completo aplicando extracción, limpieza y fragmentación, y
reporta el resultado. Incluye una comparación del texto antes y después de la
limpieza, cuya captura se emplea en la sección 4.6 del documento escrito.
"""

import sys

from src.config import DOCUMENTOS_DIR, TAMANO_FRAGMENTO, SOLAPAMIENTO
from src.ingesta.extractor_pdf import extraer_pdf
from src.ingesta.extractor_docx import extraer_docx
from src.procesamiento.limpieza import limpiar_documento
from src.procesamiento.fragmentacion import fragmentar_documento, estadisticas

SEP = "=" * 78


def procesar(ruta):
    """Ejecuta el pipeline completo sobre un documento."""
    if ruta.suffix.lower() == ".pdf":
        bloques = extraer_pdf(ruta)
    else:
        bloques = extraer_docx(ruta)

    if not bloques:
        return None, None, None

    limpios = limpiar_documento(bloques)
    fragmentos = fragmentar_documento(limpios)

    return bloques, limpios, fragmentos


def main() -> None:
    rutas = sorted(
        list(DOCUMENTOS_DIR.glob("*.pdf")) + list(DOCUMENTOS_DIR.glob("*.docx"))
    )

    if not rutas:
        print(f"No se encontraron documentos en: {DOCUMENTOS_DIR}")
        sys.exit(1)

    print(f"\nConfiguración: fragmento={TAMANO_FRAGMENTO}, solapamiento={SOLAPAMIENTO}")
    print(SEP)

    total_fragmentos = 0
    comparacion = None

    for ruta in rutas:
        bloques, limpios, fragmentos = procesar(ruta)

        print(f"\n{ruta.name}")

        if not bloques:
            print("  Sin contenido extraíble. Documento omitido.")
            continue

        est = estadisticas(fragmentos)
        total_fragmentos += est["total"]

        car_original = sum(len(b["texto"]) for b in bloques)
        car_limpio = sum(len(b["texto"]) for b in limpios)
        reduccion = (
            100 * (car_original - car_limpio) / car_original if car_original else 0
        )

        print(f"  Bloques extraídos    : {len(bloques)}")
        print(f"  Caracteres original  : {car_original:,}")
        print(f"  Caracteres limpio    : {car_limpio:,}  (-{reduccion:.1f}%)")
        print(f"  Fragmentos generados : {est['total']}")
        print(f"  Longitud media       : {est['longitud_media']:,}")
        print(f"  Longitud mín / máx   : {est['longitud_minima']} / {est['longitud_maxima']}")

        if est["multipagina"]:
            print(f"  Fragmentos multipágina: {est['multipagina']}")

        # Guarda el primer documento con contenido para la comparación.
        if comparacion is None and bloques:
            comparacion = (ruta.name, bloques[0]["texto"], limpios[0]["texto"])

    print("\n" + SEP)
    print(f"TOTAL DE FRAGMENTOS EN EL CORPUS: {total_fragmentos}")
    print(SEP)

    # Comparación antes / después de la limpieza.
    if comparacion:
        nombre, original, limpio = comparacion
        print(f"\nCOMPARACIÓN DE LIMPIEZA — {nombre}")
        print(SEP)
        print("\n--- TEXTO EXTRAÍDO (sin procesar) ---\n")
        print(original[:500])
        print("\n--- TEXTO LIMPIO ---\n")
        print(limpio[:500])

    # Muestra de fragmentos con su referencia de origen.
    print("\n" + SEP)
    print("MUESTRA DE FRAGMENTOS")
    print(SEP)

    for ruta in rutas[:3]:
        _, _, fragmentos = procesar(ruta)
        if not fragmentos:
            continue

        fragmento = fragmentos[0]
        print(f"\n[{fragmento['documento']} | {fragmento['referencia']}]")
        print(f"[{len(fragmento['texto'])} caracteres]\n")
        print(fragmento["texto"][:400])
        print("...")


if __name__ == "__main__":
    main()
