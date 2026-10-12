"""
Verificación de la detección de elementos eliminables.

Ejecutar desde la raíz del proyecto:
    python verificar_limpieza.py

Muestra qué líneas y secuencias identificará la limpieza como eliminables en
cada documento, sin aplicar los cambios. Permite comprobar que la detección no
esté suprimiendo contenido legítimo antes de reconstruir el índice.
"""

import sys

from src.config import DOCUMENTOS_DIR
from src.ingesta.extractor_pdf import extraer_pdf
from src.ingesta.extractor_docx import extraer_docx
from src.procesamiento.limpieza import diagnosticar_limpieza, limpiar_documento

SEP = "=" * 78


def main() -> None:
    rutas = sorted(
        list(DOCUMENTOS_DIR.glob("*.pdf")) + list(DOCUMENTOS_DIR.glob("*.docx"))
    )

    if not rutas:
        print(f"No se encontraron documentos en: {DOCUMENTOS_DIR}")
        sys.exit(1)

    print("\nELEMENTOS QUE SE ELIMINARÁN")
    print(SEP)

    for ruta in rutas:
        bloques = (
            extraer_pdf(ruta) if ruta.suffix.lower() == ".pdf"
            else extraer_docx(ruta)
        )

        if not bloques:
            continue

        print(f"\n{ruta.name}")

        diagnostico = diagnosticar_limpieza(bloques)

        repetidas = diagnostico["lineas_repetidas"]
        navegacion = diagnostico["secuencias_navegacion"]

        if repetidas:
            print(f"  Líneas repetidas ({len(repetidas)}):")
            for linea in repetidas[:6]:
                print(f"    - «{linea[:60]}»")
            if len(repetidas) > 6:
                print(f"    ... y {len(repetidas) - 6} más")
        else:
            print("  Líneas repetidas: ninguna")

        if navegacion:
            print(f"  Secuencias de navegación ({len(navegacion)}):")
            for secuencia in navegacion[:6]:
                print(f"    - «{secuencia}»")
            if len(navegacion) > 6:
                print(f"    ... y {len(navegacion) - 6} más")
        else:
            print("  Secuencias de navegación: ninguna")

    # Comparación detallada sobre el documento más afectado.
    print("\n" + SEP)
    print("COMPARACIÓN ANTES / DESPUÉS")
    print(SEP)

    objetivo = next(
        (r for r in rutas if "Cronograma" in r.name),
        rutas[0],
    )

    bloques = (
        extraer_pdf(objetivo) if objetivo.suffix.lower() == ".pdf"
        else extraer_docx(objetivo)
    )

    if not bloques:
        return

    limpios = limpiar_documento(bloques)

    # Busca un bloque intermedio, donde suelen concentrarse los artefactos.
    indice = min(10, len(bloques) - 1)

    print(f"\nDocumento: {objetivo.name} (bloque {indice + 1})")
    print("\n--- ANTES ---\n")
    print(bloques[indice]["texto"][:500])

    if indice < len(limpios):
        print("\n--- DESPUÉS ---\n")
        print(limpios[indice]["texto"][:500])


if __name__ == "__main__":
    main()
